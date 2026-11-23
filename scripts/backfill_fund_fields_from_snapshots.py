"""Backfill empty fund columns from already-imported official snapshots.

The ETL stores source-backed facts in ``fund_profile_snapshots`` even when the
matching ``funds`` column was empty at import time.  This script promotes only
those filed values; it never overwrites a non-empty column and never invents a
value.

Sources used:
* ``aum_history`` - SEC Form N-PORT series net assets.
* ``summary`` / ``ncsr_tsr_class`` - SEC N-1A or N-CSR class ticker.

A ticker is applied only when no other U.S. fund already owns it, so a class
symbol cannot silently move between share classes.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal

NET_ASSETS_SQL = text("""
WITH candidates AS (
    SELECT DISTINCT ON (f.id)
           f.id AS fund_id,
           s.payload->>'net_assets' AS net_assets,
           s.source_report_date
    FROM funds f
    JOIN fund_profile_snapshots s
      ON s.fund_id = f.id AND s.dataset = 'aum_history'
    WHERE f.domicile_country = 'US'
      AND f.net_assets IS NULL
      AND s.payload->>'net_assets' ~ '^[0-9]+(\\.[0-9]+)?$'
    ORDER BY f.id, s.source_report_date DESC NULLS LAST, s.id DESC
)
UPDATE funds f
SET net_assets = c.net_assets::numeric,
    net_assets_date = c.source_report_date
FROM candidates c
WHERE f.id = c.fund_id
  AND f.net_assets IS NULL
  AND c.net_assets::numeric > 0
RETURNING f.id
""")

TICKER_SQL = text("""
WITH candidates AS (
    SELECT DISTINCT ON (f.id)
           f.id AS fund_id,
           upper(btrim(s.payload->>'ticker')) AS ticker
    FROM funds f
    JOIN fund_profile_snapshots s
      ON s.fund_id = f.id
     AND s.dataset IN ('summary', 'ncsr_tsr_class')
    WHERE f.domicile_country = 'US'
      AND COALESCE(btrim(f.ticker), '') = ''
      AND NULLIF(s.payload->>'ticker', '') IS NOT NULL
    ORDER BY f.id, s.source_report_date DESC NULLS LAST, s.id DESC
)
UPDATE funds f
SET ticker = c.ticker
FROM candidates c
WHERE f.id = c.fund_id
  AND COALESCE(btrim(f.ticker), '') = ''
  AND c.ticker ~ '^[A-Z][A-Z0-9.-]{0,9}$'
  AND c.ticker NOT IN ('NA', 'N/A', 'NONE', '-', '--')
  AND NOT EXISTS (
      SELECT 1 FROM funds other
      WHERE other.domicile_country = 'US'
        AND other.id <> f.id
        AND upper(btrim(other.ticker)) = c.ticker)
RETURNING f.id
""")


def backfill(*, apply: bool) -> dict[str, int]:
    result = {"net_assets_filled": 0, "tickers_filled": 0, "applied": apply}
    with SessionLocal() as session:
        if apply:
            result["net_assets_filled"] = len(session.execute(NET_ASSETS_SQL).all())
            result["tickers_filled"] = len(session.execute(TICKER_SQL).all())
            session.commit()
        else:
            result["net_assets_candidates"] = session.execute(text(
                "SELECT count(*) FROM funds f WHERE f.domicile_country='US' "
                "AND f.net_assets IS NULL AND EXISTS ("
                "SELECT 1 FROM fund_profile_snapshots s WHERE s.fund_id=f.id "
                "AND s.dataset='aum_history' AND s.payload->>'net_assets' "
                "~ '^[0-9]+(\\.[0-9]+)?$')")).scalar_one()
            result["ticker_candidates"] = session.execute(text(
                "SELECT count(*) FROM funds f WHERE f.domicile_country='US' "
                "AND COALESCE(btrim(f.ticker),'')='' AND EXISTS ("
                "SELECT 1 FROM fund_profile_snapshots s WHERE s.fund_id=f.id "
                "AND s.dataset IN ('summary','ncsr_tsr_class') "
                "AND NULLIF(s.payload->>'ticker','') IS NOT NULL)")).scalar_one()
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Count candidates without writing to the database")
    args = parser.parse_args()
    print(json.dumps(backfill(apply=not args.dry_run), indent=2))


if __name__ == "__main__":
    main()
