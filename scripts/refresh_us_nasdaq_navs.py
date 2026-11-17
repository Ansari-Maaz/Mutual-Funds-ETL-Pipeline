"""Rate-limited refresh of US mutual-fund prices from Nasdaq's official APIs.

The SEC connector supplies the ticker universe. Use --ticker to refresh a
specific fund and its Nasdaq metadata; the normal SEC ETL command loads the
resulting daily observation into FundFlow.
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
        writer = csv.DictWriter(stream, fieldnames=["ticker", "valuation_date", "nav", "open", "high", "low", "close", "source_url"])
        writer.writeheader()
        writer.writerows(sorted(rows.values(), key=lambda row: row["ticker"]))
        stream.flush()
    temporary.replace(OUT)


def _price(value: str | None) -> str | None:
    value = (value or "").replace("$", "").replace(",", "").strip()
    return value if value and value.upper() not in {"N/A", "NA", "-"} else None


def fetch(ticker: str, start: date, end: date) -> dict[str, str] | None:
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
        nav = _price(row.get("close"))
        if not nav:
            return None
        return {"valuation_date": valuation_date, "nav": nav,
                "open": _price(row.get("open")) or nav,
                "high": _price(row.get("high")) or nav,
                "low": _price(row.get("low")) or nav,
                "close": nav}
    except (ValueError, KeyError, TypeError, json.JSONDecodeError, urllib.error.URLError, OSError) as exc:
        logging.getLogger(__name__).warning("Nasdaq request failed for %s: %s", ticker, exc)
        return None


def fetch_info(ticker: str) -> tuple[dict, str]:
    url = f"https://api.nasdaq.com/api/quote/{urllib.parse.quote(ticker)}/info?assetclass=mutualfunds"
    request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"})
    with urllib.request.urlopen(request, timeout=20) as response:
        payload = json.load(response)
    info = payload.get("data") or {}
    if str(info.get("symbol", "")).upper() != ticker.upper():
        raise ValueError(f"Nasdaq info response did not match ticker {ticker}")
    return info, url


def save_official_metadata(ticker: str, info: dict, info_url: str) -> None:
    """Persist Nasdaq's published market metadata with its own source provenance."""
    from sqlalchemy import select
    from sqlalchemy.dialects.postgresql import insert
    from app.db.session import SessionLocal
    from app.etl.load import upsert_fund_profile_snapshots
    from app.models.schema import Fund, Source

    source_id = "us_nasdaq_mutual_fund_navs"
    with SessionLocal() as session:
        stmt = insert(Source).values(source_id=source_id, country_code="US", organization="Nasdaq",
            source_name="Nasdaq Fund Network mutual-fund market data", endpoint_url=info_url,
            verification_status="Usable Fund Data Confirmed", integration_status="Integrated",
            license_status="Unknown")
        session.execute(stmt.on_conflict_do_update(index_elements=[Source.source_id], set_={
            "organization": stmt.excluded.organization, "source_name": stmt.excluded.source_name,
            "endpoint_url": stmt.excluded.endpoint_url}))
        fund = session.execute(select(Fund).where(Fund.source_id == "sec_open_end_fund_classes",
            Fund.ticker.ilike(ticker))).scalars().one_or_none()
        if fund is None:
            raise LookupError(f"No SEC master fund record found for {ticker}")
        payload = {
            "symbol": info.get("symbol"),
            "instrument_type": "Mutual Fund" if info.get("assetClass") == "MUTUALFUNDS" else info.get("stockType"),
            "source_instrument_type": info.get("stockType"),
            "exchange": info.get("exchange"),
            "mic_code": None,
            "currency": (info.get("primaryData") or {}).get("currency"),
            "exchange_timezone": None,
            "interval": "1day",
            "is_nasdaq_listed": info.get("isNasdaqListed"),
            "field_sources": {
                "symbol": {"source_id": "sec_open_end_fund_classes", "source_url": "https://www.sec.gov/files/investment/data/other/investment-company-series-class-information/investment-company-series-class-2026.csv"},
                "instrument_type": {"source_id": source_id, "source_url": info_url},
                "exchange": {"source_id": source_id, "source_url": info_url},
                "mic_code": None,
                "exchange_timezone": None,
                "currency": {"source_id": source_id, "source_url": info_url},
                "interval": {"basis": "daily historical endpoint"},
            },
            "note": "Nasdaq reports this as a Nasdaq Fund Network managed fund; it is not marked Nasdaq-listed. MIC and exchange timezone are not supplied by this official response.",
        }
        upsert_fund_profile_snapshots(session, fund.id, source_id,
            {"market_data_metadata": payload}, as_of_date=date.today(), source_url=info_url)
        session.commit()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--ticker", action="append", help="Refresh this ticker directly (repeatable); unlike default mode this refreshes existing rows too")
    parser.add_argument("--missing-nav", action="store_true", help="Only request tickers whose fund has no stored NAV observation")
    args = parser.parse_args()
    db_url = database_url().replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(db_url) as connection:
        if args.ticker:
            tickers = sorted({t.strip().upper() for t in args.ticker if t.strip()})
        elif args.missing_nav:
            tickers = [r[0] for r in connection.execute(
                "select distinct f.ticker from funds f "
                "where f.source_id='sec_open_end_fund_classes' "
                "and f.ticker is not null and f.ticker <> '' "
                "and not exists (select 1 from nav_observations n where n.fund_id=f.id) "
                "order by f.ticker")]
        else:
            tickers = [r[0] for r in connection.execute("select distinct ticker from funds where source_id='sec_open_end_fund_classes' and ticker is not null and ticker <> '' order by ticker")]
    if args.limit and not args.ticker:
        tickers = tickers[:args.limit]
    existing: dict[str, dict[str, str]] = {}
    if OUT.exists():
        with OUT.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                existing[row["ticker"]] = row
    # Refresh Nasdaq data only in its own output; the SEC connector can merge
    # the separate Yahoo file without either script replacing the other.
    if not args.ticker and not args.missing_nav:
        tickers = [ticker for ticker in tickers if ticker not in existing]
    start = date.today() - timedelta(days=30)
    end = date.today()
    failures = 0
    for index, ticker in enumerate(tickers, start=1):
        result = fetch(ticker, start, end)
        if result:
            date_params = urllib.parse.urlencode({"assetclass": "mutualfunds", "fromdate": start.isoformat(), "todate": end.isoformat(), "limit": 20})
            history_url = f"https://api.nasdaq.com/api/quote/{urllib.parse.quote(ticker)}/historical?{date_params}"
            existing[ticker] = {"ticker": ticker, **result, "source_url": history_url}
            if args.ticker:
                info, info_url = fetch_info(ticker)
                save_official_metadata(ticker, info, info_url)
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
