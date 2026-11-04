"""Backfill US NAV source fields only when a raw row exactly matches the DB.

The Yahoo and Nasdaq files contain public price observations, not verified
issuer NAVs. This script records provenance and preserves that distinction in
the source catalogue; it never labels those rows official NAVs.
"""
from __future__ import annotations

import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert

from app.db.session import SessionLocal
from app.models.schema import Fund, NavObservation, Source

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data/raw/united_states"
SOURCE_ROWS = (
    ("us_yahoo_mutual_fund_navs", "Yahoo Finance", "Public US mutual fund daily price series",
     "https://query1.finance.yahoo.com/v8/finance/spark"),
    ("us_nasdaq_mutual_fund_navs", "Nasdaq", "Public historical US mutual fund prices",
     "https://api.nasdaq.com/api/quote/QQQM/historical?assetclass=mutualfunds"),
)
FILES = (
    ("us_yahoo_mutual_fund_navs", RAW / "yahoo_mutual_fund_navs.csv"),
    ("us_nasdaq_mutual_fund_navs", RAW / "nasdaq_mutual_fund_navs.csv"),
)


def load_candidates() -> dict[tuple[str, date], list[dict[str, str]]]:
    """Collect publisher alternatives; choose only one matching the DB value."""
    candidates: dict[tuple[str, date], list[dict[str, str]]] = {}
    for source_id, path in FILES:
        if not path.exists():
            continue
        with path.open(encoding="utf-8-sig", newline="") as stream:
            for row in csv.DictReader(stream):
                ticker = (row.get("ticker") or "").strip().upper()
                try:
                    observation_date = date.fromisoformat((row.get("valuation_date") or "")[:10])
                    value = Decimal((row.get("nav") or "").replace(",", "").replace("$", "").strip())
                except (ValueError, InvalidOperation):
                    continue
                if not ticker or not value.is_finite() or value <= 0:
                    continue
                url = (row.get("source_url") or "").strip()
                if not url:
                    url = (f"https://query1.finance.yahoo.com/v8/finance/spark?symbols={ticker}&range=1mo&interval=1d"
                           if source_id == "us_yahoo_mutual_fund_navs"
                           else f"https://api.nasdaq.com/api/quote/{ticker}/historical?assetclass=mutualfunds")
                key = (ticker, observation_date)
                candidates.setdefault(key, []).append({"source_id": source_id, "source_url": url, "value": str(value)})
    return candidates


def backfill() -> dict[str, int]:
    candidates = load_candidates()
    if not candidates:
        return {"raw_observations": 0, "unique_fund_matches": 0, "exact_database_matches": 0,
                "updated_rows": 0, "ambiguous_tickers": 0}
    tickers = {ticker for ticker, _ in candidates}
    metadata = {source_id: {"source_id": source_id, "country_code": "US", "organization": organization,
        "source_name": name, "endpoint_url": url, "verification_status": "Discovered",
        "integration_status": "In Progress", "license_status": "Unknown"}
        for source_id, organization, name, url in SOURCE_ROWS}
    counters = {"raw_observations": len(candidates), "unique_fund_matches": 0,
                "exact_database_matches": 0, "updated_rows": 0, "ambiguous_tickers": 0}
    with SessionLocal() as session:
        for source in metadata.values():
            statement = insert(Source).values(**source).on_conflict_do_update(
                index_elements=[Source.source_id],
                set_={key: value for key, value in source.items() if key != "source_id"})
            session.execute(statement)
        funds_by_ticker: dict[str, list[int]] = {}
        for fund_id, ticker in session.execute(select(Fund.id, Fund.ticker).where(
                Fund.domicile_country == "US", Fund.source_id == "sec_open_end_fund_classes",
                Fund.ticker.in_(tickers))):
            funds_by_ticker.setdefault(ticker.strip().upper(), []).append(fund_id)
        matched_sources: set[str] = set()
        for (ticker, valuation_date), alternatives in candidates.items():
            fund_ids = funds_by_ticker.get(ticker, [])
            if len(fund_ids) != 1:
                counters["ambiguous_tickers"] += bool(fund_ids)
                continue
            counters["unique_fund_matches"] += 1
            fund_id = fund_ids[0]
            stored = session.execute(select(NavObservation.id, NavObservation.nav, NavObservation.source_id).where(
                NavObservation.fund_id == fund_id,
                NavObservation.valuation_date == valuation_date,
                NavObservation.currency == "USD")).first()
            if not stored:
                continue
            matches = [source for source in alternatives if Decimal(stored.nav) == Decimal(source["value"])]
            if not matches:
                continue
            source = next((row for row in matches if row["source_id"] == "us_nasdaq_mutual_fund_navs"), matches[0])
            counters["exact_database_matches"] += 1
            matched_sources.add(source["source_id"])
            if stored.source_id is not None:
                continue
            result = session.execute(update(NavObservation).where(
                NavObservation.id == stored.id, NavObservation.source_id.is_(None)).values(
                    source_id=source["source_id"], source_url=source["source_url"]))
            counters["updated_rows"] += result.rowcount
        for source_id in matched_sources:
            session.execute(update(Source).where(Source.source_id == source_id).values(
                verification_status="Usable Fund Data Confirmed", integration_status="Integrated"))
        session.commit()
    return counters


if __name__ == "__main__":
    import json
    print(json.dumps(backfill(), indent=2))
