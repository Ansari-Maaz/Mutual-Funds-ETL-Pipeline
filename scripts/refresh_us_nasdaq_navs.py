"""Rate-limited refresh of current US mutual-fund NAVs from Nasdaq.

The SEC connector supplies the ticker universe. This script only writes raw
source rows; the normal ETL command performs validation and database upserts.
"""
from __future__ import annotations

import argparse
import csv
import json
import time
import urllib.parse
import urllib.request
import urllib.error
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import database_url
OUT = ROOT / "data" / "raw" / "united_states" / "nasdaq_mutual_fund_navs.csv"


def write_rows(rows: dict[str, dict[str, str]]) -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    temporary = OUT.with_suffix(OUT.suffix + ".tmp")
    with temporary.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["ticker", "valuation_date", "nav", "source_url"])
        writer.writeheader()
        writer.writerows(sorted(rows.values(), key=lambda row: row["ticker"]))
        stream.flush()
    temporary.replace(OUT)


def fetch(ticker: str, start: date, end: date) -> tuple[str, str] | None:
    query = urllib.parse.urlencode({"assetclass": "mutualfunds", "fromdate": start.isoformat(), "todate": end.isoformat(), "limit": 20})
    url = f"https://api.nasdaq.com/api/quote/{urllib.parse.quote(ticker)}/historical?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
        rows = ((payload.get("data") or {}).get("tradesTable") or {}).get("rows") or []
        if not rows:
            return None
        row = rows[0]
        mm, dd, yyyy = (row.get("date") or "").split("/")
        valuation_date = f"{yyyy}-{mm.zfill(2)}-{dd.zfill(2)}"
        nav = (row.get("close") or "").replace("$", "").replace(",", "").strip()
        if not nav or nav.upper() in {"N/A", "NA", "-"}:
            return None
        return valuation_date, nav
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, urllib.error.URLError, OSError) as exc:
        logging.getLogger(__name__).warning("Nasdaq request failed for %s: %s", ticker, exc)
        return None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    db_url = database_url().replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(db_url) as connection:
        tickers = [r[0] for r in connection.execute("select distinct ticker from funds where source_id='sec_open_end_fund_classes' and ticker is not null and ticker <> '' order by ticker")]
    if args.limit:
        tickers = tickers[:args.limit]
    existing: dict[str, dict[str, str]] = {}
    if OUT.exists():
        with OUT.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                existing[row["ticker"]] = row
    # Refresh Nasdaq data only in its own output; the SEC connector can merge
    # the separate Yahoo file without either script replacing the other.
    tickers = [ticker for ticker in tickers if ticker not in existing]
    start = date.today() - timedelta(days=30)
    end = date.today()
    failures = 0
    for index, ticker in enumerate(tickers, start=1):
        result = fetch(ticker, start, end)
        if result:
            valuation_date, nav = result
            existing[ticker] = {"ticker": ticker, "valuation_date": valuation_date, "nav": nav,
                                "source_url": "https://api.nasdaq.com/api/quote/" + ticker + "/historical?assetclass=mutualfunds"}
        else:
            failures += 1
        if index % 100 == 0 or index == len(tickers):
            write_rows(existing)
            print(f"processed={index}/{len(tickers)} successful={len(existing)}", flush=True)
        if index < len(tickers):
            time.sleep(max(0.0, args.delay))
    print(f"wrote={len(existing)} path={OUT}")
    if tickers and not existing:
        raise SystemExit(f"No Nasdaq rows were retrieved; {failures} tickers failed or returned no data")


if __name__ == "__main__":
    main()
