"""Audit portfolio-holding field coverage for the latest report per fund.

Read-only: prints one row per holdings field with the number and share of
positions missing it, both across every stored position and across the latest
report date of each fund (the rows a profile page shows by default).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import database_url

FIELDS = (
    "ticker", "isin", "cusip", "quantity", "market_value", "portfolio_weight",
    "unit", "issuer_lei", "issuer_type", "asset_category", "investment_country",
    "is_restricted", "fair_value_level", "derivative_category", "payoff_profile",
    "exchange_rate",
)


def audit() -> dict:
    url = database_url().replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TEMP TABLE latest_report ON COMMIT DROP AS
                SELECT h.fund_id, max(h.reporting_date) AS reporting_date
                FROM portfolio_holdings h GROUP BY 1
            """)
            all_rows: dict[str, dict] = {}
            latest_rows: dict[str, dict] = {}
            cursor.execute("SELECT count(*) FROM portfolio_holdings")
            all_total = cursor.fetchone()[0]
            cursor.execute("""
                SELECT count(*) FROM portfolio_holdings h
                JOIN latest_report l ON l.fund_id = h.fund_id
                  AND l.reporting_date = h.reporting_date
            """)
            latest_total = cursor.fetchone()[0]
            for field in FIELDS:
                cursor.execute(f"SELECT count({field}) FROM portfolio_holdings")
                all_rows[field] = {"present": cursor.fetchone()[0]}
                cursor.execute(f"""
                    SELECT count(h.{field}) FROM portfolio_holdings h
                    JOIN latest_report l ON l.fund_id = h.fund_id
                      AND l.reporting_date = h.reporting_date
                """)
                latest_rows[field] = {"present": cursor.fetchone()[0]}
            for field in ("first_bought_date", "share_change_percentage",
                          "one_year_return", "sector", "trailing_pe"):
                cursor.execute(f"""
                    SELECT count(m.{field}) FROM holding_metrics m
                    JOIN portfolio_holdings h ON h.id = m.holding_id
                    JOIN latest_report l ON l.fund_id = h.fund_id
                      AND l.reporting_date = h.reporting_date
                    WHERE m.data_source = 'sec_nport_derived'
                """)
                latest_rows[field] = {"present": cursor.fetchone()[0]}
                all_rows[field] = {"present": None}

    result = {"all_positions": all_total, "latest_report_positions": latest_total,
              "fields": {}}
    for field in FIELDS:
        result["fields"][field] = {
            "missing_all": all_total - all_rows[field]["present"],
            "present_all_pct": round(100.0 * all_rows[field]["present"] / all_total, 2),
            "missing_latest": latest_total - latest_rows[field]["present"],
            "present_latest_pct": round(100.0 * latest_rows[field]["present"] / latest_total, 2),
        }
    for field in ("first_bought_date", "share_change_percentage",
                  "one_year_return", "sector", "trailing_pe"):
        result["fields"][field] = {
            "present_latest": latest_rows[field]["present"],
            "present_latest_pct": round(100.0 * latest_rows[field]["present"] / latest_total, 2),
        }
    return result


if __name__ == "__main__":
    data = audit()
    out = ROOT / "reports" / "holding_field_gaps.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2) + "\n")
    print(f"Latest-report positions: {data['latest_report_positions']:,}")
    for field, values in data["fields"].items():
        if "missing_latest" in values:
            print(f"  {field:24s} missing {values['missing_latest']:>10,} "
                  f"({values['present_latest_pct']:5.1f}% present)")
        else:
            print(f"  {field:24s} present {values['present_latest']:>10,} "
                  f"({values['present_latest_pct']:5.1f}%)")
    print(f"Wrote {out.relative_to(ROOT)}")
