"""Backfill holdings for US funds with no stored portfolio positions.

Most of these are older/dormant share classes whose SEC series stopped filing
before the DERA N-PORT bulk archives begin.  The official fallback is the
individual N-PORT filing on EDGAR: scan up to ten years of each registrant's
filings, keep the newest report per series and write only the filed positions.
No value is invented and existing holdings are never overwritten.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.db.session import SessionLocal
from app.etl.runs import tracked_run
from app.holdings.sec_nport import sync_sec_holdings


def target_ids(limit: int | None) -> list[int]:
    suffix = f" LIMIT {int(limit)}" if limit else ""
    sql = text("""
        SELECT f.id FROM funds f
        LEFT JOIN portfolio_holdings h ON h.fund_id = f.id
        WHERE f.domicile_country = 'US' AND h.fund_id IS NULL
        ORDER BY f.id
    """ + suffix)
    with SessionLocal() as session:
        return [row[0] for row in session.execute(sql).all()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, help="Only test with the first N funds")
    parser.add_argument("--history-days", type=int, default=3650)
    args = parser.parse_args()
    ids = target_ids(args.limit)
    result = tracked_run("sec-nport-holdings-gap", lambda: sync_sec_holdings(
        set(ids), history_days=args.history_days, latest_only=True,
        cache_downloads=True))
    print(json.dumps({"funds_targeted": len(ids), **result}, indent=2, default=str))


if __name__ == "__main__":
    main()
