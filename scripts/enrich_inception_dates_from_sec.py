"""Enrich US fund inception dates from SEC EDGAR submissions JSON.

Each registered investment company in EDGAR has a submission record at:
  https://data.sec.gov/submissions/CIK{cik10}.json

That record includes ``registrantInfo.dateOfOrganization`` and the oldest
filing effective date, both usable as proxies for inception date where none
is already stored.

This script:
1. Selects US funds missing inception_date that have a sec_cik.
2. Fetches the EDGAR submission JSON for each CIK (up to --limit).
3. Sets inception_date to dateOfOrganization (preferred) or the earliest
   known filing date.
4. Records provenance as a fund_profile_snapshot row (type='sec_edgar_inception').
5. Writes only where inception_date IS NULL (never overwrites).
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.db.session import SessionLocal
from app.models.schema import Fund, FundProfileSnapshot, Source

LOGGER = logging.getLogger("enrich_inception_dates")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

EDGAR_SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
SOURCE_ID = "sec_edgar_submissions"
SOURCE_NAME = "SEC EDGAR Company Submissions API"
SOURCE_URL_BASE = "https://data.sec.gov/submissions/"
DELAY = 0.12  # EDGAR politely requests ≤10 req/s


def _ensure_source(session) -> None:
    stmt = pg_insert(Source).values(
        source_id=SOURCE_ID,
        source_name=SOURCE_NAME,
        country_code="US",
        organization="SEC EDGAR",
        endpoint_url=SOURCE_URL_BASE,
        verification_status="Official",
        integration_status="Active",
        license_status="Public",
    ).on_conflict_do_nothing()
    session.execute(stmt)
    session.commit()


def _fetch(url: str) -> dict | None:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "FundFlow research/1.0 contact@fundflow.example",
            "Accept": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.load(resp)
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        LOGGER.warning("EDGAR fetch failed %s: %s", url, exc)
        return None


def _parse_date(text: str | None) -> date | None:
    if not text:
        return None
    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(text.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def _earliest_filing_date(submissions: dict) -> date | None:
    """Return the earliest effectiveDate across all filings in the submission."""
    filings = submissions.get("filings", {}).get("recent", {})
    dates = filings.get("filingDate") or []
    parsed = [d for d in (_parse_date(s) for s in dates) if d]
    return min(parsed) if parsed else None


def main(limit: int = 500, dry_run: bool = False) -> None:
    with SessionLocal() as session:
        _ensure_source(session)

        # Select funds missing inception_date that have a CIK
        candidates = session.execute(
            select(Fund)
            .where(
                Fund.domicile_country == "US",
                Fund.inception_date.is_(None),
                Fund.sec_cik.isnot(None),
                Fund.sec_cik != "",
            )
            .order_by(Fund.id)
            .limit(limit)
        ).scalars().all()

    LOGGER.info("Candidates with missing inception_date and known CIK: %d", len(candidates))

    updated = 0
    errors = 0
    skipped = 0

    for fund in candidates:
        cik_raw = (fund.sec_cik or "").strip()
        if not cik_raw:
            skipped += 1
            continue
        cik_padded = cik_raw.zfill(10)
        url = EDGAR_SUBMISSIONS_URL.format(cik=cik_padded)

        data = _fetch(url)
        time.sleep(DELAY)
        if not data:
            errors += 1
            continue

        # Try dateOfOrganization first, then oldest filing date
        inception = _parse_date(
            (data.get("registrantInfo") or {}).get("dateOfOrganization")
        ) or _earliest_filing_date(data)

        if inception is None:
            skipped += 1
            continue

        LOGGER.info("Fund id=%d ticker=%s CIK=%s inception=%s", fund.id, fund.ticker, cik_raw, inception)

        if dry_run:
            updated += 1
            continue

        with SessionLocal() as session:
            session.execute(
                update(Fund)
                .where(Fund.id == fund.id, Fund.inception_date.is_(None))
                .values(inception_date=inception)
            )
            # Store provenance snapshot
            import hashlib as _hashlib
            snap_key = _hashlib.md5(f"{fund.id}:sec_edgar_inception".encode()).hexdigest()[:64]
            snap_stmt = pg_insert(FundProfileSnapshot).values(
                fund_id=fund.id,
                source_id=SOURCE_ID,
                dataset="sec_edgar_inception",
                source_report_date=inception,
                snapshot_key=snap_key,
                payload={
                    "inception_date": inception.isoformat(),
                    "cik": cik_raw,
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                },
                source_url=url,
            ).on_conflict_do_nothing()
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
    import json as _json
    print(_json.dumps(summary, indent=2))
    LOGGER.info("Done: %s", summary)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich US fund inception dates from SEC EDGAR submissions")
    parser.add_argument("--limit", type=int, default=500, help="Max funds to process (default 500)")
    parser.add_argument("--dry-run", action="store_true", help="Report without writing")
    args = parser.parse_args()
    main(limit=args.limit, dry_run=args.dry_run)
