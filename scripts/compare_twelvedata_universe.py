"""Compare explicitly selected FundFlow mutual funds or ETFs with Twelve Data.

Read-only: this script never imports vendor values into FundFlow. Default work
costs two standard credits per symbol. History costs one additional time-series
request per symbol; optional composition/holdings calls cost 200 credits each.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
import getpass
import json
import logging
import os
from pathlib import Path
import re
import time
from typing import Any

import httpx
from sqlalchemy import func, select

ROOT = Path(__file__).resolve().parents[1]
import sys
sys.path.insert(0, str(ROOT))
from app.db.session import SessionLocal
from app.models.schema import Fund, NavObservation, PortfolioHolding

API = "https://api.twelvedata.com"
LOG = logging.getLogger("fundflow.twelvedata")
COUNTRY_ALIASES = {"US": "UNITED STATES", "USA": "UNITED STATES", "GB": "UNITED KINGDOM", "UK": "UNITED KINGDOM"}
ACCESS_SENTINELS = {"request_access_via_add_ons", "request_access_via_addon", "not_available"}


def _key() -> str:
    value = os.getenv("TWELVE_DATA_API_KEY") or os.getenv("TD_KEY")
    if not value:
        value = getpass.getpass("Twelve Data API key (hidden input): ").strip()
    if not value:
        raise RuntimeError("A Twelve Data API key is required via TWELVE_DATA_API_KEY or hidden prompt.")
    os.environ["TWELVE_DATA_API_KEY"] = value
    return value


def _safe_error(error: Exception) -> str:
    message = str(error)
    for env_name in ("TWELVE_DATA_API_KEY", "TD_KEY"):
        secret = os.getenv(env_name)
        if secret:
            message = message.replace(secret, "[REDACTED]")
    # Never retain a Twelve Data URL because its key is a query parameter.
    message = re.sub(r"https?://\S+", "[request URL redacted]", message)
    return f"{type(error).__name__}: {message}"


def _canonical_text(value: Any) -> str | None:
    if value is None:
        return None
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def _canonical_country(value: Any) -> str | None:
    raw = str(value).strip().upper() if value is not None else ""
    return COUNTRY_ALIASES.get(raw, raw) or None


def _number(value: Any) -> Decimal | None:
    try:
        return Decimal(str(value)) if value is not None and not isinstance(value, bool) else None
    except (InvalidOperation, ValueError):
        return None


def compare(path: str, td: Any, ff: Any, *, rule: str = "exact") -> dict[str, Any]:
    if isinstance(td, str) and td.strip().lower() in ACCESS_SENTINELS:
        return {"field": path, "status": "unavailable_to_subscription", "twelve_data": td,
                "fundflow": ff, "note": "Provider returned an access sentinel, not a value."}
    if td is None and ff is None:
        return {"field": path, "status": "unavailable_from_both", "twelve_data": None, "fundflow": None}
    if td is None:
        return {"field": path, "status": "missing_in_twelvedata", "twelve_data": None, "fundflow": ff}
    if ff is None:
        return {"field": path, "status": "missing_in_fundflow", "twelve_data": td, "fundflow": None}
    if rule == "numeric":
        left, right = _number(td), _number(ff)
        if left is None or right is None:
            equal = str(td) == str(ff)
            difference = None
        else:
            equal = left == right
            difference = str(left - right)
        result = {"field": path, "status": "match" if equal else "mismatch",
                  "twelve_data": td, "fundflow": ff}
        if difference is not None:
            result["difference_td_minus_fundflow"] = difference
            result["nearest_cent_match"] = left.quantize(Decimal("0.01")) == right.quantize(Decimal("0.01"))
        return result
    if rule == "country":
        equal = _canonical_country(td) == _canonical_country(ff)
    elif rule in ("symbol", "isin", "name", "currency"):
        equal = _canonical_text(td) == _canonical_text(ff)
    else:
        equal = td == ff
    return {"field": path, "status": "match" if equal else "mismatch", "twelve_data": td, "fundflow": ff}


def _local_record(symbol: str, kind: str, end_date: date, history_limit: int) -> dict[str, Any] | None:
    with SessionLocal() as session:
        stmt = select(Fund).where(Fund.domicile_country == "US", Fund.ticker.ilike(symbol)).order_by(Fund.id)
        funds = session.execute(stmt).scalars().all()
        if not funds:
            return None
        if len(funds) > 1:
            # For an ETF request prefer records whose canonical type names an ETF,
            # but never choose arbitrarily if the database remains ambiguous.
            if kind == "etf":
                filtered = [f for f in funds if "ETF" in (f.fund_type or "").upper()]
                if len(filtered) == 1:
                    funds = filtered
            if len(funds) != 1:
                raise LookupError(f"{symbol}: {len(funds)} FundFlow ticker rows; provide a unique ticker before comparing")
        fund = funds[0]
        nav_stmt = select(NavObservation).where(NavObservation.fund_id == fund.id,
            NavObservation.valuation_date <= end_date).order_by(NavObservation.valuation_date.desc()).limit(max(history_limit, 1))
        nav_rows = list(session.execute(nav_stmt).scalars())
        latest_holdings = session.execute(select(func.max(PortfolioHolding.reporting_date)).where(
            PortfolioHolding.fund_id == fund.id)).scalar_one_or_none()
        holdings = []
        if latest_holdings:
            holdings = list(session.execute(select(PortfolioHolding).where(
                PortfolioHolding.fund_id == fund.id,
                PortfolioHolding.reporting_date == latest_holdings).order_by(PortfolioHolding.holding_index)).scalars())
        return {
            "id": fund.id, "name": fund.name, "symbol": fund.ticker, "isin": fund.isin,
            "country": fund.domicile_country, "currency": fund.currency,
            "fund_type": fund.fund_type, "provider": fund.provider, "category": fund.category,
            "latest_nav": ({"date": nav_rows[0].valuation_date.isoformat(), "nav": str(nav_rows[0].nav),
                            "currency": nav_rows[0].currency} if nav_rows else None),
            "historical_nav": [{"date": row.valuation_date.isoformat(), "nav": str(row.nav),
                                "currency": row.currency} for row in nav_rows],
            "holdings_report_date": latest_holdings.isoformat() if latest_holdings else None,
            "holdings": [{"symbol": row.ticker, "isin": row.isin, "name": row.security_name,
                          "weight": str(row.portfolio_weight) if row.portfolio_weight is not None else None}
                         for row in holdings],
        }


def _call(client: httpx.Client, endpoint: str, params: dict[str, Any], key: str) -> dict[str, Any]:
    response = client.get(f"{API}/{endpoint}", params={**params, "apikey": key})
    if response.is_error:
        raise RuntimeError(f"HTTP {response.status_code} from Twelve Data endpoint {endpoint}")
    payload = response.json()
    if payload.get("status") == "error" or payload.get("code"):
        # Do not include the response URL; Twelve Data puts its credential there.
        raise RuntimeError(f"Twelve Data error from {endpoint}: {payload.get('message') or payload.get('code')}")
    return payload


def _directory_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    result = payload.get("result") or {}
    if not isinstance(result, dict):
        return []
    value = result.get("list", [])
    if isinstance(value, list):
        return value
    return []


def _fund_result(client: httpx.Client, key: str, symbol: str, kind: str, end_date: date,
                 history_limit: int, include_holdings: bool) -> dict[str, Any]:
    result: dict[str, Any] = {"ticker": symbol, "kind": kind, "valuation_date": end_date.isoformat(),
                              "comparisons": [], "historical_nav": [], "holdings_comparison": None,
                              "endpoint_errors": [], "coverage": {}}
    local: dict[str, Any] | None = None
    try:
        local = _local_record(symbol, kind, end_date, history_limit)
        if local is None:
            result["record_status"] = "missing_in_fundflow"
        else:
            result["fundflow_id"] = local["id"]
    except Exception as error:
        result["endpoint_errors"].append({"endpoint": "FundFlow lookup", "error": _safe_error(error)})

    directory_endpoint = "etfs/list" if kind == "etf" else "funds"
    try:
        directory = _call(client, directory_endpoint, {"symbol": symbol}, key)
        entries = _directory_rows(directory)
        match = next((row for row in entries if str(row.get("symbol", "")).strip().upper() == symbol), None)
        if match is None:
            result["record_status"] = result.get("record_status", "missing_in_twelvedata")
            result["coverage"]["directory"] = "successful response with no exact symbol"
        else:
            result["coverage"]["directory"] = "exact symbol returned"
            if local:
                mappings = (("symbol", "symbol", "symbol"), ("name", "name", "name"),
                            ("country", "country", "country"), ("currency", "currency", "currency"),
                            ("isin", "isin", "isin"))
                for td_field, ff_field, rule in mappings:
                    # ETF directory documents omit NAV currency and ISIN on some
                    # entitlements; represent absent response fields honestly.
                    if kind == "etf" and td_field == "currency" and td_field not in match:
                        result["comparisons"].append({"field": "directory.currency", "status": "unavailable_from_endpoint",
                            "twelve_data": None, "fundflow": local.get("currency"),
                            "note": "The /etfs/list directory response does not provide currency."})
                    elif kind == "etf" and td_field == "isin" and td_field not in match:
                        result["comparisons"].append({"field": "directory.isin", "status": "unavailable_to_subscription",
                            "twelve_data": None, "fundflow": local.get("isin"),
                            "note": "Twelve Data documents ISIN access as a data add-on; no value was returned by this plan."})
                    else:
                        result["comparisons"].append(compare(f"directory.{td_field}", match.get(td_field), local.get(ff_field), rule=rule))
    except Exception as error:
        result["endpoint_errors"].append({"endpoint": directory_endpoint, "error": _safe_error(error)})

    if not local:
        return result

    try:
        series_params: dict[str, Any] = {"symbol": symbol, "interval": "1day"}
        if history_limit:
            local_dates = [date.fromisoformat(row["date"]) for row in local["historical_nav"]]
            if local_dates:
                series_params["start_date"] = min(local_dates).isoformat()
                series_params["end_date"] = end_date.isoformat()
            series_params["outputsize"] = str(min(max(history_limit, 1), 5000))
        else:
            series_params.update({"date": end_date.isoformat(), "outputsize": "1"})
        series = _call(client, "time_series", series_params, key)
        values = series.get("values", [])
        result["coverage"]["time_series"] = len(values)
        if history_limit:
            local_by_date = {row["date"]: row for row in local["historical_nav"]}
            td_by_date = {row.get("datetime"): row for row in values if row.get("datetime")}
            for observed_date in sorted(set(local_by_date) | set(td_by_date)):
                td_row, ff_row = td_by_date.get(observed_date), local_by_date.get(observed_date)
                result["historical_nav"].append({"date": observed_date,
                    "close_vs_nav": compare(f"historical_nav.{observed_date}.close", td_row.get("close") if td_row else None,
                                              ff_row.get("nav") if ff_row else None, rule="numeric")})
        else:
            td_row = next((row for row in values if row.get("datetime") == end_date.isoformat()), None)
            latest_nav = local.get("latest_nav") or {}
            ff_row = latest_nav if latest_nav.get("date") == end_date.isoformat() else None
            result["comparisons"].append(compare("time_series.values.datetime", td_row.get("datetime") if td_row else None,
                                                 ff_row.get("date") if ff_row else None))
            result["comparisons"].append(compare("time_series.values.close_vs_nav", td_row.get("close") if td_row else None,
                                                 ff_row.get("nav") if ff_row else None, rule="numeric"))
        meta = series.get("meta", {})
        for field, value, rule in (("symbol", local.get("symbol"), "symbol"),
                                   ("currency", local.get("currency"), "currency")):
            result["comparisons"].append(compare(f"time_series.meta.{field}", meta.get(field), value, rule=rule))
    except Exception as error:
        result["endpoint_errors"].append({"endpoint": "time_series", "error": _safe_error(error)})

    if include_holdings:
        holdings_endpoint = "etfs/world/composition" if kind == "etf" else "mutual_funds/world/composition"
        try:
            payload = _call(client, holdings_endpoint, {"symbol": symbol}, key)
            provider_key = "etf" if kind == "etf" else "mutual_fund"
            comp = payload.get(provider_key, {}).get("composition", {})
            td_holdings = comp.get("top_holdings", [])
            local_rows = local.get("holdings", [])
            # Twelve Data composition responses do not consistently expose an
            # as-of date. Do not assert a weight match across unknown periods.
            result["holdings_comparison"] = {
                "status": "available_but_period_alignment_unknown" if td_holdings and local_rows else
                          "missing_in_fundflow" if td_holdings and not local_rows else
                          "missing_in_twelvedata" if local_rows and not td_holdings else "unavailable_from_both",
                "twelve_data_holdings": td_holdings,
                "fundflow_holdings": local_rows,
                "fundflow_reporting_date": local.get("holdings_report_date"),
                "twelve_data_as_of_date": payload.get("as_of_date"),
                "weight_differences": [],
                "note": "Holdings weights are not compared unless both sources provide a confirmed aligned reporting date.",
            }
        except Exception as error:
            result["endpoint_errors"].append({"endpoint": holdings_endpoint, "error": _safe_error(error)})
            result["holdings_comparison"] = {"status": "unavailable_or_endpoint_error"}
    else:
        result["holdings_comparison"] = {"status": "not_requested", "credit_cost_if_requested": 200}
    return result


def run(tickers: list[str], kind: str, end_date: date, history_limit: int,
        include_holdings: bool, max_credits: int, interval_seconds: float) -> dict[str, Any]:
    estimate = len(tickers) * (2 + (200 if include_holdings else 0))
    if estimate > max_credits:
        raise ValueError(f"Estimated {estimate} credits exceeds --max-credits={max_credits}; reduce scope or explicitly raise the cap.")
    key = _key()
    records = []
    with httpx.Client(timeout=httpx.Timeout(30), limits=httpx.Limits(max_connections=4), follow_redirects=True) as client:
        for index, ticker in enumerate(tickers, 1):
            LOG.info("Comparing %s (%s/%s)", ticker, index, len(tickers))
            records.append(_fund_result(client, key, ticker, kind, end_date, history_limit, include_holdings))
            if interval_seconds and index < len(tickers):
                time.sleep(interval_seconds)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(), "valuation_date": end_date.isoformat(),
        "kind": kind, "requested_symbols": tickers, "estimated_credits": estimate,
        "credit_note": "Fund/ETF directory and time_series are standard calls; composition is 200 credits per symbol and opt-in.",
        "scope_note": "Only explicitly requested symbols are in scope. An unrequested FundFlow symbol is not counted as missing.",
        "funds": records,
        "totals": {
            "requested": len(tickers), "field_comparisons": sum(len(x["comparisons"]) for x in records),
            "matches": sum(c["status"] == "match" for x in records for c in x["comparisons"]),
            "mismatches": sum(c["status"] == "mismatch" for x in records for c in x["comparisons"]),
            "missing_in_fundflow": sum(c["status"] == "missing_in_fundflow" for x in records for c in x["comparisons"]),
            "missing_in_twelvedata": sum(c["status"] == "missing_in_twelvedata" for x in records for c in x["comparisons"]),
            "unavailable_to_subscription": sum(c["status"] == "unavailable_to_subscription" for x in records for c in x["comparisons"]),
            "unavailable_from_endpoint": sum(c["status"] == "unavailable_from_endpoint" for x in records for c in x["comparisons"]),
            "historical_nav_dates": sum(len(x["historical_nav"]) for x in records),
            "holdings_not_comparable_due_to_period": sum((x.get("holdings_comparison") or {}).get("status") == "available_but_period_alignment_unknown" for x in records),
            "endpoint_errors": sum(len(x["endpoint_errors"]) for x in records),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=("mutual_fund", "etf"), required=True)
    parser.add_argument("--tickers", nargs="+", required=True)
    parser.add_argument("--date", type=date.fromisoformat, default=date.today())
    parser.add_argument("--history-limit", type=int, default=0, help="Compare up to this many daily observations per symbol (0 disables history).")
    parser.add_argument("--include-holdings", action="store_true", help="Calls premium 200-credit composition endpoint per symbol.")
    parser.add_argument("--max-credits", type=int, default=50, help="Hard cap on estimated Twelve Data credits for the run.")
    parser.add_argument("--interval-seconds", type=float, default=1.0)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "reports")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    tickers = [item.strip().upper() for item in args.tickers]
    if len(set(tickers)) != len(tickers) or not all(re.fullmatch(r"[A-Z0-9.\-/]+", item) for item in tickers):
        parser.error("Symbols must be unique and contain only letters, digits, dot, dash, or slash.")
    if args.history_limit < 0 or args.history_limit > 5000:
        parser.error("--history-limit must be from 0 to 5000.")
    if args.interval_seconds < 0:
        parser.error("--interval-seconds cannot be negative")
    try:
        # httpx's INFO event log prints the full request URL, and Twelve Data
        # carries the credential as a query parameter. Keep its logger quiet.
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("httpcore").setLevel(logging.WARNING)
        report = run(tickers, args.kind, args.date, args.history_limit, args.include_holdings, args.max_credits, args.interval_seconds)
    except Exception as error:
        parser.exit(2, f"error: {_safe_error(error)}\n")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"twelvedata_{args.kind}_{args.date.isoformat()}"
    output = args.output_dir / f"{stem}.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    LOG.info("Wrote %s", output)
    print(json.dumps({"report": str(output), "estimated_credits": report["estimated_credits"], "totals": report["totals"]}, indent=2))


if __name__ == "__main__":
    main()
