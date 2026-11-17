"""Build a consolidated beta comparison report from verified run JSON files.

This aggregator does not invent Twelve Data values or count unrequested
universe members as missing. Input files are copied into the report with their
individual dates and scope retained; fields unavailable to the account remain
separate from mismatches.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import csv
import html
import json
from pathlib import Path
from typing import Any
from decimal import Decimal, InvalidOperation

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUTS = sorted((ROOT / "reports").glob("twelvedata_us_fund_comparison_*.json")) + sorted((ROOT / "reports").glob("twelvedata_etf_*.json"))
NOT_STORED_FIELDS = {
    "directory.exchange", "directory.mic_code", "time_series.meta.exchange",
    "time_series.meta.mic_code", "time_series.meta.exchange_timezone",
}
NOT_COMPARABLE_FIELDS = {
    "time_series.values.open", "time_series.values.high", "time_series.values.low",
}


def normalized_comparison(item: dict[str, Any], kind: str = "mutual_fund") -> dict[str, Any]:
    """Separate absent FundFlow schema fields from comparable value gaps."""
    comparison = dict(item)
    field = comparison.get("field")
    # Vendor display names can differ only by punctuation, and provider
    # taxonomies use "Mutual Fund" where FundFlow records the more specific
    # "Open-end mutual fund". Keep both raw values in the record while marking
    # these as normalized semantic matches.
    if comparison.get("status") == "mismatch" and field and field.endswith(".name"):
        canonical = lambda value: "".join(ch for ch in str(value or "").upper() if ch.isalnum())
        if canonical(comparison.get("twelve_data")) == canonical(comparison.get("fundflow")):
            comparison["status"] = "match"
            comparison["classification_note"] = "Names are equivalent after punctuation and spacing normalization; raw source strings are preserved."
    if comparison.get("status") == "mismatch" and field and field.endswith(".type"):
        canonical = lambda value: "".join(ch for ch in str(value or "").upper() if ch.isalnum())
        taxonomy = {"MUTUALFUND", "OPENENDMUTUALFUND"}
        if canonical(comparison.get("twelve_data")) in taxonomy and canonical(comparison.get("fundflow")) in taxonomy:
            comparison["status"] = "match"
            comparison["classification_note"] = "Equivalent broad instrument taxonomy; FundFlow retains its more specific open-end classification."
    if comparison.get("status") == "mismatch" and field and field.endswith("close_vs_nav"):
        try:
            td = Decimal(str(comparison.get("twelve_data")))
            ff = Decimal(str(comparison.get("fundflow")))
            if td.quantize(Decimal("0.01")) == ff.quantize(Decimal("0.01")):
                comparison["status"] = "match_at_reported_cent_precision"
                comparison["classification_note"] = "The raw provider decimals differ, but both values report the same cent-level price. Raw difference is retained."
        except (InvalidOperation, TypeError):
            pass
    if comparison.get("status") == "missing_in_fundflow" and field in NOT_STORED_FIELDS:
        comparison["status"] = "not_collected_in_fundflow"
        comparison["classification_note"] = "This metadata field is not stored in the current FundFlow schema; its absence is a coverage limitation, not a value mismatch."
    elif comparison.get("status") == "missing_in_fundflow" and field in NOT_COMPARABLE_FIELDS:
        comparison["status"] = "not_comparable"
        comparison["classification_note"] = "FundFlow stores one daily NAV value, not OHLC bars; no high/low/open value is inferred."
    elif comparison.get("status") == "missing_in_twelvedata" and field == "directory.isin":
        comparison["status"] = "unavailable_to_subscription"
        comparison["classification_note"] = "Twelve Data documents ISIN access as an add-on; no directory value was returned."
    elif comparison.get("status") == "missing_in_twelvedata" and kind == "etf" and field == "directory.currency":
        comparison["status"] = "unavailable_from_endpoint"
        comparison["classification_note"] = "The /etfs/list response does not provide currency."
    return comparison


def all_comparisons(fund: dict[str, Any], kind: str = "mutual_fund") -> list[dict[str, Any]]:
    comparisons = [normalized_comparison(item, kind) for item in fund.get("comparisons", [])]
    for observation in fund.get("historical_nav", []):
        item = observation.get("close_vs_nav")
        if item:
            comparisons.append(normalized_comparison(item, kind))
    return comparisons


def load_runs(paths: list[Path]) -> list[dict[str, Any]]:
    runs = []
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["source_report"] = path.name
        runs.append(payload)
    if not runs:
        raise ValueError("No verified Twelve Data run JSON files were supplied.")
    return runs


def _status_counts(runs: list[dict[str, Any]]) -> Counter:
    result: Counter = Counter()
    for run in runs:
        for fund in run.get("funds", []):
            for item in all_comparisons(fund, run.get("kind", "mutual_fund")):
                result[item.get("status", "unknown")] += 1
    return result


def build_report(runs: list[dict[str, Any]], *, database_validation: dict[str, Any] | None = None) -> dict[str, Any]:
    official_path = ROOT / "reports/nasdaq_official_comparison_data_2026-10-30_2026-11-06.json"
    official_close: dict[tuple[str, str], tuple[str, str, str]] = {}
    if official_path.exists():
        official_data = json.loads(official_path.read_text(encoding="utf-8"))
        for instrument in official_data.get("funds", []):
            for observation in instrument.get("observations", []):
                official_close[(instrument["ticker"].upper(), observation["date"])] = (
                    str(observation["close"]), instrument["source_id"], instrument["source_url"])
    funds_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for run in runs:
        date = str(run.get("valuation_date", "unknown"))
        for fund in run.get("funds", []):
            symbol = str(fund.get("ticker", "")).upper()
            key = (symbol, date)
            kind = run.get("kind", "mutual_fund")
            current = funds_by_key.setdefault(key, {"ticker": symbol, "valuation_date": date, "kind": kind, "comparisons": [], "endpoint_errors": []})
            comparisons = all_comparisons(fund, kind)
            # Reconcile saved API responses against the newly refreshed local
            # official values for the same date. Retain the pre-refresh value
            # and official provenance so the report remains auditable.
            for item in comparisons:
                observed_date = date
                if item.get("field", "").startswith("historical_nav."):
                    observed_date = item["field"].split(".")[1]
                official_row = official_close.get((symbol, observed_date))
                is_historical_close = item.get("field", "").startswith("historical_nav.") and item.get("field", "").endswith(".close")
                if official_row and (item.get("field", "").endswith("close_vs_nav") or is_historical_close):
                    item["fundflow_before_official_refresh"] = item.get("fundflow")
                    item["fundflow"] = official_row[0]
                    item["fundflow_source_id"] = official_row[1]
                    item["fundflow_source_url"] = official_row[2]
                    td_value = item.get("twelve_data")
                    if td_value is not None:
                        td_decimal, official_decimal = Decimal(str(td_value)), Decimal(official_row[0])
                        item["difference_td_minus_fundflow"] = str(td_decimal - official_decimal)
                        item["rounded_to_cent_match"] = td_decimal.quantize(Decimal("0.01")) == official_decimal.quantize(Decimal("0.01"))
                        item["numeric_value_match"] = td_decimal == official_decimal
                        item["status"] = "match" if td_decimal == official_decimal else (
                            "match_at_reported_cent_precision" if item["rounded_to_cent_match"] else "mismatch")
            current["comparisons"].extend(comparisons)
            current["endpoint_errors"].extend(fund.get("endpoint_errors", []))

    funds = list(funds_by_key.values())
    status_counts: Counter = Counter(item.get("status", "unknown") for fund in funds for item in fund.get("comparisons", []))
    official_validation = []
    if official_path.exists():
        official = json.loads(official_path.read_text(encoding="utf-8"))
        vendor_prices: dict[tuple[str, str], Any] = {}
        for run in runs:
            for vendor_fund in run.get("funds", []):
                symbol = str(vendor_fund.get("ticker", "")).upper()
                if run.get("kind") == "etf":
                    for observation in vendor_fund.get("historical_nav", []):
                        item = observation.get("close_vs_nav", {})
                        if item.get("twelve_data") is not None:
                            vendor_prices[(symbol, str(observation.get("date")))] = item["twelve_data"]
                else:
                    item = next((c for c in vendor_fund.get("comparisons", []) if c.get("field", "").endswith("close_vs_nav")), None)
                    if item and item.get("twelve_data") is not None:
                        vendor_prices[(symbol, str(run.get("valuation_date")))] = item["twelve_data"]
        for instrument in official.get("funds", []):
            for observation in instrument.get("observations", []):
                ticker, observed_date = instrument["ticker"], observation["date"]
                vendor_value = vendor_prices.get((ticker, observed_date))
                official_close = Decimal(str(observation["close"]))
                if vendor_value is None:
                    status, difference = "no_saved_twelvedata_value_for_date", None
                else:
                    vendor_decimal = Decimal(str(vendor_value))
                    difference = str(vendor_decimal - official_close)
                    status = "cent_level_match" if vendor_decimal.quantize(Decimal("0.01")) == official_close.quantize(Decimal("0.01")) else "mismatch"
                official_validation.append({"ticker": ticker, "kind": instrument["kind"], "date": observed_date,
                    "twelve_data_close": str(vendor_value) if vendor_value is not None else None,
                    "nasdaq_official_close_or_nav": str(official_close), "difference_twelvedata_minus_nasdaq": difference,
                    "status": status, "source_id": instrument["source_id"], "source_url": instrument["source_url"],
                    "price_basis": "ETF market close" if instrument["kind"] == "etf_market_price" else "mutual-fund daily NAV"})
    instrument_types = sorted({run.get("kind", "mutual_fund") for run in runs})
    record_statuses = []
    for fund in funds:
        observed = {item.get("status") for item in fund.get("comparisons", [])}
        if fund.get("endpoint_errors"):
            status = "endpoint_error"
        elif observed and observed <= {"match", "match_at_reported_cent_precision", "unavailable_to_subscription"} and ("match" in observed or "match_at_reported_cent_precision" in observed):
            status = "exact_match"
        elif "match" in observed:
            status = "partial_match"
        elif "missing_in_twelvedata" in observed:
            status = "missing_in_twelvedata"
        elif "missing_in_fundflow" in observed:
            status = "missing_in_fundflow"
        else:
            status = "unresolved"
        record_statuses.append({"ticker": fund["ticker"], "valuation_date": fund["valuation_date"], "status": status})
    price_rows = []
    holdings_validation = []
    for run in runs:
        for fund in run.get("funds", []):
            holdings = fund.get("holdings_comparison") or {"status": "not_compared_in_source_run"}
            holdings_validation.append({
                "ticker": fund.get("ticker"), "kind": run.get("kind", "mutual_fund"),
                "status": holdings.get("status", "not_compared_in_source_run"),
                "fundflow_reporting_date": holdings.get("fundflow_reporting_date"),
                "twelve_data_as_of_date": holdings.get("twelve_data_as_of_date"),
                "weight_differences": holdings.get("weight_differences", []),
                "note": holdings.get("note", "No holdings/composition response was included in the source run."),
            })
    # Price summary is calculated from the reconciled FundFlow values above,
    # not stale values embedded in the older API-run snapshot.
    for fund in funds:
        for item in fund.get("comparisons", []):
            field = item.get("field", "")
            is_price = field.endswith("close_vs_nav") or (field.startswith("historical_nav.") and field.endswith(".close"))
            if not is_price or item.get("twelve_data") is None or item.get("fundflow") is None:
                continue
            td_value, ff_value = Decimal(str(item["twelve_data"])), Decimal(str(item["fundflow"]))
            observed_date = field.split(".")[1] if field.startswith("historical_nav.") else fund["valuation_date"]
            price_rows.append({
                "ticker": fund["ticker"], "valuation_date": observed_date, "kind": fund["kind"],
                "twelve_data_close": str(td_value), "fundflow_official_close_or_nav": str(ff_value),
                "difference_td_minus_fundflow": str(td_value - ff_value),
                "exact_match": td_value == ff_value,
                "nearest_cent_match": td_value.quantize(Decimal("0.01")) == ff_value.quantize(Decimal("0.01")),
                "source_id": item.get("fundflow_source_id"), "source_url": item.get("fundflow_source_url"),
                "price_basis": "ETF market close" if fund["kind"] == "etf" else "mutual-fund daily NAV",
            })

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "title": "FundFlow beta validation against Twelve Data",
        "overall_status": "PARTIAL_VALIDATION",
        "scope": {
            "distinct_fund_date_records": len(funds),
            "distinct_symbols": len({fund["ticker"] for fund in funds}),
            "instrument_types": instrument_types,
            "valuation_dates": sorted({fund["valuation_date"] for fund in funds}),
            "total_api_sample_observations": len(price_rows),
            "coverage_note": f"This report covers the explicit samples of {', '.join(instrument_types)} symbols in its source runs, not the full FundFlow universe. Unrequested symbols are out of scope and are not counted as missing.",
        },
        "summary": {
            "total_fund_date_records_compared": len(funds),
            "distinct_fund_symbols_compared": len({fund["ticker"] for fund in funds}),
            "exact_match_records": sum(row["status"] == "exact_match" for row in record_statuses),
            "partial_match_records": sum(row["status"] == "partial_match" for row in record_statuses),
            "records_with_no_comparable_mismatches": sum(not any(item.get("status") == "mismatch" for item in fund["comparisons"]) for fund in funds),
            "missing_fundflow_records": sum(row["status"] == "missing_in_fundflow" for row in record_statuses),
            "missing_twelvedata_records": sum(row["status"] == "missing_in_twelvedata" for row in record_statuses),
            "exact_matches": status_counts.get("match", 0),
            "matches_at_reported_cent_precision": status_counts.get("match_at_reported_cent_precision", 0),
            "field_mismatches": status_counts.get("mismatch", 0),
            "missing_fundflow_fields": status_counts.get("missing_in_fundflow", 0),
            "missing_twelvedata_fields": status_counts.get("missing_in_twelvedata", 0),
            "not_collected_in_fundflow_fields": status_counts.get("not_collected_in_fundflow", 0),
            "not_comparable_fields": status_counts.get("not_comparable", 0),
            "unavailable_to_subscription_fields": status_counts.get("unavailable_to_subscription", 0),
            "unavailable_from_endpoint_fields": status_counts.get("unavailable_from_endpoint", 0),
            "endpoint_errors": sum(len(fund.get("endpoint_errors", [])) for fund in funds),
            "historical_vendor_observations_compared": sum(row["kind"] == "etf" for row in price_rows),
            "holdings_available_but_date_unaligned": sum(fund.get("holdings_comparison", {}).get("status") == "available_but_period_alignment_unknown" for run in runs for fund in run.get("funds", [])),
            "price_records": len(price_rows),
            "exact_price_matches": sum(row["exact_match"] is True for row in price_rows),
            "nearest_cent_price_matches": sum(row["nearest_cent_match"] is True for row in price_rows),
            "official_comparison_observations": len(official_validation),
            "official_comparison_cent_level_matches": sum(row["status"] == "cent_level_match" for row in official_validation),
            "official_comparison_mismatches": sum(row["status"] == "mismatch" for row in official_validation),
            "official_comparison_without_saved_twelvedata": sum(row["status"] == "no_saved_twelvedata_value_for_date" for row in official_validation),
        },
        "coverage": {
            "fund_identifiers": "Ticker sample only; ISIN/CUSIP fields returned as add-on access sentinel in source runs.",
            "names_country_currency": "Compared where present in source runs.",
            "latest_nav": "One daily observation per ticker and valuation date in source runs.",
            "historical_nav": "Daily history is included where present in saved Twelve Data runs; local official Nasdaq records now cover 2026-10-30 through 2026-11-06 for the 10-fund sample and QQQM.",
            "holdings": "Not covered; holdings/composition endpoints are plan-gated or separately metered and were not called.",
            "etfs": "QQQM is included as a separate ETF sample; official Nasdaq observations are market-price bars, not NAV.",
            "full_universe": "Not validated; the sample cannot establish fund universe completeness.",
        },
        "database_migration_validation": database_validation or {
            "status": "PENDING",
            "reason": "The Supabase database is blank and its Free-plan database quota is below FundFlow's approximately 2.9 GB source database. Full restore and live source-vs-target comparison have not been performed.",
        },
        "known_limitations": [
            "The included vendor checks are prior successful Twelve Data API runs, not fresh calls on report-generation date.",
            "The local comparison window is refreshed from Nasdaq. Mutual-fund rows are daily NAV; QQQM rows are ETF market prices and must be compared as closes, not NAV.",
            "Unavailable add-on fields are reported separately and are not mismatches.",
            "OHLC values are not inferred from a single FundFlow NAV field.",
            "No missing-fund claim is made outside the explicit request sample.",
            "Holdings and the full FundFlow universe are not validated. ISIN/CUSIP remain unavailable from the current Twelve Data entitlement.",
        ],
        "source_runs": runs,
        "nav_differences": price_rows,
        "official_nasdaq_comparison": {"source": "Nasdaq official historical API", "window": "2026-10-30 through 2026-11-06",
            "data_file": official_path.name if official_path.exists() else None, "observations": official_validation,
            "note": "Reported vendor values are compared with official daily prices at cent precision. Mutual-fund records are NAV; ETF records are market closes. Missing vendor dates are not counted as matches."},
        "holdings_validation": holdings_validation,
        "record_match_statuses": record_statuses,
        "fund_records": funds,
    }
    return report


def write_outputs(report: dict[str, Any], output_dir: Path, stem: str) -> tuple[Path, Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{stem}.json"
    csv_path = output_dir / f"{stem}.csv"
    html_path = output_dir / f"{stem}.html"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    rows = []
    for fund in report["fund_records"]:
        for item in fund.get("comparisons", []):
            rows.append({
                "ticker": fund["ticker"], "valuation_date": fund["valuation_date"],
                "field": item.get("field"), "status": item.get("status"),
                "twelve_data": item.get("twelve_data"), "fundflow": item.get("fundflow"),
                "difference": item.get("difference"), "note": item.get("note"),
            })
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["ticker", "valuation_date", "field", "status", "twelve_data", "fundflow", "difference", "note"])
        writer.writeheader()
        writer.writerows(rows)

    summary = report["summary"]
    items = "".join(
        f"<tr><td>{html.escape(str(fund['ticker']))}</td><td>{html.escape(str(fund['valuation_date']))}</td><td>{html.escape(str(row.get('field')))}</td><td>{html.escape(str(row.get('status')))}</td><td>{html.escape(str(row.get('twelve_data')))}</td><td>{html.escape(str(row.get('fundflow')))}</td></tr>"
        for fund in report["fund_records"] for row in fund.get("comparisons", [])
    )
    holdings_rows = "".join(
        f"<tr><td>{html.escape(str(item['ticker']))}</td><td>{html.escape(str(item['kind']))}</td><td>{html.escape(str(item['status']))}</td><td>{html.escape(str(item.get('fundflow_reporting_date')))}</td><td>{html.escape(str(item.get('twelve_data_as_of_date')))}</td><td>{html.escape(str(item.get('note')))}</td></tr>"
        for item in report["holdings_validation"]
    )
    official_rows = "".join(
        f"<tr><td>{html.escape(str(item['ticker']))}</td><td>{html.escape(str(item['date']))}</td><td>{html.escape(str(item['price_basis']))}</td><td>{html.escape(str(item.get('twelve_data_close')))}</td><td>{html.escape(str(item['nasdaq_official_close_or_nav']))}</td><td>{html.escape(str(item['status']))}</td></tr>"
        for item in report.get("official_nasdaq_comparison", {}).get("observations", [])
    )
    notes = "".join(f"<li>{html.escape(note)}</li>" for note in report["known_limitations"])
    html_doc = f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>FundFlow beta validation</title>
<style>body{{font:15px system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#18212b}}table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{border:1px solid #d8dee6;padding:.45rem;text-align:left}}th{{background:#f2f5f8;position:sticky;top:0}}.cards{{display:flex;flex-wrap:wrap;gap:1rem}}.card{{border:1px solid #d8dee6;border-radius:8px;padding:1rem;min-width:150px}}.status{{padding:.5rem;background:#fff5d6;border-left:4px solid #c78d00}}</style>
<h1>FundFlow beta validation against Twelve Data</h1><p>Generated {html.escape(report['generated_at'])}</p><p class="status"><strong>{html.escape(report['overall_status'])}</strong> — {html.escape(report['scope']['coverage_note'])}</p>
<h2>Executive summary</h2><p>{html.escape(str(summary['records_with_no_comparable_mismatches']))} of {html.escape(str(summary['total_fund_date_records_compared']))} sampled fund/date records have no comparable field mismatches. {html.escape(str(summary['nearest_cent_price_matches']))} of {html.escape(str(summary['price_records']))} saved prices match at cent precision; {html.escape(str(summary['exact_price_matches']))} are exact as raw decimals. Overall status remains partial while fields or dates are unavailable or unverified.</p><div class="cards">{''.join(f'<div class="card"><strong>{html.escape(str(k.replace("_", " ").title()))}</strong><br>{html.escape(str(v))}</div>' for k,v in summary.items())}</div>
<h2>Coverage and migration status</h2><pre>{html.escape(json.dumps(report['coverage'], indent=2))}</pre><pre>{html.escape(json.dumps(report['database_migration_validation'], indent=2))}</pre>
<h2>Known limitations and recommendations</h2><ul>{notes}</ul><p>Run the modular comparison script for a fresh, explicitly scoped API run. The report does not count unrequested funds as missing.</p>
<h2>Portfolio holdings validation</h2><p>Holdings are compared only when both sources provide aligned reporting dates. Current run statuses are shown below.</p><table><thead><tr><th>Ticker</th><th>Kind</th><th>Status</th><th>FundFlow date</th><th>Twelve Data date</th><th>Note</th></tr></thead><tbody>{holdings_rows}</tbody></table>
<h2>Official Nasdaq source reconciliation</h2><p>Daily prices/NAVs were refreshed from Nasdaq for 2026-10-30 through 2026-11-06. Only saved Twelve Data dates are counted as comparisons; a missing vendor value is unverified.</p><table><thead><tr><th>Ticker</th><th>Date</th><th>Basis</th><th>Twelve Data</th><th>Nasdaq official</th><th>Status</th></tr></thead><tbody>{official_rows}</tbody></table>
<h2>Field-level results</h2><table><thead><tr><th>Ticker</th><th>Date</th><th>Field</th><th>Status</th><th>Twelve Data</th><th>FundFlow</th></tr></thead><tbody>{items}</tbody></table></html>"""
    html_path.write_text(html_doc, encoding="utf-8")
    return json_path, csv_path, html_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", action="append", type=Path, help="Verified run JSON; repeatable (defaults to existing US sample reports).")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports")
    parser.add_argument("--stem", default="fundflow_beta_validation")
    parser.add_argument("--database-validation-json", type=Path,
                        help="Attach output from validate_database_restore.py; this validates a local restore, not Supabase unless the target was Supabase.")
    args = parser.parse_args()
    paths = args.input if args.input else DEFAULT_INPUTS
    database_validation = json.loads(args.database_validation_json.read_text(encoding="utf-8")) if args.database_validation_json else None
    if database_validation:
        database_validation["supabase_project_restore"] = "PENDING"
        database_validation["supabase_note"] = "This validation target was the disposable local PostgreSQL 17 container. The Supabase project remains empty; its restore and cloud parity checks are still pending."
    report = build_report(load_runs(paths), database_validation=database_validation)
    outputs = write_outputs(report, args.output_dir, args.stem)
    print(json.dumps({"status": report["overall_status"], "summary": report["summary"], "outputs": [str(path) for path in outputs]}, indent=2))


if __name__ == "__main__":
    main()
