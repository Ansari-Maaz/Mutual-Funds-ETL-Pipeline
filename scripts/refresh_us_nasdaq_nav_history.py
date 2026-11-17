"""Backfill dated US mutual-fund NAV history from Nasdaq Fund Network.

The public Nasdaq quote endpoint is not a formally versioned API. This tool
keeps the exact request URL, uses only the reported close as the daily NAV, and
inserts only missing (fund, date, currency) rows. Existing observations are
never overwritten; value differences are reported for review.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import json
import logging
from pathlib import Path
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.db.session import SessionLocal
from app.models.schema import Fund, NavObservation, Source

ROOT = Path(__file__).resolve().parents[1]
API = "https://api.nasdaq.com/api/quote/{ticker}/historical"
SOURCE_ID = "us_nasdaq_mutual_fund_navs"
LOG = logging.getLogger("fundflow.nasdaq_nav_history")


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    cleaned = str(value).replace("$", "").replace(",", "").strip()
    if not cleaned or cleaned.upper() in {"N/A", "NA", "-"}:
        return None
    try:
        number = Decimal(cleaned)
        return number if number > 0 else None
    except InvalidOperation:
        return None


def fetch_history(ticker: str, start: date, end: date) -> tuple[list[dict], str]:
    params = urllib.parse.urlencode({
        "assetclass": "mutualfunds", "fromdate": start.isoformat(),
        "todate": end.isoformat(), "limit": 500,
    })
    url = API.format(ticker=urllib.parse.quote(ticker)) + "?" + params
    request = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0", "Accept": "application/json, text/plain, */*",
        "Origin": "https://www.nasdaq.com", "Referer": "https://www.nasdaq.com/",
    })
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if payload.get("status", "success") == "error" or payload.get("message"):
        raise RuntimeError(f"Nasdaq returned an error for {ticker}")
    table = ((payload.get("data") or {}).get("tradesTable") or {})
    rows = table.get("rows") or []
    output = []
    for row in rows:
        try:
            valuation_date = datetime.strptime(row.get("date", ""), "%m/%d/%Y").date()
        except ValueError:
            continue
        nav = _decimal(row.get("close"))
        if nav is None or not start <= valuation_date <= end:
            continue
        output.append({"valuation_date": valuation_date, "nav": nav})
    # Duplicate dates in a provider response are not imported twice.
    deduped = {item["valuation_date"]: item for item in output}
    return [deduped[key] for key in sorted(deduped)], url


def refresh(tickers: list[str], *, history_days: int = 365,
            delay_seconds: float = 1.0) -> dict:
    if not 1 <= history_days <= 3650:
        raise ValueError("history_days must be between 1 and 3650")
    if delay_seconds < 0:
        raise ValueError("delay_seconds cannot be negative")
    end = date.today()
    start = end - timedelta(days=history_days)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_id": SOURCE_ID,
        "source_scope": "Nasdaq Fund Network daily mutual-fund close/NAV values; reported values only",
        "requested_start_date": start.isoformat(), "requested_end_date": end.isoformat(),
        "history_days": history_days, "tickers": [],
        "totals": {"requested": len(tickers), "fetched": 0, "inserted": 0,
                   "existing_equal": 0, "existing_conflict": 0, "errors": 0},
        "limitations": [
            "Nasdaq's public quote endpoint is not a formally versioned API.",
            "Only the response close is used as the mutual-fund daily NAV; adjusted close and OHLC fields are not substituted.",
            "Existing FundFlow values are retained. Same-date differences are reported, not overwritten.",
        ],
    }

    with SessionLocal() as session:
        source = {
            "source_id": SOURCE_ID, "country_code": "US", "organization": "Nasdaq",
            "source_name": "Nasdaq Fund Network US mutual-fund daily NAV history",
            "endpoint_url": "https://api.nasdaq.com/api/quote/{ticker}/historical?assetclass=mutualfunds",
            "verification_status": "Usable Fund Data Confirmed",
            "integration_status": "Integrated", "license_status": "Unknown",
        }
        statement = insert(Source).values(**source).on_conflict_do_update(
            index_elements=[Source.source_id],
            set_={key: value for key, value in source.items() if key != "source_id"},
        )
        session.execute(statement)
        session.commit()

    for index, ticker in enumerate(tickers):
        result = {"ticker": ticker, "fetched_rows": 0, "inserted_rows": 0,
                  "existing_equal_rows": 0, "existing_conflict_rows": 0, "error": None}
        try:
            with SessionLocal() as session:
                funds = session.execute(select(Fund).where(
                    Fund.source_id == "sec_open_end_fund_classes",
                    Fund.domicile_country == "US",
                    func.upper(Fund.ticker) == ticker,
                ).order_by(Fund.id)).scalars().all()
            if len(funds) != 1:
                raise LookupError(f"Expected one SEC-linked FundFlow row for {ticker}; found {len(funds)}")
            fund = funds[0]
            if fund.currency != "USD":
                raise ValueError(f"FundFlow currency for {ticker} is not confirmed as USD")

            observations, source_url = fetch_history(ticker, start, end)
            result["fetched_rows"] = len(observations)
            result["source_url"] = source_url
            if not observations:
                raise LookupError(f"Nasdaq returned no dated values for {ticker}")

            dates = [item["valuation_date"] for item in observations]
            with SessionLocal() as session:
                existing_rows = session.execute(select(
                    NavObservation.valuation_date, NavObservation.nav
                ).where(
                    NavObservation.fund_id == fund.id,
                    NavObservation.currency == "USD",
                    NavObservation.valuation_date.in_(dates),
                )).all()
                existing = {day: Decimal(str(value)) for day, value in existing_rows}
                missing, equal, conflicts = [], 0, []
                for item in observations:
                    day, value = item["valuation_date"], item["nav"]
                    if day not in existing:
                        missing.append({
                            "fund_id": fund.id, "source_id": SOURCE_ID,
                            "source_url": source_url, "valuation_date": day,
                            "nav": value, "currency": "USD",
                        })
                    elif existing[day] == value:
                        equal += 1
                    else:
                        conflicts.append({"date": day.isoformat(),
                            "existing_fundflow_nav": str(existing[day]),
                            "nasdaq_reported_nav": str(value),
                            "status": "conflict_preserved_existing"})
                inserted = 0
                if missing:
                    statement = insert(NavObservation.__table__).values(missing).on_conflict_do_nothing(
                        constraint="uq_nav_fund_date_currency")
                    inserted = session.execute(statement).rowcount
                    if inserted is None or inserted < 0:
                        inserted = session.execute(select(func.count()).select_from(NavObservation).where(
                            NavObservation.fund_id == fund.id,
                            NavObservation.source_id == SOURCE_ID,
                            NavObservation.currency == "USD",
                            NavObservation.valuation_date.in_([item["valuation_date"] for item in missing]),
                        )).scalar_one()
                session.commit()
            result["inserted_rows"] = inserted
            result["existing_equal_rows"] = equal
            result["existing_conflict_rows"] = len(conflicts)
            if conflicts:
                result["conflicts"] = conflicts
            report["totals"]["fetched"] += len(observations)
            report["totals"]["inserted"] += inserted
            report["totals"]["existing_equal"] += equal
            report["totals"]["existing_conflict"] += len(conflicts)
        except (urllib.error.URLError, TimeoutError, OSError, ValueError,
                RuntimeError, LookupError) as error:
            result["error"] = f"{type(error).__name__}: {error}"
            report["totals"]["errors"] += 1
            LOG.warning("NAV refresh failed for %s: %s", ticker, result["error"])
        report["tickers"].append(result)
        LOG.info("%s: fetched %d, inserted %d, conflicts %d",
                 ticker, result["fetched_rows"], result["inserted_rows"], result["existing_conflict_rows"])
        if index + 1 < len(tickers) and delay_seconds:
            time.sleep(delay_seconds)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = ROOT / "reports" / f"us_nasdaq_nav_history_{stamp}.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report["report_path"] = str(report_path)
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ticker", action="append", required=True,
                        help="SEC-linked U.S. mutual-fund ticker; repeat per symbol")
    parser.add_argument("--history-days", type=int, default=365)
    parser.add_argument("--delay-seconds", type=float, default=1.0)
    args = parser.parse_args()
    tickers = [item.strip().upper() for item in args.ticker]
    if len(set(tickers)) != len(tickers) or not all(re.fullmatch(r"[A-Z0-9.\-/]+", item) for item in tickers):
        parser.error("Tickers must be unique and contain only letters, digits, dot, dash, or slash.")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    report = refresh(tickers, history_days=args.history_days, delay_seconds=args.delay_seconds)
    print(json.dumps({"report": report["report_path"], "totals": report["totals"]}, indent=2))
    if report["totals"]["errors"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
