"""Comprehensive US Mutual Fund Data Completeness & Gap Audit.

Audits every US mutual fund record across:
- Basic fund identification and metadata
- NAV observations and history
- Portfolio holdings and position details
- Profile snapshots and extended attributes

Outputs:
- reports/us_fund_coverage_audit.json
- reports/us_fund_coverage_audit.md
- reports/us_fund_coverage_audit.csv
"""
from __future__ import annotations

import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import psycopg
from app.config import database_url

REPORTS_DIR = ROOT / "reports"
RAW_DIR = ROOT / "data" / "raw" / "united_states"


def run_audit() -> dict[str, Any]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    raw_url = database_url().replace("postgresql+psycopg://", "postgresql://", 1)

    print("Executing comprehensive US fund audit against PostgreSQL...", flush=True)

    with psycopg.connect(raw_url) as conn:
        with conn.cursor() as cur:
            # 1. Total counts and basic field coverage
            cur.execute("""
                SELECT 
                    COUNT(*) AS total_funds,
                    COUNT(name) AS has_name,
                    COUNT(legal_name) AS has_legal_name,
                    COUNT(ticker) AS has_ticker,
                    COUNT(isin) AS has_isin,
                    COUNT(sec_series_id) AS has_series_id,
                    COUNT(sec_cik) AS has_cik,
                    COUNT(category) AS has_category,
                    COUNT(fund_type) AS has_fund_type,
                    COUNT(inception_date) AS has_inception_date,
                    COUNT(status) AS has_status,
                    COUNT(provider) AS has_provider,
                    COUNT(manager) AS has_manager,
                    COUNT(administrator) AS has_administrator,
                    COUNT(net_assets) AS has_net_assets,
                    COUNT(currency) AS has_currency,
                    COUNT(official_url) AS has_official_url,
                    COUNT(holdings_report_date) AS has_holdings_report_date,
                    COUNT(CASE WHEN holdings_status = 'available' THEN 1 END) AS holdings_available,
                    COUNT(CASE WHEN holdings_status = 'unavailable' THEN 1 END) AS holdings_unavailable,
                    COUNT(CASE WHEN holdings_status = 'not_checked' THEN 1 END) AS holdings_not_checked
                FROM funds
                WHERE domicile_country = 'US'
            """)
            basic_row = cur.fetchone()
            basic_cols = [desc[0] for desc in cur.description]
            basic_stats = dict(zip(basic_cols, basic_row))
            total = basic_stats["total_funds"]

            # 2. NAV Coverage
            cur.execute("""
                SELECT 
                    COUNT(DISTINCT f.id) AS funds_with_nav,
                    COUNT(n.id) AS total_nav_observations,
                    COUNT(DISTINCT n.valuation_date) AS distinct_nav_dates,
                    MIN(n.valuation_date)::text AS earliest_nav_date,
                    MAX(n.valuation_date)::text AS latest_nav_date
                FROM funds f
                JOIN nav_observations n ON n.fund_id = f.id
                WHERE f.domicile_country = 'US'
            """)
            nav_stats = dict(zip([d[0] for d in cur.description], cur.fetchone()))

            # NAV by Source
            cur.execute("""
                SELECT COALESCE(n.source_id, 'unattributed') AS source_id, COUNT(DISTINCT f.id) AS funds, COUNT(n.id) AS observations
                FROM funds f
                JOIN nav_observations n ON n.fund_id = f.id
                WHERE f.domicile_country = 'US'
                GROUP BY n.source_id
                ORDER BY funds DESC
            """)
            nav_by_source = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]

            # 3. Portfolio Holdings Coverage
            cur.execute("""
                SELECT 
                    COUNT(DISTINCT f.id) AS funds_with_holdings,
                    COUNT(h.id) AS total_holdings_rows,
                    COUNT(DISTINCT h.reporting_date) AS distinct_report_dates,
                    MIN(h.reporting_date)::text AS earliest_report_date,
                    MAX(h.reporting_date)::text AS latest_report_date,
                    COUNT(h.cusip) AS holdings_with_cusip,
                    COUNT(h.isin) AS holdings_with_isin,
                    COUNT(h.ticker) AS holdings_with_ticker,
                    COUNT(h.market_value) AS holdings_with_market_value,
                    COUNT(h.portfolio_weight) AS holdings_with_weight,
                    COUNT(h.quantity) AS holdings_with_quantity
                FROM funds f
                JOIN portfolio_holdings h ON h.fund_id = f.id
                WHERE f.domicile_country = 'US'
            """)
            holdings_stats = dict(zip([d[0] for d in cur.description], cur.fetchone()))

            # Holdings by Source
            cur.execute("""
                SELECT COALESCE(h.data_source, 'unspecified') AS data_source, COUNT(DISTINCT f.id) AS funds, COUNT(h.id) AS positions
                FROM funds f
                JOIN portfolio_holdings h ON h.fund_id = f.id
                WHERE f.domicile_country = 'US'
                GROUP BY h.data_source
                ORDER BY funds DESC
            """)
            holdings_by_source = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]

            # 4. Profile Snapshots coverage
            cur.execute("""
                SELECT p.dataset, COUNT(DISTINCT p.fund_id) AS funds, COUNT(*) AS snapshots
                FROM fund_profile_snapshots p
                JOIN funds f ON f.id = p.fund_id
                WHERE f.domicile_country = 'US'
                GROUP BY p.dataset
                ORDER BY funds DESC
            """)
            snapshots_by_dataset = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]

            # 5. Overlap stats (both NAV and Holdings, neither, etc.)
            cur.execute("""
                WITH fund_nav AS (
                    SELECT DISTINCT fund_id FROM nav_observations
                ),
                fund_hld AS (
                    SELECT DISTINCT fund_id FROM portfolio_holdings
                )
                SELECT 
                    COUNT(CASE WHEN n.fund_id IS NOT NULL AND h.fund_id IS NOT NULL THEN 1 END) AS both_nav_and_holdings,
                    COUNT(CASE WHEN n.fund_id IS NOT NULL AND h.fund_id IS NULL THEN 1 END) AS nav_only,
                    COUNT(CASE WHEN n.fund_id IS NULL AND h.fund_id IS NOT NULL THEN 1 END) AS holdings_only,
                    COUNT(CASE WHEN n.fund_id IS NULL AND h.fund_id IS NULL THEN 1 END) AS missing_both
                FROM funds f
                LEFT JOIN fund_nav n ON n.fund_id = f.id
                LEFT JOIN fund_hld h ON h.fund_id = f.id
                WHERE f.domicile_country = 'US'
            """)
            overlap_stats = dict(zip([d[0] for d in cur.description], cur.fetchone()))

            # 6. Detailed individual fund gap records
            print("Querying per-fund gap records for export...", flush=True)
            cur.execute("""
                SELECT 
                    f.id AS fund_id,
                    f.source_fund_id AS sec_class_id,
                    f.sec_series_id,
                    f.sec_cik,
                    f.ticker,
                    f.name,
                    f.provider,
                    f.fund_type,
                    f.isin,
                    f.net_assets::text AS net_assets,
                    f.inception_date::text AS inception_date,
                    f.holdings_status,
                    f.holdings_report_date::text AS holdings_report_date,
                    n.nav_count,
                    n.latest_nav_date::text AS latest_nav_date,
                    n.nav_source,
                    h.holding_count,
                    h.latest_holding_date::text AS latest_holding_date,
                    h.holding_source
                FROM funds f
                LEFT JOIN LATERAL (
                    SELECT COUNT(*)::int AS nav_count, MAX(valuation_date) AS latest_nav_date,
                           (SELECT source_id FROM nav_observations x WHERE x.fund_id = f.id ORDER BY valuation_date DESC, id DESC LIMIT 1) AS nav_source
                    FROM nav_observations WHERE fund_id = f.id
                ) n ON true
                LEFT JOIN LATERAL (
                    SELECT COUNT(*)::int AS holding_count, MAX(reporting_date) AS latest_holding_date,
                           (SELECT data_source FROM portfolio_holdings x WHERE x.fund_id = f.id ORDER BY reporting_date DESC, id DESC LIMIT 1) AS holding_source
                    FROM portfolio_holdings WHERE fund_id = f.id
                ) h ON true
                WHERE f.domicile_country = 'US'
                ORDER BY f.id
            """)
            fund_rows = [dict(zip([d[0] for d in cur.description], r)) for r in cur.fetchall()]

    # Compute field completeness percentages
    field_completeness = {
        "Fund Name": {"count": basic_stats["has_name"], "pct": round(basic_stats["has_name"] / total * 100, 2)},
        "Legal Name": {"count": basic_stats["has_legal_name"], "pct": round(basic_stats["has_legal_name"] / total * 100, 2)},
        "Ticker / Symbol": {"count": basic_stats["has_ticker"], "pct": round(basic_stats["has_ticker"] / total * 100, 2)},
        "ISIN": {"count": basic_stats["has_isin"], "pct": round(basic_stats["has_isin"] / total * 100, 2)},
        "SEC Series ID": {"count": basic_stats["has_series_id"], "pct": round(basic_stats["has_series_id"] / total * 100, 2)},
        "SEC CIK": {"count": basic_stats["has_cik"], "pct": round(basic_stats["has_cik"] / total * 100, 2)},
        "Category": {"count": basic_stats["has_category"], "pct": round(basic_stats["has_category"] / total * 100, 2)},
        "Fund Type": {"count": basic_stats["has_fund_type"], "pct": round(basic_stats["has_fund_type"] / total * 100, 2)},
        "Inception Date": {"count": basic_stats["has_inception_date"], "pct": round(basic_stats["has_inception_date"] / total * 100, 2)},
        "Status": {"count": basic_stats["has_status"], "pct": round(basic_stats["has_status"] / total * 100, 2)},
        "Provider / Registrant": {"count": basic_stats["has_provider"], "pct": round(basic_stats["has_provider"] / total * 100, 2)},
        "Manager": {"count": basic_stats["has_manager"], "pct": round(basic_stats["has_manager"] / total * 100, 2)},
        "Administrator": {"count": basic_stats["has_administrator"], "pct": round(basic_stats["has_administrator"] / total * 100, 2)},
        "Net Assets": {"count": basic_stats["has_net_assets"], "pct": round(basic_stats["has_net_assets"] / total * 100, 2)},
        "Currency": {"count": basic_stats["has_currency"], "pct": round(basic_stats["has_currency"] / total * 100, 2)},
        "Official URL": {"count": basic_stats["has_official_url"], "pct": round(basic_stats["has_official_url"] / total * 100, 2)},
        "NAV Coverage": {"count": nav_stats["funds_with_nav"], "pct": round(nav_stats["funds_with_nav"] / total * 100, 2)},
        "Portfolio Holdings Coverage": {"count": holdings_stats["funds_with_holdings"], "pct": round(holdings_stats["funds_with_holdings"] / total * 100, 2)},
        "Both NAV and Holdings": {"count": overlap_stats["both_nav_and_holdings"], "pct": round(overlap_stats["both_nav_and_holdings"] / total * 100, 2)},
    }

    audit_summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_us_funds": total,
        "basic_stats": basic_stats,
        "nav_stats": nav_stats,
        "nav_by_source": nav_by_source,
        "holdings_stats": holdings_stats,
        "holdings_by_source": holdings_by_source,
        "snapshots_by_dataset": snapshots_by_dataset,
        "overlap_stats": overlap_stats,
        "field_completeness": field_completeness,
    }

    # Write JSON summary
    json_path = REPORTS_DIR / "us_fund_coverage_audit.json"
    json_path.write_text(json.dumps(audit_summary, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote JSON audit: {json_path}")

    # Write Markdown summary
    md_lines = [
        "# FundFlow — Comprehensive US Mutual Fund Data Audit",
        "",
        f"**Audit Timestamp:** {audit_summary['generated_at']}  ",
        f"**Universe:** All US Domiciled Funds in PostgreSQL (`domicile_country = 'US'`)  ",
        f"**Total US Funds:** **{total:,}**",
        "",
        "---",
        "",
        "## 1. Field-Level Completeness Report",
        "",
        "| Field | Populated Records | Completeness (%) | Status / Note |",
        "| :--- | ---: | ---: | :--- |",
    ]
    for field_name, stats in field_completeness.items():
        status_note = "Complete" if stats["pct"] == 100 else ("Substantial" if stats["pct"] > 50 else "High Gaps")
        md_lines.append(f"| {field_name} | {stats['count']:,} | {stats['pct']}% | {status_note} |")

    md_lines.extend([
        "",
        "---",
        "",
        "## 2. Core Coverage Dimensions",
        "",
        "| Dimension | Funds | Observations / Rows | Date Span | Sources |",
        "| :--- | ---: | ---: | :--- | :--- |",
        f"| **NAV Observations** | {nav_stats['funds_with_nav']:,} ({round(nav_stats['funds_with_nav']/total*100, 1)}%) | {nav_stats['total_nav_observations']:,} rows | {nav_stats['earliest_nav_date']} to {nav_stats['latest_nav_date']} | {', '.join(s['source_id'] for s in nav_by_source)} |",
        f"| **Portfolio Holdings** | {holdings_stats['funds_with_holdings']:,} ({round(holdings_stats['funds_with_holdings']/total*100, 1)}%) | {holdings_stats['total_holdings_rows']:,} positions | {holdings_stats['earliest_report_date']} to {holdings_stats['latest_report_date']} | {', '.join(s['data_source'] for s in holdings_by_source)} |",
        f"| **Both NAV & Holdings** | {overlap_stats['both_nav_and_holdings']:,} ({round(overlap_stats['both_nav_and_holdings']/total*100, 1)}%) | — | — | Full depth profile |",
        f"| **Holdings Only** | {overlap_stats['holdings_only']:,} ({round(overlap_stats['holdings_only']/total*100, 1)}%) | — | — | Missing daily NAV observations |",
        f"| **NAV Only** | {overlap_stats['nav_only']:,} ({round(overlap_stats['nav_only']/total*100, 1)}%) | — | — | Missing SEC N-PORT portfolio filings |",
        f"| **Missing Both** | {overlap_stats['missing_both']:,} ({round(overlap_stats['missing_both']/total*100, 1)}%) | — | — | Requires targeted research & filing recovery |",
        "",
        "---",
        "",
        "## 3. NAV Source Attribution Breakdown",
        "",
        "| NAV Source | Covered Funds | Total Observations |",
        "| :--- | ---: | ---: |",
    ])
    for s in nav_by_source:
        md_lines.append(f"| `{s['source_id']}` | {s['funds']:,} | {s['observations']:,} |")

    md_lines.extend([
        "",
        "---",
        "",
        "## 4. Portfolio Holdings by Data Source",
        "",
        "| Data Source | Covered Funds | Position Rows |",
        "| :--- | ---: | ---: |",
    ])
    for s in holdings_by_source:
        md_lines.append(f"| `{s['data_source']}` | {s['funds']:,} | {s['positions']:,} |")

    md_path = REPORTS_DIR / "us_fund_coverage_audit.md"
    md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    print(f"Wrote Markdown audit: {md_path}")

    # Write CSV of all funds with gap annotations
    csv_path = REPORTS_DIR / "us_fund_coverage_audit.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "fund_id", "sec_class_id", "sec_series_id", "sec_cik", "ticker", "name", "provider",
            "fund_type", "isin", "net_assets", "inception_date", "holdings_status",
            "holdings_report_date", "nav_count", "latest_nav_date", "nav_source",
            "holding_count", "latest_holding_date", "holding_source",
            "missing_ticker", "missing_nav", "missing_holdings", "missing_net_assets"
        ])
        writer.writeheader()
        for row in fund_rows:
            writer.writerow({
                **row,
                "missing_ticker": not bool(row.get("ticker")),
                "missing_nav": (row.get("nav_count") or 0) == 0,
                "missing_holdings": (row.get("holding_count") or 0) == 0,
                "missing_net_assets": not bool(row.get("net_assets")),
            })
    print(f"Wrote CSV audit: {csv_path} ({len(fund_rows):,} rows)")

    return audit_summary


if __name__ == "__main__":
    run_audit()
