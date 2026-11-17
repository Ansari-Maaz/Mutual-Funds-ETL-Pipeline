"""Report country-by-country source-backed coverage for Twelve Data MF fields.

Read-only. Counts stored records; it does not assert that FundFlow and Twelve
Data define a field identically or that source coverage is complete.
"""
from __future__ import annotations

import argparse
import csv
import json
from datetime import date, datetime, timezone
from pathlib import Path

from sqlalchemy import text

from app.db.session import engine

ROOT = Path(__file__).resolve().parents[1]

QUERY = text("""
WITH fund_base AS (
  SELECT f.id,f.domicile_country AS country,f.ticker,f.isin,f.sec_cik,
         f.holdings_report_date
  FROM funds f
), profile AS (
  SELECT p.fund_id,
    bool_or(p.dataset='summary') AS has_summary,
    bool_or(p.dataset='performance') AS has_performance,
    bool_or(p.dataset='risk') AS has_risk,
    bool_or(p.dataset='ratings') AS has_ratings,
    bool_or(p.dataset='composition') AS has_composition,
    bool_or(p.dataset='purchase_info') AS has_purchase_info,
    bool_or(p.dataset='sustainability') AS has_sustainability,
    bool_or(p.dataset='expense_ratio_history') AS has_expense_ratio,
    bool_or(p.dataset='yields') AS has_yield,
    bool_or(p.dataset='aum_history') AS has_aum,
    bool_or(p.dataset='identifiers' AND nullif(p.payload->>'cusip','') IS NOT NULL)
      OR bool_or(p.dataset='summary' AND nullif(p.payload->>'cusip','') IS NOT NULL) AS has_cusip
  FROM fund_profile_snapshots p GROUP BY p.fund_id
), nav AS (
  SELECT n.fund_id,count(*)::int AS nav_records,max(n.valuation_date) AS latest_nav
  FROM nav_observations n GROUP BY n.fund_id
)
SELECT COALESCE(f.country,'??') AS country,
  count(*)::int AS funds,
  count(*) FILTER (WHERE nullif(f.ticker,'') IS NOT NULL)::int AS with_ticker,
  count(*) FILTER (WHERE nullif(f.isin,'') IS NOT NULL)::int AS with_isin,
  count(*) FILTER (WHERE nullif(f.sec_cik,'') IS NOT NULL)::int AS with_cik,
  count(*) FILTER (WHERE p.has_cusip)::int AS with_cusip,
  count(*) FILTER (WHERE n.nav_records>0)::int AS with_nav,
  COALESCE(sum(n.nav_records),0)::int AS nav_records,
  max(n.latest_nav)::text AS latest_nav_date,
  count(*) FILTER (WHERE f.holdings_report_date IS NOT NULL)::int AS with_holdings,
  max(f.holdings_report_date)::text AS latest_holdings_date,
  count(*) FILTER (WHERE p.has_summary)::int AS with_summary,
  count(*) FILTER (WHERE p.has_performance)::int AS with_performance,
  count(*) FILTER (WHERE p.has_risk)::int AS with_risk,
  count(*) FILTER (WHERE p.has_ratings)::int AS with_ratings,
  count(*) FILTER (WHERE p.has_composition)::int AS with_composition_snapshot,
  count(*) FILTER (WHERE p.has_purchase_info)::int AS with_purchase_info,
  count(*) FILTER (WHERE p.has_sustainability)::int AS with_sustainability,
  count(*) FILTER (WHERE p.has_expense_ratio)::int AS with_expense_ratio,
  count(*) FILTER (WHERE p.has_yield)::int AS with_yield,
  count(*) FILTER (WHERE p.has_aum)::int AS with_aum
FROM fund_base f
LEFT JOIN profile p ON p.fund_id=f.id
LEFT JOIN nav n ON n.fund_id=f.id
GROUP BY COALESCE(f.country,'??')
ORDER BY funds DESC,country
""")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'reports')
    args = parser.parse_args()
    with engine.connect() as connection:
        rows = [dict(row) for row in connection.execute(QUERY).mappings()]
    generated_at = datetime.now(timezone.utc).isoformat()
    report = {
        'generated_at': generated_at,
        'as_of_date': date.today().isoformat(),
        'read_only': True,
        'interpretation': 'A stored record indicates presence only. It does not establish exact equivalence to Twelve Data, compatible definitions, fresh valuation dates, or full source coverage.',
        'countries': rows,
        'totals': {key: sum(int(row.get(key) or 0) for row in rows) for key in rows[0] if key not in ('country','latest_nav_date','latest_holdings_date')} if rows else {},
        'latest_nav_date': max((row['latest_nav_date'] for row in rows if row['latest_nav_date']), default=None),
        'latest_holdings_date': max((row['latest_holdings_date'] for row in rows if row['latest_holdings_date']), default=None),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = f'twelvedata_field_coverage_{date.today().isoformat()}'
    json_path = args.output_dir / f'{stem}.json'
    csv_path = args.output_dir / f'{stem}.csv'
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    if rows:
        with csv_path.open('w', newline='', encoding='utf-8') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
    print(json.dumps({'json_report': str(json_path), 'csv_report': str(csv_path), 'countries': len(rows), 'funds': report['totals'].get('funds', 0), 'latest_nav_date': report['latest_nav_date'], 'latest_holdings_date': report['latest_holdings_date']}, indent=2))


if __name__ == '__main__':
    main()
