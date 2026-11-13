"""Direct reload of US mutual fund NAVs from local CSV snapshots into nav_observations.

Reads the existing nasdaq_mutual_fund_navs.csv and yahoo_mutual_fund_navs.csv
files and upserts NAV rows directly into nav_observations. Faster than
re-running the full SEC ETL connector. Only adds missing rows (idempotent).
"""
from __future__ import annotations

import csv
import logging
import sys
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text as _text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import SessionLocal
from app.models.schema import Fund, NavObservation, Source

LOGGER = logging.getLogger("reload_nav_csvs")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

RAW = ROOT / "data" / "raw" / "united_states"
NASDAQ_CSV = RAW / "nasdaq_mutual_fund_navs.csv"
YAHOO_CSV  = RAW / "yahoo_mutual_fund_navs.csv"

SOURCES = {
    "us_nasdaq_mutual_fund_navs": {
        "source_id": "us_nasdaq_mutual_fund_navs",
        "country_code": "US",
        "organization": "Nasdaq",
        "source_name": "US mutual fund daily NAV observations (Nasdaq)",
        "endpoint_url": "https://api.nasdaq.com/api/quote/",
        "verification_status": "Official",
        "integration_status": "Active",
        "license_status": "Public",
    },
    "us_yahoo_mutual_fund_navs": {
        "source_id": "us_yahoo_mutual_fund_navs",
        "country_code": "US",
        "organization": "Yahoo Finance",
        "source_name": "US mutual fund daily NAV observations (Yahoo)",
        "endpoint_url": "https://query1.finance.yahoo.com/v8/finance/spark",
        "verification_status": "Undiscovered",
        "integration_status": "Active",
        "license_status": "Unknown",
    },
}


def _ensure_sources(session) -> None:
    for src in SOURCES.values():
        session.execute(pg_insert(Source).values(**src).on_conflict_do_nothing())
    session.commit()


def _decimal(val: str) -> Decimal | None:
    try:
        cleaned = str(val).replace("$", "").replace(",", "").strip()
        if not cleaned or cleaned.upper() in ("N/A", "NA", ""):
            return None
        return Decimal(cleaned)
    except InvalidOperation:
        return None


def _load_ticker_map(session) -> dict[str, int]:
    """Return {ticker_upper: fund_id} for all US funds with a ticker."""
    rows = session.execute(
        _text("SELECT id, ticker FROM funds WHERE domicile_country='US' AND ticker IS NOT NULL AND ticker != ''")
    ).fetchall()
    return {row[1].strip().upper(): row[0] for row in rows}


def reload_csv(csv_path: Path, source_id: str, ticker_map: dict[str, int], batch_size: int = 1000) -> dict:
    if not csv_path.exists():
        LOGGER.warning("CSV not found: %s", csv_path)
        return {"skipped": True, "path": str(csv_path)}

    inserted = 0
    skipped = 0
    batch: list[dict] = []

    def flush_batch(b: list) -> int:
        if not b:
            return 0
        with SessionLocal() as session:
            stmt = pg_insert(NavObservation).values(b).on_conflict_do_nothing()
            result = session.execute(stmt)
            session.commit()
            return result.rowcount

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            ticker = (row.get("ticker") or "").strip().upper()
            fund_id = ticker_map.get(ticker)
            if not fund_id:
                skipped += 1
                continue
            nav = _decimal(row.get("nav") or row.get("close") or "")
            if nav is None:
                skipped += 1
                continue
            val_date_str = (row.get("valuation_date") or "").strip()
            if not val_date_str:
                skipped += 1
                continue
            try:
                val_date = date.fromisoformat(val_date_str)
            except ValueError:
                skipped += 1
                continue

            # Build open/high/low/close — for open-end MFs collapse to single NAV
            o = _decimal(row.get("open") or "")
            h = _decimal(row.get("high") or "")
            lo = _decimal(row.get("low") or "")
            cl = _decimal(row.get("close") or "")
            if o and h and lo and cl:
                ohlc_basis = "source_reported_ohlc"
            else:
                o = h = lo = cl = nav
                ohlc_basis = "single_daily_nav"

            batch.append({
                "fund_id": fund_id,
                "source_id": source_id,
                "valuation_date": val_date,
                "nav": nav,
                "open": o,
                "high": h,
                "low": lo,
                "close": cl,
                "ohlc_basis": ohlc_basis,
                "currency": "USD",
                "source_url": (row.get("source_url") or "").strip() or None,
            })
            if len(batch) >= batch_size:
                inserted += flush_batch(batch)
                batch = []

    inserted += flush_batch(batch)
    return {"source_id": source_id, "inserted": inserted, "skipped": skipped, "path": str(csv_path)}


def main() -> None:
    with SessionLocal() as session:
        _ensure_sources(session)
        LOGGER.info("Building ticker → fund_id map...")
        ticker_map = _load_ticker_map(session)

    LOGGER.info("Ticker map: %d funds", len(ticker_map))

    # Nasdaq preferred (more authoritative); load Yahoo first so Nasdaq
    # on_conflict rows are skipped rather than overwritten
    for path, src_id in [(YAHOO_CSV, "us_yahoo_mutual_fund_navs"),
                          (NASDAQ_CSV, "us_nasdaq_mutual_fund_navs")]:
        LOGGER.info("Loading %s ...", path.name)
        result = reload_csv(path, src_id, ticker_map)
        LOGGER.info("  → %s", result)


if __name__ == "__main__":
    main()
