"""Compare Twelve Data's US fund directory, full-data and daily series with FundFlow.

No Twelve Data values are written to FundFlow tables. The report records only
field-level comparison outcomes. The full-data call is opt-in because Twelve
Data currently prices that endpoint at 1,000 credits per request.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import json
import os
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.schema import Fund, FundProfileSnapshot, NavObservation

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
API = "https://api.twelvedata.com"


def compare_field(path: str, expected: Any, actual: Any) -> dict[str, Any]:
    """Report value and JSON type equality without coercing away mismatches."""
    expected_type = type(expected).__name__ if expected is not None else "null"
    actual_type = type(actual).__name__ if actual is not None else "null"
    matches = expected_type == actual_type and expected == actual
    result = {"field": path, "status": "match" if matches else "mismatch",
              "twelve_data_type": expected_type, "fundflow_type": actual_type,
              "twelve_data": expected, "fundflow": actual}
    if not matches and expected is None and actual is not None:
        result["status"] = "missing_in_twelvedata"
    elif not matches and actual is None and expected is not None:
        result["status"] = "missing_in_fundflow"
    return result


def _decimal(value: Any) -> Decimal | None:
    try:
        if value is None or isinstance(value, bool):
            return None
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def compare_numeric(path: str, expected: Any, actual: Any) -> dict[str, Any]:
    """Add numeric equality while retaining the exact serialized values/types."""
    result = compare_field(path, expected, actual)
    left, right = _decimal(expected), _decimal(actual)
    result["numeric_value_match"] = left is not None and right is not None and left == right
    return result


def _single_fund(ticker: str) -> tuple[dict, list[dict]]:
    with SessionLocal() as session:
        funds = session.execute(select(Fund).where(Fund.domicile_country == "US",
            Fund.ticker.is_not(None), Fund.ticker.ilike(ticker)).order_by(Fund.id)).scalars().all()
        if not funds:
            raise LookupError(f"No US FundFlow record has ticker {ticker!r}")
        if len(funds) > 1:
            raise LookupError(f"Ticker {ticker!r} matches {len(funds)} local funds; resolve share class before comparing")
        fund = funds[0]
        navs = session.execute(select(NavObservation).where(NavObservation.fund_id == fund.id)
            .order_by(NavObservation.valuation_date.desc()).limit(100)).scalars().all()
        snapshots = session.execute(select(FundProfileSnapshot).where(FundProfileSnapshot.fund_id == fund.id)
            .order_by(FundProfileSnapshot.source_report_date.desc().nullslast(), FundProfileSnapshot.retrieved_at.desc())).scalars().all()
        local = {"id": fund.id, "name": fund.name, "ticker": fund.ticker,
            "country": fund.domicile_country, "currency": fund.currency,
            "provider": fund.provider, "category": fund.category, "fund_type": fund.fund_type,
            "isin": fund.isin, "inception_date": fund.inception_date.isoformat() if fund.inception_date else None,
            "sec_cik": fund.sec_cik, "sec_series_id": fund.sec_series_id,
            "nav": [{"date": row.valuation_date.isoformat(), "value": str(row.nav),
                     "currency": row.currency, "source_id": row.source_id,
                     "source_url": row.source_url} for row in navs],
            "profile_data": {row.dataset: row.payload for row in snapshots}}
    return local, navs


def _call(client: httpx.Client, endpoint: str, params: dict[str, str]) -> dict:
    response = client.get(f"{API}/{endpoint}", params=params)
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") == "error" or payload.get("code"):
        raise RuntimeError(f"Twelve Data {endpoint} error: {payload.get('message') or payload.get('code')}")
    return payload


def _fund_directory_match(payload: dict, ticker: str) -> dict | None:
    """Find an exact symbol in Twelve Data's documented /funds response."""
    entries = payload.get("result", {}).get("list", [])
    return next((row for row in entries
                 if str(row.get("symbol", "")).strip().upper() == ticker.upper()), None)


def run_comparison(ticker: str, valuation_date: date, *, include_full_data: bool = False) -> dict:
    key = os.getenv("TWELVE_DATA_API_KEY") or os.getenv("TD_KEY")
    if not key:
        raise RuntimeError("Set TWELVE_DATA_API_KEY (or TD_KEY) in your local environment; never paste it into chat.")
    local, nav_rows = _single_fund(ticker)
    params = {"symbol": ticker, "apikey": key}
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(), "ticker": ticker,
        "valuation_date": valuation_date.isoformat(), "fundflow_id": local["id"],
        "twelve_data_full_endpoint_requested": include_full_data,
        "full_endpoint_credit_note": "The /mutual_funds/world endpoint costs 1,000 credits per call." if include_full_data else None,
        "comparisons": [], "endpoint_errors": [],
    }
    with httpx.Client(timeout=30, follow_redirects=True) as client:
        try:
            # /funds is the endpoint used for basic ticker metadata. The
            # separate /mutual_funds/world endpoint is a premium full-data API.
            directory = _call(client, "funds", params)
            match = _fund_directory_match(directory, ticker)
            if not match:
                report["endpoint_errors"].append({"endpoint": "funds", "error": "No exact ticker match returned"})
            else:
                mapping = {"symbol": "ticker", "name": "name", "country": "country",
                           "currency": "currency", "type": "fund_type"}
                for td_field, ff_field in mapping.items():
                    ff_value = "United States" if ff_field == "country" and local["country"] == "US" else local.get(ff_field)
                    report["comparisons"].append(compare_field(f"directory.{td_field}", match.get(td_field), ff_value))
                # Keep vendor directory values visible as parity gaps until
                # independently verified and sourced into FundFlow.
                for field in ("exchange", "mic_code", "isin", "cusip"):
                    ff_field = "isin" if field == "isin" else None
                    report["comparisons"].append(compare_field(
                        f"directory.{field}", match.get(field), local.get(ff_field) if ff_field else None))
        except Exception as error:
            report["endpoint_errors"].append({"endpoint": "funds", "error": f"{type(error).__name__}: {error}"})
        try:
            series = _call(client, "time_series", {**params, "interval": "1day",
                "date": valuation_date.isoformat(), "outputsize": "1"})
            meta = series.get("meta", {})
            values = series.get("values", [])
            observed = next((row for row in values if row.get("datetime") == valuation_date.isoformat()), None)
            local_nav = next((row for row in local["nav"] if row["date"] == valuation_date.isoformat()), None)
            for td_field, ff_value in (("symbol", local["ticker"]), ("currency", local["currency"]),
                                       ("exchange", None), ("mic_code", None),
                                       ("exchange_timezone", None), ("type", local["fund_type"])):
                report["comparisons"].append(compare_field(f"time_series.meta.{td_field}", meta.get(td_field), ff_value))
            if observed is None:
                report["endpoint_errors"].append({"endpoint": "time_series", "error": "No value for requested date"})
            elif local_nav is None:
                report["comparisons"].append(compare_field("time_series.values.datetime", observed.get("datetime"), None))
                report["comparisons"].append(compare_numeric("time_series.values.close", observed.get("close"), None))
            else:
                report["comparisons"].append(compare_field("time_series.values.datetime", observed.get("datetime"), local_nav["date"]))
                report["comparisons"].append(compare_numeric("time_series.values.close_vs_nav", observed.get("close"), local_nav["value"]))
                for field in ("open", "high", "low"):
                    # The current NAV schema stores a single daily valuation, not
                    # OHLC bars. Do not manufacture three prices from one NAV.
                    report["comparisons"].append(compare_field(f"time_series.values.{field}", observed.get(field), None))
        except Exception as error:
            report["endpoint_errors"].append({"endpoint": "time_series", "error": f"{type(error).__name__}: {error}"})
        if include_full_data:
            try:
                full = _call(client, "mutual_funds/world", params)
                report["twelve_data_full_data_fields"] = sorted(_flatten(full))
                report["fundflow_profile_datasets"] = sorted(local["profile_data"])
                report["full_data_note"] = "Full Twelve Data payload was not copied into FundFlow. Compare only authorized fields against official-source snapshots; vendor data remain separate."
            except Exception as error:
                report["endpoint_errors"].append({"endpoint": "mutual_funds/world", "error": f"{type(error).__name__}: {error}"})
    return report


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, dict):
        out = {}
        for key, child in value.items():
            out.update(_flatten(child, f"{prefix}.{key}" if prefix else key))
        return out
    if isinstance(value, list):
        out = {}
        for index, child in enumerate(value):
            out.update(_flatten(child, f"{prefix}[{index}]"))
        return out
    return {prefix: value}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", required=True)
    parser.add_argument("--date", required=True, type=date.fromisoformat)
    parser.add_argument("--include-full-data", action="store_true", help="Call the Ultra/Enterprise-only 1,000-credit full data endpoint")
    args = parser.parse_args()
    result = run_comparison(args.ticker.upper(), args.date, include_full_data=args.include_full_data)
    REPORTS.mkdir(parents=True, exist_ok=True)
    output = REPORTS / f"twelvedata_comparison_{args.ticker.upper()}_{args.date.isoformat()}.json"
    output.write_text(json.dumps(result, indent=2, default=str) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(output), "field_results": len(result["comparisons"]),
        "matches": sum(item["status"] == "match" for item in result["comparisons"]),
        "mismatches": sum(item["status"] == "mismatch" for item in result["comparisons"]),
        "missing_in_fundflow": sum(item["status"] == "missing_in_fundflow" for item in result["comparisons"]),
        "endpoint_errors": result["endpoint_errors"]}, indent=2))


if __name__ == "__main__":
    main()
