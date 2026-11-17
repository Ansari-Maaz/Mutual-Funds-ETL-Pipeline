"""Compare a representative US mutual-fund sample against Twelve Data.

The comparison is read-only: vendor responses are written to a report file,
not imported into FundFlow tables. It uses two one-credit endpoints per fund
and deliberately does not call the premium full-data endpoint.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import getpass
import json
import os
from pathlib import Path
import time

from scripts.compare_twelvedata import _safe_error, run_comparison

ROOT = Path(__file__).resolve().parents[1]
REPORTS = ROOT / "reports"
DEFAULT_TICKERS = [
    "VFIAX",  # large-cap index
    "VTSAX",  # total US market
    "FXAIX",  # S&P 500 index
    "SWPPX",  # S&P 500 index, second provider
    "FCNTX",  # active growth
    "DODGX",  # active value
    "FBALX",  # balanced allocation
    "VWELX",  # balanced allocation, second provider
    "VBTLX",  # US bond index
    "VTIAX",  # international equity index
]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat, default=date(2026, 10, 30),
                        help="Common local NAV date to compare (default: 2026-10-30)")
    parser.add_argument("--tickers", nargs="+", default=DEFAULT_TICKERS,
                        help="10–20 US fund tickers; defaults to the curated sample")
    parser.add_argument("--interval-seconds", type=float, default=15,
                        help="Delay between funds to stay within basic API credit limits")
    args = parser.parse_args()
    tickers = [ticker.strip().upper() for ticker in args.tickers]
    if not 10 <= len(tickers) <= 20:
        parser.error("Provide 10 to 20 tickers.")
    if len(set(tickers)) != len(tickers):
        parser.error("Tickers must be unique.")
    if args.interval_seconds < 0:
        parser.error("--interval-seconds cannot be negative.")

    if not (os.getenv("TWELVE_DATA_API_KEY") or os.getenv("TD_KEY")):
        # Hidden prompt avoids putting the credential in shell history, process
        # arguments, output files, or the checked-in project configuration.
        os.environ["TWELVE_DATA_API_KEY"] = getpass.getpass("Twelve Data API key (hidden input): ")

    results = []
    for index, ticker in enumerate(tickers):
        if index and args.interval_seconds:
            time.sleep(args.interval_seconds)
        print(f"[{index + 1}/{len(tickers)}] Comparing {ticker}", flush=True)
        try:
            results.append(run_comparison(ticker, args.date, include_full_data=False))
        except Exception as error:
            # Never serialize an exception's request URL: API keys are sent as
            # query parameters by Twelve Data and must not land in reports.
            results.append({"ticker": ticker, "valuation_date": args.date.isoformat(),
                            "endpoint_errors": [{"endpoint": "comparison",
                                "error": _safe_error(error)}],
                            "comparisons": []})

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "valuation_date": args.date.isoformat(),
        "scope": "10 US mutual-fund share classes; Twelve Data directory metadata and one daily-series observation; no premium full-data endpoint",
        "tickers_requested": tickers,
        "endpoint_cost_note": "Two standard requests per fund (directory and time series); premium /mutual_funds/world was not called.",
        "funds": results,
        "totals": {
            "funds_requested": len(tickers),
            "funds_with_any_comparisons": sum(bool(item.get("comparisons")) for item in results),
            "field_comparisons": sum(len(item.get("comparisons", [])) for item in results),
            "matches": sum(1 for item in results for field in item.get("comparisons", []) if field.get("status") == "match"),
            "mismatches": sum(1 for item in results for field in item.get("comparisons", []) if field.get("status") == "mismatch"),
            "missing_in_fundflow": sum(1 for item in results for field in item.get("comparisons", []) if field.get("status") == "missing_in_fundflow"),
            "missing_in_twelvedata": sum(1 for item in results for field in item.get("comparisons", []) if field.get("status") == "missing_in_twelvedata"),
            "unavailable_to_subscription": sum(1 for item in results for field in item.get("comparisons", []) if field.get("status") == "unavailable_to_subscription"),
            "endpoint_errors": sum(len(item.get("endpoint_errors", [])) for item in results),
        },
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    output = REPORTS / f"twelvedata_us_fund_comparison_{args.date.isoformat()}.json"
    output.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    price_rows = []
    response_blocks = []
    exact_prices = cent_prices = available_prices = 0
    exact_symbol_date_currency = 0
    for item in results:
        fields = {field["field"]: field for field in item.get("comparisons", [])}
        close = fields.get("time_series.values.close_vs_nav", {})
        td_price, ff_price = close.get("twelve_data"), close.get("fundflow")
        name = fields.get("directory.name", {}).get("fundflow", "")
        if td_price is not None and ff_price is not None:
            available_prices += 1
            exact_prices += int(close.get("numeric_value_match", False))
            cent_prices += int(close.get("rounded_to_cent_match", False))
            delta = close.get("difference", "")
            safe_name = name.replace("|", "\\|")
            price_rows.append(f"| {item['ticker']} | {safe_name} | {td_price} | {ff_price} | {delta} | {'Yes' if close.get('rounded_to_cent_match') else 'No'} |")
        if all(fields.get(key, {}).get("status") == "match" for key in (
                "directory.symbol", "directory.country", "directory.currency",
                "time_series.values.datetime", "time_series.meta.currency")):
            exact_symbol_date_currency += 1
        def value(path: str, side: str):
            return fields.get(path, {}).get(side)
        def number(path: str):
            raw = value(path, "twelve_data")
            return float(raw) if raw is not None else None
        td_data = {
            "symbol": value("time_series.meta.symbol", "twelve_data"),
            "instrument_type": value("time_series.meta.type", "twelve_data"),
            "exchange": value("time_series.meta.exchange", "twelve_data"),
            "mic_code": value("time_series.meta.mic_code", "twelve_data"),
            "currency": value("time_series.meta.currency", "twelve_data"),
            "exchange_timezone": value("time_series.meta.exchange_timezone", "twelve_data"),
            "interval": "1day",
            "market_data": [{
                "date": value("time_series.values.datetime", "twelve_data"),
                "open": number("time_series.values.open"),
                "high": number("time_series.values.high"),
                "low": number("time_series.values.low"),
                "close": number("time_series.values.close_vs_nav"),
            }],
        }
        ff_data = {
            "name": value("directory.name", "fundflow"),
            "ticker": value("directory.symbol", "fundflow"),
            "valuation_date": value("time_series.values.datetime", "fundflow"),
            "nav": float(value("time_series.values.close_vs_nav", "fundflow")) if value("time_series.values.close_vs_nav", "fundflow") is not None else None,
            "currency": value("time_series.meta.currency", "fundflow"),
        }
        td_response = {"status": "success" if not item.get("endpoint_errors") else "error", "data": td_data}
        ff_response = {"status": "success" if item.get("fundflow_id") else "error", "data": ff_data}
        response_blocks.extend([
            f"### {item['ticker']}", "", "**TWELVE DATA**", "",
            "```json", json.dumps(td_response, indent=2, ensure_ascii=False), "```", "",
            "**FUNDFLOW**", "", "```json", json.dumps(ff_response, indent=2, ensure_ascii=False), "```", "",
        ])
    markdown = [
        f"# Twelve Data vs FundFlow US mutual fund comparison — {args.date.isoformat()}", "",
        f"Generated {report['generated_at']}.", "",
        "FundFlow prices below are the stored Yahoo Finance daily prices for the same date. This is vendor-to-vendor price comparison, not issuer-verified NAV. Twelve Data values are not imported into FundFlow.", "",
        "## Price comparison", "",
        "| Ticker | FundFlow fund name | Twelve Data close | FundFlow value | TD − FundFlow | Same to nearest cent |",
        "|---|---|---:|---:|---:|:---:|", *price_rows, "",
        "## Findings", "",
        f"- Symbol, country, currency, and date matched for {exact_symbol_date_currency}/{len(results)} funds; endpoint errors: {report['totals']['endpoint_errors']}.",
        f"- Daily values are exactly equal for {exact_prices}/{available_prices} funds and equal to the nearest cent for {cent_prices}/{available_prices}.",
        "- ISIN/CUSIP returned `request_access_via_add_ons`; those values are unavailable under the current subscription. Exchange and OHLC fields are included in the Twelve Data response; FundFlow stores a single daily value.", "",
        "The response blocks below use the requested format.", "", *response_blocks,
    ]
    markdown_output = output.with_suffix(".md")
    markdown_output.write_text("\n".join(markdown) + "\n", encoding="utf-8")
    print(json.dumps({"report": str(output), "summary": str(markdown_output), **report["totals"]}, indent=2))


if __name__ == "__main__":
    main()
