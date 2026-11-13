"""Enrich US mutual fund category field from Nasdaq fund-info API.

Nasdaq's /api/quote/{ticker}/info?assetclass=mutualfunds endpoint returns
structured fund metadata including category, objective, and fund family.
This script populates category (and other empty metadata) for all US funds
that have a ticker but lack a category.

Fields populated (only if currently NULL/empty):
  - category
  - manager
  - provider (fund family)

Provenance is recorded as a fund_profile_snapshot with dataset='nasdaq_fund_info'.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import SessionLocal
from app.models.schema import Fund, FundProfileSnapshot, Source

LOGGER = logging.getLogger("enrich_categories")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

SOURCE_ID = "nasdaq_fund_info"
SOURCE_NAME = "Nasdaq Fund Information API"
SOURCE_ORG = "Nasdaq"
NASDAQ_INFO_URL = "https://api.nasdaq.com/api/quote/{ticker}/info?assetclass=mutualfunds"
NASDAQ_SUMMARY_URL = "https://api.nasdaq.com/api/quote/{ticker}/summary?assetclass=mutualfunds"
DELAY = 0.4  # polite rate limit


def _ensure_source(session) -> None:
    stmt = pg_insert(Source).values(
        source_id=SOURCE_ID,
        source_name=SOURCE_NAME,
        country_code="US",
        organization=SOURCE_ORG,
        endpoint_url="https://api.nasdaq.com/api/quote/",
        verification_status="Official",
        integration_status="Active",
        license_status="Public",
    ).on_conflict_do_nothing()
    session.execute(stmt)
    session.commit()


def _fetch_nasdaq_info(ticker: str) -> dict | None:
    """Fetch both info and summary endpoints; merge results."""
    merged: dict = {}
    for url_tmpl in (NASDAQ_INFO_URL, NASDAQ_SUMMARY_URL):
        url = url_tmpl.format(ticker=urllib.parse.quote(ticker))
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=20) as resp:
                result = json.load(resp)
                data = result.get("data") or {}
                merged.update(data)
                # Merge summaryData separately
                if data.get("summaryData"):
                    merged.setdefault("summaryData", {}).update(data["summaryData"])
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
            LOGGER.debug("Nasdaq fetch failed for %s at %s: %s", ticker, url_tmpl, exc)
        time.sleep(0.2)
    return merged if merged else None


def _extract_fields(payload: dict) -> dict:
    """Extract category and metadata from merged Nasdaq API response."""
    summary = payload.get("summaryData") or {}
    primary = payload.get("primaryData") or {}

    def _val(*keys: str) -> str | None:
        for k in keys:
            v = summary.get(k)
            if isinstance(v, dict):
                v = v.get("value")
            if v and str(v).strip() not in ("", "N/A", "--", "None", "Not Assigned"):
                return str(v).strip()
        return None

    def _primary_val(*keys: str) -> str | None:
        for k in keys:
            v = primary.get(k)
            if v and str(v).strip() not in ("", "N/A", "--", "None"):
                return str(v).strip()
        return None

    category = _val("Category", "FundCategory", "InstrumentType")
    # Remove generic "Mutual Fund" as a category — that's already fund_type
    if category and category.lower() in ("mutual fund", "managed fund", "open-end fund"):
        category = None

    return {
        "category": category,
        "manager": _val("FundManager", "Manager"),
        "provider": _val("FundFamily", "FundCompany", "Issuer"),
        "nav": _primary_val("lastSalePrice", "nav"),
        "nav_date": _primary_val("lastTradeTimestamp", "asOfDate"),
        "share_class": _val("ShareClass"),
        "expense_ratio": _val("NetExpenseRatio", "GrossExpenseRatio"),
        "currency_basis": _val("Currency"),
        "raw": payload,
    }


def main(limit: int = 500, dry_run: bool = False, only_missing_category: bool = True) -> None:
    with SessionLocal() as session:
        _ensure_source(session)

        q = select(Fund).where(
            Fund.domicile_country == "US",
            Fund.ticker.isnot(None),
            Fund.ticker != "",
        )
        if only_missing_category:
            q = q.where(
                (Fund.category.is_(None)) | (Fund.category == "")
            )
        q = q.order_by(Fund.ticker).limit(limit)
        candidates = session.execute(q).scalars().all()

    LOGGER.info("Candidates for category enrichment: %d", len(candidates))

    updated = 0
    errors = 0
    skipped = 0

    for fund in candidates:
        ticker = (fund.ticker or "").strip().upper()
        if not ticker:
            skipped += 1
            continue

        payload = _fetch_nasdaq_info(ticker)
        time.sleep(DELAY)

        if not payload:
            errors += 1
            continue

        fields = _extract_fields(payload)
        updates = {}

        # Only update empty fields
        if fields.get("category") and not (fund.category or "").strip():
            updates["category"] = fields["category"]
        if fields.get("manager") and not (fund.manager or "").strip():
            updates["manager"] = fields["manager"]
        if fields.get("provider") and not (fund.provider or "").strip():
            updates["provider"] = fields["provider"]

        if not any([fields.get("category"), fields.get("manager"), fields.get("provider")]):
            skipped += 1
            continue

        LOGGER.info(
            "ticker=%s category=%s manager=%s provider=%s updates=%s",
            ticker, fields.get("category"), fields.get("manager"),
            fields.get("provider"), list(updates.keys()),
        )

        if dry_run:
            updated += 1
            continue

        source_url = NASDAQ_INFO_URL.format(ticker=ticker.lower())
        snap_key = hashlib.md5(f"{fund.id}:nasdaq_fund_info".encode()).hexdigest()[:64]

        with SessionLocal() as session:
            if updates:
                session.execute(
                    update(Fund).where(Fund.id == fund.id).values(**updates)
                )
            snap_stmt = pg_insert(FundProfileSnapshot).values(
                fund_id=fund.id,
                source_id=SOURCE_ID,
                dataset="nasdaq_fund_info",
                source_report_date=date.today(),
                snapshot_key=snap_key,
                payload={
                    **{k: v for k, v in fields.items() if k != "raw"},
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                },
                source_url=source_url,
            ).on_conflict_do_update(
                index_elements=["fund_id", "source_id", "snapshot_key"],
                set_={"payload": pg_insert(FundProfileSnapshot).excluded.payload,
                      "retrieved_at": datetime.now(timezone.utc)},
            )
            session.execute(snap_stmt)
            session.commit()
        updated += 1

    summary = {
        "candidates": len(candidates),
        "updated": updated,
        "skipped": skipped,
        "errors": errors,
        "dry_run": dry_run,
    }
    print(json.dumps(summary, indent=2))
    LOGGER.info("Done: %s", summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich US fund categories from Nasdaq fund info API")
    parser.add_argument("--limit", type=int, default=500, help="Max funds to process")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--all", action="store_true", help="Include funds that already have category")
    args = parser.parse_args()
    main(limit=args.limit, dry_run=args.dry_run, only_missing_category=not args.all)
