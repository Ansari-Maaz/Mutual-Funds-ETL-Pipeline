"""Backfill SEC SIC sector labels on holding metrics after industry resolution.

``sync-sec-nport-metrics`` joins ``security_industry`` while it builds its
staging table.  When new tickers are resolved afterwards, this script refreshes
only the sector (and its stated basis) on the newest metric rows, avoiding a
second full N-PORT metrics rebuild.  It never changes NAV, P/E or returns.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.db.session import SessionLocal

SQL = text("""
WITH latest AS (
    SELECT fund_id, max(reporting_date) AS reporting_date
    FROM portfolio_holdings GROUP BY 1
)
UPDATE holding_metrics m
SET sector = i.sector,
    calculation_basis = CASE
        WHEN m.calculation_basis LIKE '%Sector basis: no SIC match%'
            THEN regexp_replace(
                m.calculation_basis,
                'Sector basis: no SIC match for the filed ticker\\.',
                'Sector basis: SEC SIC ' || COALESCE(i.sic, '')
                    || COALESCE(' - ' || i.sic_description, ''))
        ELSE m.calculation_basis
    END
FROM portfolio_holdings h
JOIN latest l ON l.fund_id = h.fund_id AND l.reporting_date = h.reporting_date
JOIN security_industry i ON i.ticker = upper(btrim(h.ticker))
WHERE m.holding_id = h.id
  AND m.sector IS DISTINCT FROM i.sector
RETURNING m.holding_id
""")


def main() -> None:
    with SessionLocal() as session:
        updated = len(session.execute(SQL).all())
        session.commit()
    print(json.dumps({"sector_rows_updated": updated}, indent=2))


if __name__ == "__main__":
    main()
