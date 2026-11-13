"""Fetch Yahoo Finance NAV for US funds that currently have no NAV observation.

Queries the DB for funds with ticker but no NAV, batches them through
Yahoo's spark endpoint, and upserts directly into nav_observations.
No intermediate CSV step.
"""
from __future__ import annotations

import json
import logging
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import SessionLocal
from app.models.schema import Fund, NavObservation, Source

LOGGER = logging.getLogger("fill_missing_navs_yahoo")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

YAHOO_SPARK = "https://query1.finance.yahoo.com/v8/finance/spark"
SOURCE_ID = "us_yahoo_mutual_fund_navs"
BATCH = 20
DELAY = 0.5


def _decimal(val) -> Decimal | None:
    try:
        return Decimal(str(val).replace(",", "").replace("$", "").strip())
    except (InvalidOperation, ValueError, TypeError):
        return None


def _ensure_source(session) -> None:
    session.execute(
        pg_insert(Source).values(
            source_id=SOURCE_ID,
            source_name="US mutual fund daily NAV observations (Yahoo)",
            country_code="US",
            organization="Yahoo Finance",
            endpoint_url=YAHOO_SPARK,
            verification_status="Undiscovered",
            integration_status="Active",
            license_status="Unknown",
        ).on_conflict_do_nothing()
    )
    session.commit()


def get_missing_funds(session, limit: int = 10000) -> list[tuple[int, str]]:
    rows = session.execute(text("""
        SELECT f.id, f.ticker
        FROM funds f
        LEFT JOIN (SELECT DISTINCT fund_id FROM nav_observations) nav ON nav.fund_id = f.id
        WHERE f.domicile_country = 'US'
          AND f.ticker IS NOT NULL AND f.ticker != ''
          AND nav.fund_id IS NULL
        ORDER BY f.ticker
        LIMIT :limit
    """), {"limit": limit}).fetchall()
    return [(r[0], r[1].strip().upper()) for r in rows]


def fetch_yahoo_batch(tickers: list[str]) -> dict[str, dict]:
    """Fetch NAV from Yahoo spark endpoint for a batch of tickers."""
    query = "symbols=" + ",".join(tickers) + "&range=1mo&interval=1d"
    url = YAHOO_SPARK + "?" + query
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.load(r)
        return payload if isinstance(payload, dict) else {}
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("Yahoo batch failed: %s", exc)
        return {}


def main(limit: int = 10000, dry_run: bool = False) -> None:
    with SessionLocal() as session:
        _ensure_source(session)
        LOGGER.info("Finding funds with ticker but no NAV...")
        missing = get_missing_funds(session, limit=limit)

    LOGGER.info("Found %d funds with ticker but no NAV", len(missing))
    ticker_to_id = {ticker: fid for fid, ticker in missing}
    tickers = list(ticker_to_id.keys())

    inserted_total = 0
    errors = 0

    for i in range(0, len(tickers), BATCH):
        batch_tickers = tickers[i : i + BATCH]
        payload = fetch_yahoo_batch(batch_tickers)
        time.sleep(DELAY)

        nav_rows = []
        for ticker, data in payload.items():
            fund_id = ticker_to_id.get(ticker.upper())
            if not fund_id:
                continue
            ts = data.get("timestamp") or []
            closes = data.get("close") or []
            pairs = [(t, v) for t, v in zip(ts, closes) if v is not None]
            if not pairs:
                continue
            stamp, nav_val = pairs[-1]
            nav = _decimal(nav_val)
            if nav is None:
                continue
            val_date = datetime.fromtimestamp(stamp, tz=timezone.utc).date()
            source_url = f"{YAHOO_SPARK}?symbols={ticker}&range=1mo&interval=1d"
            nav_rows.append({
                "fund_id": fund_id,
                "source_id": SOURCE_ID,
                "valuation_date": val_date,
                "nav": nav,
                "open": nav, "high": nav, "low": nav, "close": nav,
                "ohlc_basis": "single_daily_nav",
                "currency": "USD",
                "source_url": source_url,
            })

        if nav_rows and not dry_run:
            with SessionLocal() as session:
                result = session.execute(
                    pg_insert(NavObservation).values(nav_rows).on_conflict_do_nothing()
                )
                session.commit()
                inserted_total += len(nav_rows)

        if (i // BATCH + 1) % 25 == 0 or i + BATCH >= len(tickers):
            LOGGER.info(
                "processed=%d/%d inserted=%d errors=%d",
                min(i + BATCH, len(tickers)), len(tickers), inserted_total, errors,
            )

    LOGGER.info("Done: inserted=%d errors=%d dry_run=%s", inserted_total, errors, dry_run)


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--limit", type=int, default=10000)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    main(limit=args.limit, dry_run=args.dry_run)
