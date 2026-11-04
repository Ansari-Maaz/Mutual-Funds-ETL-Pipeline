"""Export field-level status and source-native SEC match keys for every US fund."""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import text

from app.db.session import engine

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
DATASETS = (
    "scheme_master", "nav_history", "aum_history", "expense_ratio_history",
    "money_market_nav_history", "holdings", "performance", "risk_metrics", "yields", "fees", "distributions",
    "official_documents", "official_sources", "twelve_data_parity", "amfi_code",
)
PROFILE_DATASETS = {
    "aum_history": "aum_history",
    "expense_ratio_history": "expense_ratio_history",
    "performance": "performance",
    "risk_metrics": "risk",
    "yields": "yields",
    "fees": "fees",
    "distributions": "distributions",
    "official_documents": "official_documents",
    "official_sources": "summary",
    "money_market_nav_history": "nav_history",
}
MASTER_FIELDS = (
    "name", "legal_name", "ticker", "provider", "fund_family", "category", "fund_type",
    "share_class", "plan", "distribution_option", "currency", "isin", "cusip",
    "sec_cik", "sec_series_id", "inception_date", "benchmark", "manager", "co_managers",
    "administrator", "domicile", "exchange", "mic_code", "exchange_timezone",
    "investment_objective", "investment_strategy", "status", "official_url",
    "factsheet_url", "prospectus_url",
)
MASTER_FIELD_ALIASES = {
    "provider": ("provider",), "fund_family": ("fund_family", "family"),
    "category": ("category",), "fund_type": ("instrument_type", "fund_type"),
    "share_class": ("share_class", "shareClass"),
    "plan": ("plan",), "distribution_option": ("distribution_option", "distributionOption"),
    "benchmark": ("benchmark", "benchmark_name"), "manager": ("fund_manager", "manager"),
    "co_managers": ("co_managers", "coManagers"), "exchange": ("exchange",),
    "mic_code": ("mic_code", "micCode"), "exchange_timezone": ("exchange_timezone", "exchangeTimezone"),
    "investment_objective": ("objective", "investment_objective"),
    "investment_strategy": ("investment_strategy", "strategy"),
    "cusip": ("cusip",), "factsheet_url": ("factsheet_url", "fact_sheet_url"),
    "prospectus_url": ("prospectus_url",), "official_url": ("official_url",),
}


def _field_value(row: dict, field: str):
    """Resolve a master field from normalized columns or provider summary data."""
    direct = row.get(field)
    if direct not in (None, ""):
        return direct
    summary = row.get("profile_summary") or {}
    if isinstance(summary, dict):
        for key in MASTER_FIELD_ALIASES.get(field, ()):
            value = summary.get(key)
            if value not in (None, "", [], {}):
                return value
    return None


def _status(row: dict, dataset: str) -> str:
    if dataset == "amfi_code":
        return "not_applicable"
    if dataset == "scheme_master":
        present = sum(_field_value(row, field) not in (None, "", [], {}) for field in MASTER_FIELDS)
        return "available" if present == len(MASTER_FIELDS) else "partially_available" if present else "requires_verification"
    if dataset == "nav_history":
        # Sourcing alone does not establish official NAV equivalence or full history.
        return "partially_available" if row["nav_rows"] else "requires_verification"
    if dataset == "holdings":
        if row["holding_rows"]:
            return "available"
        if row["holdings_status"] == "unavailable":
            return "unavailable"
        return "requires_verification"
    if dataset == "twelve_data_parity":
        return "requires_verification"
    if dataset in PROFILE_DATASETS:
        count = row.get(f"profile_{PROFILE_DATASETS[dataset]}", 0) or 0
        # Snapshot presence is not evidence of complete history. No provider
        # currently supplies a completeness attestation for these datasets.
        return "partially_available" if count else "requires_verification"
    return "requires_verification"


def build_report() -> tuple[list[dict], dict]:
    query = text("""
        SELECT f.id AS fund_id, f.source_id, f.source_fund_id, f.name, f.legal_name, f.ticker, f.provider,
               f.category, f.fund_type, f.currency, f.isin,
               f.inception_date::text AS inception_date, f.sec_cik, f.sec_series_id,
               f.official_url, f.manager, f.administrator, f.domicile_country AS domicile,
               f.status, f.holdings_status,
               latest_summary.summary AS profile_summary,
               COALESCE(latest_summary.summary->>'cusip','') AS cusip,
               COALESCE(latest_summary.summary->>'benchmark','') AS benchmark,
               COALESCE(latest_summary.summary->>'objective','') AS investment_objective,
               COALESCE(nav.nav_rows, 0)::int AS nav_rows,
               COALESCE(nav.nav_source_rows, 0)::int AS nav_source_rows,
               COALESCE(nav.nav_url_rows, 0)::int AS nav_url_rows,
               nav.first_nav_date::text AS first_nav_date,
               nav.latest_nav_date::text AS latest_nav_date,
               COALESCE(holding.holding_rows, 0)::int AS holding_rows,
               holding.first_holding_date::text AS first_holding_date,
               holding.latest_holding_date::text AS latest_holding_date,
               COALESCE(profile.aum_history,0)::int AS profile_aum_history,
               COALESCE(profile.aum_scopes,0)::int AS profile_aum_scopes,
               COALESCE(profile.aum_report_dates,0)::int AS profile_aum_report_dates,
               COALESCE(profile.expense_ratio_history,0)::int AS profile_expense_ratio_history,
               COALESCE(profile.performance,0)::int AS profile_performance,
               COALESCE(profile.risk,0)::int AS profile_risk,
               COALESCE(profile.yields,0)::int AS profile_yields,
               COALESCE(profile.fees,0)::int AS profile_fees,
               COALESCE(profile.distributions,0)::int AS profile_distributions,
               COALESCE(profile.official_documents,0)::int AS profile_official_documents,
               COALESCE(profile.summary,0)::int AS profile_summary
        FROM funds f
        LEFT JOIN LATERAL (
            SELECT count(*) AS nav_rows, count(source_id) AS nav_source_rows,
                   count(source_url) AS nav_url_rows, min(valuation_date) AS first_nav_date,
                   max(valuation_date) AS latest_nav_date
            FROM nav_observations WHERE fund_id=f.id
        ) nav ON true
        LEFT JOIN LATERAL (
            SELECT count(*) AS holding_rows, min(reporting_date) AS first_holding_date,
                   max(reporting_date) AS latest_holding_date
            FROM portfolio_holdings WHERE fund_id=f.id
        ) holding ON true
        LEFT JOIN LATERAL (
            SELECT payload AS summary FROM fund_profile_snapshots
            WHERE fund_id=f.id AND dataset='summary'
            ORDER BY retrieved_at DESC,id DESC LIMIT 1
        ) latest_summary ON true
        LEFT JOIN LATERAL (
            SELECT count(*) FILTER (WHERE dataset='aum_history') AS aum_history,
                   count(DISTINCT COALESCE(payload->>'scope','unspecified')) FILTER (WHERE dataset='aum_history') AS aum_scopes,
                   count(DISTINCT source_report_date) FILTER (WHERE dataset='aum_history') AS aum_report_dates,
                   count(*) FILTER (WHERE dataset='expense_ratio_history') AS expense_ratio_history,
                   count(*) FILTER (WHERE dataset='performance') AS performance,
                   count(*) FILTER (WHERE dataset='risk') AS risk,
                   count(*) FILTER (WHERE dataset='yields') AS yields,
                   count(*) FILTER (WHERE dataset='fees') AS fees,
                   count(*) FILTER (WHERE dataset='distributions') AS distributions,
                   count(*) FILTER (WHERE dataset='official_documents') AS official_documents,
                   count(*) FILTER (WHERE dataset='nav_history') AS nav_history,
                   count(*) FILTER (WHERE dataset='summary') AS summary
            FROM fund_profile_snapshots WHERE fund_id=f.id
        ) profile ON true
        WHERE f.domicile_country='US'
        ORDER BY f.id
    """)
    with engine.connect() as connection:
        rows = [dict(row) for row in connection.execute(query).mappings()]
        nav_source_counts = dict(connection.execute(text("""
            SELECT COALESCE(n.source_id,'unattributed') AS source_id,count(*)::int AS observations
            FROM nav_observations n JOIN funds f ON f.id=n.fund_id
            WHERE f.domicile_country='US'
            GROUP BY n.source_id ORDER BY n.source_id NULLS FIRST
        """)).all())
        us_source_count = connection.execute(text(
            "SELECT count(*) FROM sources WHERE country_code='US'"
        )).scalar_one()
        failed_run_count = connection.execute(text("""
            SELECT count(*) FROM etl_runs r JOIN sources s USING (source_id)
            WHERE s.country_code='US' AND lower(r.status) IN ('failed','error')
        """)).scalar_one()
    output = []
    status_counts = {dataset: Counter() for dataset in DATASETS}
    for row in rows:
        item = {
            "fund_id": row["fund_id"], "ticker": row["ticker"], "name": row["name"],
            "provider": row["provider"], "source_id": row["source_id"],
            "source_fund_id": row["source_fund_id"],
            "sec_cik": row["sec_cik"], "sec_series_id": row["sec_series_id"],
            "sec_class_id": row["source_fund_id"] if row["source_id"] == "sec_open_end_fund_classes" else None,
            "official_profile_url": row["official_url"],
            "nav_rows": row["nav_rows"], "nav_first_date": row["first_nav_date"],
            "nav_rows_with_source_id": row["nav_source_rows"], "nav_rows_with_source_url": row["nav_url_rows"],
            "nav_latest_date": row["latest_nav_date"], "holding_rows": row["holding_rows"],
            "holdings_first_date": row["first_holding_date"], "holdings_latest_date": row["latest_holding_date"],
        }
        for field in MASTER_FIELDS:
            item[f"field_{field}"] = "available" if _field_value(row, field) not in (None, "", [], {}) else "requires_verification"
        for dataset in DATASETS:
            state = _status(row, dataset)
            item[f"status_{dataset}"] = state
            status_counts[dataset][state] += 1
        item["record_status"] = "complete" if all(
            item[f"status_{dataset}"] == "available" or item[f"status_{dataset}"] == "not_applicable"
            for dataset in DATASETS
        ) else "incomplete"
        output.append(item)
    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "country": "US",
        "funds_examined": len(rows),
        "funds_with_ticker": sum(bool(row["ticker"]) for row in rows),
        "funds_with_provider_name": sum(bool(row["provider"]) for row in rows),
        "funds_with_official_url_field": sum(bool(row["official_url"]) for row in rows),
        "funds_with_sec_cik": sum(bool(row["sec_cik"]) for row in rows),
        "funds_with_sec_series_id": sum(bool(row["sec_series_id"]) for row in rows),
        "registered_us_sources": us_source_count,
        "scheme_master_field_coverage": {
            field: sum(_field_value(row, field) not in (None, "", [], {}) for row in rows)
            for field in MASTER_FIELDS
        },
        "funds_with_recorded_extraction_failure": 0,
        "failed_us_etl_runs_in_history": failed_run_count,
        "funds_with_nav_history": sum(row["nav_rows"] > 0 for row in rows),
        "nav_observations": sum(row["nav_rows"] for row in rows),
        "funds_with_sec_money_market_nav_history": sum(row["profile_nav_history"] > 0 for row in rows),
        "sec_money_market_nav_history_snapshots": sum(row["profile_nav_history"] for row in rows),
        "nav_observations_with_source_id": sum(row["nav_source_rows"] for row in rows),
        "nav_observations_with_source_url": sum(row["nav_url_rows"] for row in rows),
        "nav_observations_by_source": nav_source_counts,
        "funds_with_holdings": sum(row["holding_rows"] > 0 for row in rows),
        "holding_observations": sum(row["holding_rows"] for row in rows),
        "funds_with_aum_history": sum(row["profile_aum_history"] > 0 for row in rows),
        "aum_snapshots": sum(row["profile_aum_history"] for row in rows),
        "funds_with_expense_ratio_history": sum(row["profile_expense_ratio_history"] > 0 for row in rows),
        "expense_ratio_snapshots": sum(row["profile_expense_ratio_history"] for row in rows),
        "funds_with_performance_data": sum(row["profile_performance"] > 0 for row in rows),
        "funds_with_risk_metrics": sum(row["profile_risk"] > 0 for row in rows),
        "funds_with_yield_data": sum(row["profile_yields"] > 0 for row in rows),
        "yield_snapshots": sum(row["profile_yields"] for row in rows),
        "funds_with_official_documents": sum(row["profile_official_documents"] > 0 for row in rows),
        "official_document_records": sum(row["profile_official_documents"] for row in rows),
        "funds_with_official_profile_source": sum(row["profile_summary"] > 0 for row in rows),
        "twelve_data_comparisons": 0,
        "twelve_data_matches": 0,
        "twelve_data_mismatches": 0,
        "status_definitions": {
            "available": "At least one source-backed record or field is stored; does not by itself guarantee complete history.",
            "partially_available": "Some data exists, but key fields, provenance, or historical coverage remain incomplete.",
            "unavailable": "An existing connector status explicitly records that the source returned no data.",
            "not_applicable": "The field is specific to another country's system.",
            "requires_verification": "No verified data is stored; do not treat this as a confirmed absence.",
            "extraction_failed": "Reserved for a recorded dataset-level extraction failure; not inferred from a generic ETL failure.",
        },
        "datasets": {name: dict(counts) for name, counts in status_counts.items()},
        "limitations": [
            "NAV history remains partial even when attributed: a price-source URL does not establish official NAV equivalence or complete history.",
            "One profile snapshot does not establish historical completeness.",
            "Twelve Data coverage is not checked without an authorized API key and comparison run.",
            "The report does not claim all provider or SEC filing archives have been searched.",
            "Per-fund extraction failures are not persisted by dataset in the current schema; zero recorded failures must not be read as zero real failures.",
        ],
    }
    return output, summary


def main() -> None:
    records, summary = build_report()
    REPORTS.mkdir(parents=True, exist_ok=True)
    csv_path = REPORTS / "us_fund_completeness.csv"
    json_path = REPORTS / "us_fund_completeness_summary.json"
    if records:
        with csv_path.open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)
    else:
        csv_path.write_text("", encoding="utf-8")
    json_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"funds_examined": summary["funds_examined"], "csv": str(csv_path),
                      "summary": str(json_path), "dataset_status_counts": summary["datasets"]}, indent=2))


if __name__ == "__main__":
    main()
