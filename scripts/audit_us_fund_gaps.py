"""Audit US NAV and portfolio-holdings coverage and explain every gap.

The script is read-only. It classifies each US fund record that lacks a NAV
observation or official holdings and records the official source that can
resolve the gap, so the report can be used as an adapter backlog.

Outputs (under ``reports/`` by default):
* ``us_fund_gaps.csv`` - one row per US fund with status and gap reason
* ``us_fund_gaps_summary.json`` - aggregate counts and provider breakdown
* ``us_fund_gaps_summary.md`` - human-readable summary
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.db.session import SessionLocal

DEFAULT_REPORTS = ROOT / "reports"
BULK_ROOT = ROOT / "data" / "raw" / "united_states" / "nport_bulk"

# Issuer sites that publish NAV directly. ``status`` is what the adapter
# actually observes today: integrated, blocked by the site, or not built yet.
ISSUER_NAV_SOURCES: list[dict[str, str]] = [
    {
        "match": "vanguard", "organization": "The Vanguard Group",
        "url": "https://investor.vanguard.com/investment-products/mutual-funds/profile/{ticker}",
        "status": "integrated: us_vanguard_fund_products",
    },
    {
        "match": "spdr|state street", "organization": "State Street Global Advisors",
        "url": "https://www.ssga.com/us/en/intermediary/library-content/products/fund-data/etfs/us/navhist-us-en-{ticker}.xlsx",
        "status": "integrated: us_ssga_spdr_navs",
    },
    {
        "match": "american funds|amcap|american balanced|american mutual|american high income|capital world|europacific|growth fund of america|income fund of america|smallcap world|washington mutual|new economy|new perspective|fundamental investors|investment company of america|capital income builder",
        "organization": "Capital Group / American Funds",
        "url": "https://www.capitalgroup.com/individual/investments/fund/{ticker_lower}",
        "status": "integrated: us_capital_group_fund_pages (retail classes with product pages)",
    },
    {
        "match": "ishares|blackrock", "organization": "BlackRock / iShares",
        "url": "https://www.ishares.com/us/products/etf-investments",
        "status": "official product page exposes JSON-LD NAV; ticker-to-product lookup not implemented",
    },
    {
        "match": "fidelity", "organization": "Fidelity Investments",
        "url": "https://fundresearch.fidelity.com/mutual-funds/summary/{ticker}",
        "status": "blocked: site returns 'Fidelity.com is Temporarily Unavailable' to automated requests",
    },
    {
        "match": "john hancock", "organization": "John Hancock Investment Management",
        "url": "https://www.jhinvestments.com/fund/{ticker}",
        "status": "blocked: HTTP 403",
    },
    {
        "match": "massmutual", "organization": "MassMutual",
        "url": "https://www.massmutual.com/funds",
        "status": "blocked: HTTP 403",
    },
    {
        "match": "invesco|aim ", "organization": "Invesco",
        "url": "https://www.invesco.com/us/financial-products/etfs/product-detail?ticker={ticker}",
        "status": "blocked: HTTP 406",
    },
    {
        "match": "schwab", "organization": "Charles Schwab",
        "url": "https://www.schwab.wallst.com/Prospect/Research/mutualfunds/nav.asp?symbol={ticker}",
        "status": "blocked: NAV URL returns HTTP 404",
    },
    {
        "match": "nationwide", "organization": "Nationwide",
        "url": "https://www.nationwide.com/investments/funds",
        "status": "client-side rendered: server HTML contains no NAV values or JSON endpoint",
    },
    {
        "match": "pimco", "organization": "PIMCO",
        "url": "https://www.pimco.com/us/en/investments",
        "status": "issuer page reachable; NAV extraction adapter not implemented",
    },
    {
        "match": "t. rowe", "organization": "T. Rowe Price",
        "url": "https://www.troweprice.com/financial-intermediary/us/en/investments/mutual-funds.html",
        "status": "issuer page reachable; NAV extraction adapter not implemented",
    },
    {
        "match": "morgan stanley", "organization": "Morgan Stanley Investment Management",
        "url": "https://www.morganstanley.com/im/en-us/individual-investor/products.html",
        "status": "issuer page reachable; NAV extraction adapter not implemented",
    },
    {
        "match": "transamerica", "organization": "Transamerica",
        "url": "https://www.transamerica.com/investments/mutual-funds",
        "status": "issuer page reachable; NAV extraction adapter not implemented",
    },
    {
        "match": "alliancebernstein|ab bond|ab cap|ab trust|ab portfolios|ab global|ab large|ab municipal|ab equity|ab fixed|ab relative|ab sustainable|ab discovery|ab core",
        "organization": "AllianceBernstein",
        "url": "https://www.alliancebernstein.com/us/en-us/investments/products/mutual-funds.html",
        "status": "issuer page reachable; NAV extraction adapter not implemented",
    },
    {
        "match": "american century", "organization": "American Century Investments",
        "url": "https://www.americancentury.com/investments/mutual-funds/",
        "status": "issuer page reachable; NAV extraction adapter not implemented",
    },
    {
        "match": "alger", "organization": "Alger",
        "url": "https://www.alger.com/",
        "status": "issuer page reachable; NAV extraction adapter not implemented",
    },
    {
        "match": "allspring", "organization": "Allspring Global Investments",
        "url": "https://www.allspringglobal.com/investments/",
        "status": "issuer page reachable; NAV extraction adapter not implemented",
    },
    {
        "match": "voya", "organization": "Voya Investment Management",
        "url": "https://www.voya.com/",
        "status": "issuer page reachable; NAV extraction adapter not implemented",
    },
    {
        "match": "lord abbett", "organization": "Lord Abbett",
        "url": "https://www.lordabbett.com/en-us/individual-investors.html",
        "status": "issuer page reachable; NAV extraction adapter not implemented",
    },
]


def issuer_source(provider: str) -> dict[str, str] | None:
    provider_lower = (provider or "").lower()
    for entry in ISSUER_NAV_SOURCES:
        for token in entry["match"].split("|"):
            if token.strip() and token.strip() in provider_lower:
                return entry
    return None


def latest_bulk_series(quarter: str | None) -> tuple[str | None, set[str]]:
    """Return the newest extracted SEC N-PORT quarter and its reported series IDs."""
    if quarter:
        candidates = [BULK_ROOT / quarter]
    else:
        candidates = sorted(
            (path for path in BULK_ROOT.iterdir() if path.is_dir() and (path / "FUND_REPORTED_INFO.tsv").exists()),
            reverse=True) if BULK_ROOT.exists() else []
    for directory in candidates:
        info = directory / "FUND_REPORTED_INFO.tsv"
        if not info.exists():
            continue
        series: set[str] = set()
        with info.open("r", encoding="utf-8", errors="replace", newline="") as stream:
            for row in csv.DictReader(stream, delimiter="\t"):
                value = (row.get("SERIES_ID") or "").strip()
                if value:
                    series.add(value)
        return directory.name, series
    return None, set()


def collect_rows() -> list[dict[str, Any]]:
    query = text("""
        SELECT f.id, f.ticker, f.name, f.provider, f.sec_series_id, f.sec_cik,
               f.holdings_status, f.holdings_report_date,
               n.nav_rows, n.latest_nav, n.nav_source,
               h.holding_rows, h.latest_holding, h.holding_source
        FROM funds f
        LEFT JOIN LATERAL (
            SELECT count(*)::int AS nav_rows, max(valuation_date) AS latest_nav,
                   (SELECT source_id FROM nav_observations x
                     WHERE x.fund_id = f.id AND x.nav > 0
                     ORDER BY valuation_date DESC, id DESC LIMIT 1) AS nav_source
            FROM nav_observations i WHERE i.fund_id = f.id AND i.nav > 0
        ) n ON true
        LEFT JOIN LATERAL (
            SELECT count(*)::int AS holding_rows, max(reporting_date) AS latest_holding,
                   (SELECT data_source FROM portfolio_holdings x
                     WHERE x.fund_id = f.id
                     ORDER BY reporting_date DESC, id DESC LIMIT 1) AS holding_source
            FROM portfolio_holdings i WHERE i.fund_id = f.id
        ) h ON true
        WHERE f.domicile_country = 'US'
        ORDER BY f.id
    """)
    with SessionLocal() as session:
        return [dict(row._mapping) for row in session.execute(query)]


def classify(row: dict[str, Any], bulk_quarter: str | None, bulk_series: set[str]) -> dict[str, Any]:
    provider = row.get("provider") or ""
    source = issuer_source(provider)
    has_nav = bool(row.get("nav_rows"))
    has_holdings = bool(row.get("holding_rows"))
    series = row.get("sec_series_id")

    if has_holdings:
        holdings_reason = ""
        holdings_action = ""
    elif not series:
        holdings_reason = "no_sec_series_identifier"
        holdings_action = "SEC N-PORT"
    elif bulk_quarter and series in bulk_series:
        holdings_reason = "latest_n_port_filing_reports_no_positions"
        holdings_action = f"SEC N-PORT {bulk_quarter} bulk data set"
    else:
        holdings_reason = "series_absent_from_latest_n_port_dataset"
        holdings_action = "SEC N-PORT earlier quarters (fund likely stopped filing or merged)"

    if has_nav:
        nav_reason = ""
        nav_action = ""
    elif not row.get("ticker"):
        nav_reason = "no_public_ticker_in_sec_class_snapshot"
        nav_action = (source or {}).get("url", "").replace("{ticker}", "").replace("{ticker_lower}", "").rstrip("/")
    elif source is None:
        nav_reason = "issuer_not_yet_mapped"
        nav_action = ""
    elif source["status"].startswith("integrated"):
        nav_reason = "ticker_not_returned_by_integrated_issuer_adapter"
        nav_action = source["url"].format(ticker=row["ticker"], ticker_lower=row["ticker"].lower())
    elif source["status"].startswith("blocked") or source["status"].startswith("client-side"):
        nav_reason = "issuer_site_does_not_expose_machine_readable_nav"
        nav_action = source["url"].format(ticker=row["ticker"], ticker_lower=row["ticker"].lower())
    else:
        nav_reason = "issuer_adapter_not_implemented"
        nav_action = source["url"].format(ticker=row["ticker"], ticker_lower=row["ticker"].lower())

    return {
        "fund_id": row["id"],
        "ticker": row.get("ticker") or "",
        "name": row.get("name") or "",
        "provider": provider,
        "sec_series_id": series or "",
        "sec_cik": row.get("sec_cik") or "",
        "has_nav": has_nav,
        "nav_rows": row.get("nav_rows") or 0,
        "latest_nav": row.get("latest_nav").isoformat() if row.get("latest_nav") else "",
        "nav_source": row.get("nav_source") or "",
        "has_holdings": has_holdings,
        "holding_rows": row.get("holding_rows") or 0,
        "latest_holding": row.get("latest_holding").isoformat() if row.get("latest_holding") else "",
        "holding_source": row.get("holding_source") or "",
        "gap": ("nav" if not has_nav else "") + ("+holdings" if not has_nav and not has_holdings else ("holdings" if not has_holdings else "")),
        "nav_gap_reason": nav_reason,
        "holdings_gap_reason": holdings_reason,
        "official_nav_source": (source or {}).get("organization", ""),
        "official_nav_url": nav_action,
        "official_nav_status": (source or {}).get("status", ""),
        "official_holdings_source": "U.S. SEC Form N-PORT" if not has_holdings else "",
        "official_holdings_action": holdings_action,
    }


CSV_COLUMNS = [
    "fund_id", "ticker", "name", "provider", "sec_series_id", "sec_cik",
    "has_nav", "nav_rows", "latest_nav", "nav_source",
    "has_holdings", "holding_rows", "latest_holding", "holding_source",
    "gap", "nav_gap_reason", "holdings_gap_reason",
    "official_nav_source", "official_nav_url", "official_nav_status",
    "official_holdings_source", "official_holdings_action",
]


def summarize(rows: list[dict[str, Any]], bulk_quarter: str | None) -> dict[str, Any]:
    total = len(rows)
    with_nav = sum(1 for row in rows if row["has_nav"])
    with_holdings = sum(1 for row in rows if row["has_holdings"])
    both = sum(1 for row in rows if row["has_nav"] and row["has_holdings"])
    neither = sum(1 for row in rows if not row["has_nav"] and not row["has_holdings"])

    nav_reasons = Counter(row["nav_gap_reason"] for row in rows if row["nav_gap_reason"])
    holdings_reasons = Counter(row["holdings_gap_reason"] for row in rows if row["holdings_gap_reason"])
    nav_sources = Counter(row["nav_source"] for row in rows if row["nav_source"])
    holdings_sources = Counter(row["holding_source"] for row in rows if row["holding_source"])

    provider_totals: dict[str, dict[str, int]] = defaultdict(
        lambda: {"funds": 0, "missing_nav": 0, "missing_holdings": 0, "missing_both": 0})
    for row in rows:
        bucket = provider_totals[row["provider"] or "(unknown)"]
        bucket["funds"] += 1
        if not row["has_nav"]:
            bucket["missing_nav"] += 1
        if not row["has_holdings"]:
            bucket["missing_holdings"] += 1
        if not row["has_nav"] and not row["has_holdings"]:
            bucket["missing_both"] += 1
    top_providers = sorted(
        ({"provider": name, **counts} for name, counts in provider_totals.items()
         if counts["missing_nav"] or counts["missing_holdings"]),
        key=lambda item: (item["missing_nav"] + item["missing_holdings"], item["funds"]),
        reverse=True)[:25]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "country": "US",
        "latest_nport_dataset": bulk_quarter,
        "funds": total,
        "with_nav": with_nav,
        "with_holdings": with_holdings,
        "with_nav_and_holdings": both,
        "missing_nav": total - with_nav,
        "missing_holdings": total - with_holdings,
        "missing_both": neither,
        "nav_coverage_percent": round(100 * with_nav / total, 2) if total else 0,
        "holdings_coverage_percent": round(100 * with_holdings / total, 2) if total else 0,
        "complete_coverage_percent": round(100 * both / total, 2) if total else 0,
        "nav_gap_reasons": dict(nav_reasons.most_common()),
        "holdings_gap_reasons": dict(holdings_reasons.most_common()),
        "nav_sources": dict(nav_sources.most_common()),
        "holdings_sources": dict(holdings_sources.most_common()),
        "top_providers_by_gap": top_providers,
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# U.S. fund coverage audit",
        "",
        f"Generated: {summary['generated_at']}",
        f"SEC N-PORT data set inspected: {summary['latest_nport_dataset'] or 'none extracted locally'}",
        "",
        "## Coverage",
        "",
        "| Metric | Funds |",
        "| --- | ---: |",
        f"| U.S. fund records | {summary['funds']:,} |",
        f"| With NAV observations | {summary['with_nav']:,} ({summary['nav_coverage_percent']}%) |",
        f"| With official portfolio holdings | {summary['with_holdings']:,} ({summary['holdings_coverage_percent']}%) |",
        f"| With both | {summary['with_nav_and_holdings']:,} ({summary['complete_coverage_percent']}%) |",
        f"| Missing NAV | {summary['missing_nav']:,} |",
        f"| Missing holdings | {summary['missing_holdings']:,} |",
        f"| Missing both | {summary['missing_both']:,} |",
        "",
        "## Why NAV is missing",
        "",
        "| Reason | Funds |",
        "| --- | ---: |",
    ]
    lines += [f"| `{reason}` | {count:,} |" for reason, count in summary["nav_gap_reasons"].items()]
    lines += ["", "## Why holdings are missing", "", "| Reason | Funds |", "| --- | ---: |"]
    lines += [f"| `{reason}` | {count:,} |" for reason, count in summary["holdings_gap_reasons"].items()]
    lines += ["", "## NAV observations by source", "", "| Source | Funds |", "| --- | ---: |"]
    lines += [f"| `{source or '(unattributed)'}` | {count:,} |" for source, count in summary["nav_sources"].items()]
    lines += ["", "## Holdings by source", "", "| Source | Funds |", "| --- | ---: |"]
    lines += [f"| `{source}` | {count:,} |" for source, count in summary["holdings_sources"].items()]
    lines += ["", "## Largest remaining gaps", "",
              "| Provider | Funds | Missing NAV | Missing holdings | Missing both |",
              "| --- | ---: | ---: | ---: | ---: |"]
    lines += [
        f"| {item['provider']} | {item['funds']:,} | {item['missing_nav']:,} | "
        f"{item['missing_holdings']:,} | {item['missing_both']:,} |"
        for item in summary["top_providers_by_gap"]
    ]
    lines += [
        "",
        "## Official-source constraints observed",
        "",
        "See `docs/US_OFFICIAL_SOURCES.md` for the verified status of every issuer site.",
        "Automated access is blocked or unusable at several large issuers (Fidelity,",
        "John Hancock, MassMutual, Invesco, Charles Schwab); Nationwide renders NAV only",
        "in client-side JavaScript. Those gaps stay empty rather than being filled from a",
        "non-official feed.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quarter", help="SEC N-PORT quarter to inspect, e.g. 2026q3 (default: newest extracted)")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORTS)
    args = parser.parse_args()

    bulk_quarter, bulk_series = latest_bulk_series(args.quarter)
    rows = collect_rows()
    classified = [classify(row, bulk_quarter, bulk_series) for row in rows]
    summary = summarize(classified, bulk_quarter)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "us_fund_gaps.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(classified)
    (args.output_dir / "us_fund_gaps_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n")
    (args.output_dir / "us_fund_gaps_summary.md").write_text(render_markdown(summary))
    print(json.dumps({key: summary[key] for key in (
        "funds", "with_nav", "with_holdings", "missing_nav", "missing_holdings",
        "missing_both", "nav_coverage_percent", "holdings_coverage_percent")}, indent=2))


if __name__ == "__main__":
    main()
