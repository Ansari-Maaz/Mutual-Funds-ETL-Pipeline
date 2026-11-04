"""Sync Vanguard's public official catalogue for exact US ticker matches."""
from __future__ import annotations

import argparse
import json
import urllib.request
from collections import Counter
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.config import timeout_seconds, user_agent
from app.db.session import SessionLocal
from app.etl.load import upsert_fund_profile_snapshots
from app.models.schema import Fund, Source

SOURCE_ID = "us_vanguard_fund_directory"
SOURCE_URL = "https://advisors.vanguard.com/investments/fund-data/all-products"


def parse_directory(payload: Any) -> list[dict[str, Any]]:
    """Validate and normalize catalog rows without changing provider values."""
    if not isinstance(payload, dict):
        raise ValueError("Vanguard directory response must be a JSON object")
    rows = []
    seen: set[str] = set()
    for port_id, row in payload.items():
        if not isinstance(row, dict):
            continue
        ticker = str(row.get("ticker") or "").strip().upper()
        identifier = str(row.get("identifier") or "").strip().upper()
        if not ticker:
            continue
        if identifier and identifier != ticker:
            raise ValueError(f"Vanguard directory identifier differs from ticker for {ticker}")
        if ticker in seen:
            raise ValueError(f"Duplicate ticker in Vanguard directory: {ticker}")
        seen.add(ticker)
        if str(row.get("portId") or port_id) != str(port_id):
            raise ValueError(f"Vanguard catalogue port ID mismatch for ticker {ticker}")
        rows.append(row)
    return rows


def fetch_directory() -> tuple[list[dict[str, Any]], str]:
    request = urllib.request.Request(SOURCE_URL, headers={
        "User-Agent": user_agent(), "Accept": "application/json",
    })
    with urllib.request.urlopen(request, timeout=timeout_seconds()) as response:
        if response.status != 200:
            raise RuntimeError(f"Vanguard directory returned HTTP {response.status}")
        final_url = response.geturl()
        payload = json.loads(response.read().decode("utf-8"))
    return parse_directory(payload), final_url


def _report_date(row: dict[str, Any]) -> date | None:
    returns = row.get("navReturns")
    if not isinstance(returns, dict):
        return None
    raw = returns.get("dailyEffectiveDate")
    try:
        return date.fromisoformat(raw) if raw else None
    except (TypeError, ValueError):
        return None


def sync_directory(*, dry_run: bool = False) -> dict[str, Any]:
    rows, source_url = fetch_directory()
    tickers = [str(row["ticker"]).strip().upper() for row in rows]
    with SessionLocal() as session:
        funds = session.scalars(select(Fund).where(
            Fund.domicile_country == "US", Fund.ticker.in_(tickers)
        )).all()
        funds_by_ticker: dict[str, list[Fund]] = {}
        for fund in funds:
            funds_by_ticker.setdefault((fund.ticker or "").strip().upper(), []).append(fund)

        matched: list[tuple[Fund, dict[str, Any]]] = []
        skipped = Counter()
        for row in rows:
            ticker = str(row["ticker"]).strip().upper()
            candidates = funds_by_ticker.get(ticker, [])
            if len(candidates) != 1:
                skipped["no_exact_unique_US_ticker_match" if not candidates else "ambiguous_US_ticker"] += 1
                continue
            matched.append((candidates[0], row))

        summary = {
            "directory_products": len(rows), "matched_funds": len(matched),
            "unique_exact_ticker_matches": len(matched), "skipped": dict(skipped),
            "source_url": source_url, "dry_run": dry_run,
        }
        if dry_run:
            return summary

        source = {
            "source_id": SOURCE_ID, "country_code": "US", "organization": "The Vanguard Group",
            "source_name": "Vanguard public all-products directory", "endpoint_url": source_url,
            "verification_status": "Usable Fund Data Confirmed", "integration_status": "Integrated",
            "license_status": "Unknown",
        }
        session.execute(insert(Source).values(**source).on_conflict_do_update(
            index_elements=[Source.source_id],
            set_={key: value for key, value in source.items() if key != "source_id"},
        ))
        totals = Counter()
        for fund, row in matched:
            classifications = row.get("classifications") if isinstance(row.get("classifications"), dict) else {}
            summary_data = {
                "provider_fund_id": row.get("portId"), "provider_fund_name": row.get("longName"),
                "provider_short_name": row.get("shortName"), "ticker": row.get("ticker"),
                "identifier": row.get("identifier"), "inception_date": row.get("inceptionDate"),
                "is_closed_to_new_investors": row.get("isClosedToNewInvestors"),
                "is_new_fund": row.get("isNewFund"), "classifications": classifications,
                "benchmark_name": row.get("benchmarkLongName"),
                "should_include_in_filtered_share_classes": row.get("shouldIncludeInFilteredShareClasses"),
                "name_match_note": "Provider display name stored separately; SEC fund name was not overwritten.",
            }
            snapshots: dict[str, dict] = {"summary": summary_data}

            if row.get("expenseRatio") not in (None, ""):
                snapshots["expense_ratio_history"] = {
                    "reported_value": row["expenseRatio"], "unit": "percent",
                    "measure": "Vanguard directory expenseRatio", "effective_date": None,
                    "note": "Directory does not provide an effective date for this expense ratio.",
                }
            nav_returns = row.get("navReturns")
            if isinstance(nav_returns, dict) and any(k not in {"dailyEffectiveDate", "monthlyEffectiveDate"} for k in nav_returns):
                snapshots["performance"] = {
                    "pricing_basis": "NAV", "values": nav_returns,
                    "methodology": "Provider-reported directory values; raw values and labels preserved.",
                }
            yields = row.get("yields")
            if isinstance(yields, dict) and yields:
                snapshots["yields"] = {"values": yields,
                    "methodology": "Provider-reported yield objects; each field's effective date is preserved."}
            loaded = upsert_fund_profile_snapshots(session, fund.id, SOURCE_ID, snapshots,
                as_of_date=_report_date(row), source_url=source_url)
            totals["snapshots"] += loaded
            totals["matched_funds"] += 1
            inception = row.get("inceptionDate")
            if inception and fund.inception_date is None:
                try:
                    fund.inception_date = date.fromisoformat(inception)
                    totals["inception_dates_filled"] += 1
                except (TypeError, ValueError):
                    totals["invalid_inception_dates"] += 1
            if classifications.get("isETF") is True and not fund.fund_type:
                fund.fund_type = "ETF"
            elif classifications.get("isMutualFund") is True and not fund.fund_type:
                fund.fund_type = "Mutual fund"
        session.commit()
        summary.update(dict(totals))
        return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Fetch and count exact matches without writing to PostgreSQL")
    args = parser.parse_args()
    print(json.dumps(sync_directory(dry_run=args.dry_run), indent=2))


if __name__ == "__main__":
    main()
