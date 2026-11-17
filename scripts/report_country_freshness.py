"""Report the freshest stored NAV and holdings date for every country.

Read-only. Answers "does each country show its latest data" by listing, per
domicile country, how many funds exist, how many have a NAV or holdings, and the
newest observation/report date in the database.

Usage:
    ./.venv/bin/python scripts/report_country_freshness.py
    ./.venv/bin/python scripts/report_country_freshness.py --json reports/country_freshness.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.db.session import SessionLocal

QUERY = text("""
WITH nav AS (
    SELECT fund_id, max(valuation_date) AS latest_nav
    FROM nav_observations
    GROUP BY fund_id
), holdings AS (
    SELECT fund_id, max(reporting_date) AS latest_holdings
    FROM portfolio_holdings
    GROUP BY fund_id
)
SELECT f.domicile_country AS country,
       count(*) AS funds,
       count(*) FILTER (WHERE nav.latest_nav IS NOT NULL) AS with_nav,
       max(nav.latest_nav)::text AS latest_nav_date,
       count(*) FILTER (WHERE holdings.latest_holdings IS NOT NULL) AS with_holdings,
       max(holdings.latest_holdings)::text AS latest_holdings_date
FROM funds f
LEFT JOIN nav ON nav.fund_id = f.id
LEFT JOIN holdings ON holdings.fund_id = f.id
GROUP BY f.domicile_country
ORDER BY funds DESC, f.domicile_country
""")


def collect() -> list[dict[str, Any]]:
    with SessionLocal() as session:
        return [dict(row._mapping) for row in session.execute(QUERY)]


def render_markdown(rows: list[dict[str, Any]], generated_at: str) -> str:
    lines = [
        "# Country data freshness",
        "",
        f"Generated: {generated_at}",
        "",
        "| Country | Funds | With NAV | Latest NAV | With holdings | Latest holdings |",
        "| --- | ---: | ---: | --- | ---: | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['country']} | {row['funds']:,} | {row['with_nav']:,} | "
            f"{row['latest_nav_date'] or '—'} | {row['with_holdings']:,} | "
            f"{row['latest_holdings_date'] or '—'} |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--json", type=Path, help="Also write the table as JSON here")
    parser.add_argument("--markdown", type=Path, help="Also write the table as Markdown here")
    args = parser.parse_args()

    generated_at = datetime.now(timezone.utc).isoformat()
    rows = collect()
    markdown = render_markdown(rows, generated_at)
    print(markdown)
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"generated_at": generated_at, "countries": rows}, indent=2) + "\n")
    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(markdown)


if __name__ == "__main__":
    main()
