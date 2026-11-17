"""Fetch Nasdaq's official daily history for the FundFlow comparison sample.

Dry-run by default. Use --apply to replace the sample-window observations with
Nasdaq-sourced values after creating a JSON backup of the affected rows.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal
import json
from pathlib import Path
import sys
import time
import urllib.parse

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.db.session import SessionLocal
from app.models.schema import Fund, NavObservation, Source

MF_SOURCE = "us_nasdaq_mutual_fund_navs"
ETF_SOURCE = "us_nasdaq_etf_market_prices"
MF_TICKERS = ["VFIAX", "VTSAX", "FXAIX", "SWPPX", "FCNTX", "DODGX", "FBALX", "VWELX", "VBTLX", "VTIAX"]
ETF_TICKERS = ["QQQM"]


def fetch(client: httpx.Client, symbol: str, asset_class: str, start: date, end: date) -> tuple[list[dict], str]:
    params = {"assetclass": asset_class, "fromdate": start.isoformat(), "todate": end.isoformat(), "limit": 100}
    url = f"https://api.nasdaq.com/api/quote/{urllib.parse.quote(symbol)}/historical?{urllib.parse.urlencode(params)}"
    response = client.get(url)
    response.raise_for_status()
    payload = response.json()
    raw_rows = (((payload.get("data") or {}).get("tradesTable") or {}).get("rows") or [])
    rows = []
    for raw in raw_rows:
        mm, dd, yyyy = (raw.get("date") or "").split("/")
        observed = date(int(yyyy), int(mm), int(dd))
        if not start <= observed <= end:
            continue
        def price(key: str) -> Decimal | None:
            value = (raw.get(key) or "").replace("$", "").replace(",", "").strip()
            return Decimal(value) if value and value.upper() not in {"N/A", "NA", "-"} else None
        close = price("close")
        if close is None:
            continue
        rows.append({"date": observed.isoformat(), "open": price("open"), "high": price("high"),
                     "low": price("low"), "close": close})
    return rows, url


def load_data(start: date, end: date, delay: float) -> list[dict]:
    result = []
    headers = {"User-Agent": "Mozilla/5.0 FundFlow beta validation", "Accept": "application/json, text/plain, */*",
               "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/"}
    with httpx.Client(timeout=30, headers=headers, follow_redirects=True) as client:
        all_items = [(ticker, "mutualfunds", "mutual_fund") for ticker in MF_TICKERS] + [(ticker, "etf", "etf_market_price") for ticker in ETF_TICKERS]
        for index, (ticker, asset_class, kind) in enumerate(all_items):
            rows, url = fetch(client, ticker, asset_class, start, end)
            if not rows:
                raise RuntimeError(f"Nasdaq returned no rows for {ticker} in requested interval")
            result.append({"ticker": ticker, "kind": kind, "source_id": MF_SOURCE if kind == "mutual_fund" else ETF_SOURCE,
                           "source_url": url, "observations": rows})
            if delay and index + 1 < len(all_items):
                time.sleep(delay)
    return result


def resolve_fund(session, item: dict) -> Fund:
    ticker, kind = item["ticker"], item["kind"]
    if kind == "etf_market_price":
        matches = session.execute(select(Fund).where(Fund.source_id == "us_qqqm_etf", Fund.source_fund_id == "QQQM")).scalars().all()
    else:
        matches = session.execute(select(Fund).where(Fund.source_id == "sec_open_end_fund_classes", Fund.ticker.ilike(ticker))).scalars().all()
    if len(matches) != 1:
        raise LookupError(f"Expected one canonical FundFlow record for {ticker}; found {len(matches)}")
    return matches[0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-date", type=date.fromisoformat, default=date(2026, 10, 30))
    parser.add_argument("--end-date", type=date.fromisoformat, default=date(2026, 11, 6))
    parser.add_argument("--delay", type=float, default=0.35)
    parser.add_argument("--apply", action="store_true", help="Back up then upsert Nasdaq records into the configured FundFlow database.")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/nasdaq_official_comparison_data_2026-10-30_2026-11-06.json")
    args = parser.parse_args()
    if args.start_date > args.end_date:
        parser.error("--start-date must be on or before --end-date")
    data = load_data(args.start_date, args.end_date, args.delay)
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "source": "Nasdaq official historical API",
               "source_url": "https://api.nasdaq.com/api/quote/{symbol}/historical", "start_date": args.start_date.isoformat(),
               "end_date": args.end_date.isoformat(), "note": "Mutual-fund rows are daily NAV observations. QQQM rows are ETF market-price bars, not NAV.", "funds": data}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, default=str) + "\n", encoding="utf-8")
    writes = 0
    backup_path = args.output.with_name("nasdaq_official_refresh_backup_2026-11-09.json")
    if args.apply:
        start, end = args.start_date, args.end_date
        with SessionLocal() as session:
            resolved = [(item, resolve_fund(session, item)) for item in data]
            fund_ids = [fund.id for _, fund in resolved]
            old = session.execute(select(NavObservation).where(NavObservation.fund_id.in_(fund_ids),
                NavObservation.valuation_date >= start, NavObservation.valuation_date <= end)).scalars().all()
            backup = {"created_at": datetime.now(timezone.utc).isoformat(), "reason": "Pre-upsert backup; Nasdaq official comparison window refresh",
                      "rows": [{"id": row.id, "fund_id": row.fund_id, "source_id": row.source_id, "source_url": row.source_url,
                                "valuation_date": row.valuation_date.isoformat(), "nav": str(row.nav), "open": str(row.open) if row.open is not None else None,
                                "high": str(row.high) if row.high is not None else None, "low": str(row.low) if row.low is not None else None,
                                "close": str(row.close) if row.close is not None else None, "ohlc_basis": row.ohlc_basis, "currency": row.currency}
                               for row in old]}
            backup_path.write_text(json.dumps(backup, indent=2) + "\n", encoding="utf-8")
            session.execute(insert(Source).values(source_id=ETF_SOURCE, country_code="US", organization="Nasdaq",
                source_name="Nasdaq ETF historical market prices", endpoint_url="https://api.nasdaq.com/api/quote/QQQM/historical",
                verification_status="Usable Fund Data Confirmed", integration_status="Integrated", license_status="Unknown")
                .on_conflict_do_update(index_elements=[Source.source_id], set_={"endpoint_url": "https://api.nasdaq.com/api/quote/QQQM/historical"}))
            for item, fund in resolved:
                for observation in item["observations"]:
                    close = observation["close"]
                    is_etf = item["kind"] == "etf_market_price"
                    values = {"fund_id": fund.id, "source_id": item["source_id"], "source_url": item["source_url"],
                              "valuation_date": date.fromisoformat(observation["date"]), "nav": close,
                              "currency": "USD", "ohlc_basis": "source_reported_ohlc" if is_etf else "single_daily_nav",
                              "open": observation["open"] if is_etf else close,
                              "high": observation["high"] if is_etf else close,
                              "low": observation["low"] if is_etf else close,
                              "close": close}
                    statement = insert(NavObservation).values(**values).on_conflict_do_update(
                        constraint="uq_nav_fund_date_currency", set_={k: v for k, v in values.items() if k != "fund_id"})
                    session.execute(statement)
                    writes += 1
            session.commit()
    print(json.dumps({"data_file": str(args.output), "apply": args.apply, "backup_file": str(backup_path) if args.apply else None,
                      "instruments": len(data), "observations": sum(len(x["observations"]) for x in data), "upserts": writes}, indent=2))


if __name__ == "__main__":
    main()
