"""Audit US fund reference-field coverage and classify every missing value.

Read-only. For each US fund record this reports whether the identity and
enrichment fields are populated, the provider, and the official source that can
supply the missing value. It complements ``audit_us_fund_gaps.py`` (NAV and
portfolio holdings) with the reference fields clients see on a fund page.

Outputs under ``reports/``:
* ``us_field_gaps.csv``          - one row per US fund with missing-field flags
* ``us_field_gaps_summary.json`` - counts, provider and action breakdowns
* ``us_field_gaps_summary.md``   - human-readable summary
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import text

from app.db.session import SessionLocal

DEFAULT_REPORTS = ROOT / "reports"

FIELDS = ["ticker", "isin", "category", "inception_date", "manager", "administrator", "net_assets"]

# Which official dataset can supply a missing value, and what the next action is.
FIELD_SOURCES: dict[str, dict[str, str]] = {
    "ticker": {
        "source": "SEC company_tickers_mf.json, N-1A TradingSymbol/scn.tsv, N-CSR TradingSymbol",
        "action": "run enrich-us-funds --tickers and sync-sec-rr-profiles",
    },
    "isin": {
        "source": "SEC N-PORT holding identifiers with CUSIP/ISIN check-digit validation",
        "action": "run enrich-us-funds --isins (only classes that appear as another fund's holding)",
    },
    "category": {
        "source": "No official investment-style taxonomy; N-CEN flags are exposed as classification",
        "action": "leave null unless an issuer publishes a category; run enrich-us-fund-categories",
    },
    "inception_date": {
        "source": "SEC N-1A prospectus XBRL PerfInceptionDate / N-CSR tailored shareholder report",
        "action": "run sync-sec-rr-profiles and sync-sec-ncsr-tsr",
    },
    "manager": {
        "source": "SEC Form N-CEN ADVISER table (primary adviser)",
        "action": "run sync-sec-ncen-bulk",
    },
    "administrator": {
        "source": "SEC Form N-CEN ADMIN table",
        "action": "run sync-sec-ncen-bulk",
    },
    "net_assets": {
        "source": "SEC N-PORT quarterly bulk NET_ASSETS; N-CEN and N-CSR series net assets",
        "action": "run sync-sec-nport-bulk, sync-sec-ncen-bulk and sync-sec-ncsr-tsr",
    },
}

QUERY = text("""
SELECT f.id, f.ticker, f.isin, f.category, f.inception_date,
       f.manager, f.administrator, f.net_assets,
       f.provider, f.name, f.sec_series_id, f.sec_cik,
       COALESCE(trim(f.ticker),'') <> '' AS has_ticker,
       COALESCE(trim(f.isin),'') <> '' AS has_isin,
       COALESCE(trim(f.category),'') <> '' AS has_category,
       f.inception_date IS NOT NULL AS has_inception_date,
       COALESCE(trim(f.manager),'') <> '' AS has_manager,
       COALESCE(trim(f.administrator),'') <> '' AS has_administrator,
       f.net_assets IS NOT NULL AS has_net_assets
FROM funds f
WHERE f.domicile_country = 'US'
ORDER BY f.id
""")


def collect_rows() -> list[dict[str, Any]]:
    with SessionLocal() as session:
        return [dict(row._mapping) for row in session.execute(QUERY)]


def missing_fields(row: dict[str, Any]) -> list[str]:
    return [field for field in FIELDS if not row.get(f"has_{field}")]


def describe(row: dict[str, Any]) -> dict[str, Any]:
    missing = missing_fields(row)
    return {
        "fund_id": row["id"],
        "ticker": row.get("ticker") or "",
        "name": row.get("name") or "",
        "provider": row.get("provider") or "",
        "sec_series_id": row.get("sec_series_id") or "",
        "sec_cik": row.get("sec_cik") or "",
        "missing_count": len(missing),
        "missing_fields": ";".join(missing),
        "next_official_sources": " | ".join(
            sorted({FIELD_SOURCES[field]["source"] for field in missing})),
        "next_actions": " | ".join(
            sorted({FIELD_SOURCES[field]["action"] for field in missing})),
        **{f"has_{field}": bool(row.get(f"has_{field}")) for field in FIELDS},
    }


CSV_COLUMNS = [
    "fund_id", "ticker", "name", "provider", "sec_series_id", "sec_cik",
    "missing_count", "missing_fields", "next_official_sources", "next_actions",
    *[f"has_{field}" for field in FIELDS],
]


def summarize(rows: list[dict[str, Any]], described: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    field_counts = {field: sum(1 for row in rows if not row.get(f"has_{field}")) for field in FIELDS}
    missing_counts = Counter(item["missing_count"] for item in described)
    by_field_reason: dict[str, int] = {}
    for field in FIELDS:
        by_field_reason[field] = field_counts[field]

    provider_buckets: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"funds": 0, "missing_by_field": Counter()})
    for row in rows:
        bucket = provider_buckets[row.get("provider") or "(unknown)"]
        bucket["funds"] += 1
        for field in FIELDS:
            if not row.get(f"has_{field}"):
                bucket["missing_by_field"][field] += 1
    top_providers = sorted(
        (
            {
                "provider": provider,
                "funds": bucket["funds"],
                "missing_total": sum(bucket["missing_by_field"].values()),
                "missing_by_field": dict(bucket["missing_by_field"].most_common()),
            }
            for provider, bucket in provider_buckets.items()
            if bucket["missing_by_field"]
        ),
        key=lambda item: item["missing_total"], reverse=True)[:30]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "country": "US",
        "funds": total,
        "field_completeness": {
            field: {
                "present": total - field_counts[field],
                "missing": field_counts[field],
                "percent_complete": round(100 * (total - field_counts[field]) / total, 2) if total else 0,
                "official_source": FIELD_SOURCES[field]["source"],
                "action": FIELD_SOURCES[field]["action"],
            }
            for field in FIELDS
        },
        "funds_by_missing_field_count": dict(sorted(missing_counts.items())),
        "top_providers_by_missing_fields": top_providers,
    }


def render_markdown(summary: dict[str, Any]) -> str:
    lines = [
        "# U.S. fund reference-field gap audit",
        "",
        f"Generated: {summary['generated_at']}",
        "",
        "## Completeness by field",
        "",
        "| Field | Present | Missing | Complete | Official source | Action |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for field, info in summary["field_completeness"].items():
        lines.append(
            f"| `{field}` | {info['present']:,} | {info['missing']:,} | "
            f"{info['percent_complete']}% | {info['official_source']} | {info['action']} |")
    lines += ["", "## Records by number of missing fields", "",
              "| Missing fields | Funds |", "| ---: | ---: |"]
    lines += [f"| {count} | {funds:,} |"
              for count, funds in summary["funds_by_missing_field_count"].items()]
    lines += ["", "## Largest providers by missing fields", "",
              "| Provider | Funds | Missing values | Fields |",
              "| --- | ---: | ---: | --- |"]
    for item in summary["top_providers_by_missing_fields"]:
        fields = ", ".join(f"{name}={count}" for name, count in item["missing_by_field"].items())
        lines.append(f"| {item['provider']} | {item['funds']:,} | {item['missing_total']:,} | {fields} |")
    lines += [
        "",
        "The per-fund worklist is `reports/us_field_gaps.csv`. A value is never",
        "inferred: the column names the official dataset that can supply it, and",
        "funds whose publisher does not state a value stay null.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORTS)
    args = parser.parse_args()

    rows = collect_rows()
    described = [describe(row) for row in rows]
    summary = summarize(rows, described)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    with (args.output_dir / "us_field_gaps.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(described)
    (args.output_dir / "us_field_gaps_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n")
    (args.output_dir / "us_field_gaps_summary.md").write_text(render_markdown(summary))
    print(json.dumps({
        "funds": summary["funds"],
        "field_completeness": summary["field_completeness"],
        "funds_by_missing_field_count": summary["funds_by_missing_field_count"],
    }, indent=2))


if __name__ == "__main__":
    main()
