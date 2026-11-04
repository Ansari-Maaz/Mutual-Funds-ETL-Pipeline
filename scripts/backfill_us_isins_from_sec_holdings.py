"""Backfill US fund ISINs only from consistent, exact-ticker SEC holdings evidence.

The SEC N-PORT rows describe portfolio securities, not an issuer's complete
fund master. This script therefore requires exact ticker, compatible normalized
fund/security names, one CUSIP/ISIN pair per FundFlow record, and a valid ISIN
check digit. It uses already stored SEC holdings and makes no network requests.
Run with --apply to write; otherwise it reports a dry-run summary.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import date
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert

from app.db.session import SessionLocal
from app.models.schema import Fund, FundProfileSnapshot, PortfolioHolding, Source

SOURCE_ID = "sec_nport_security_identifiers"
SOURCE_NAME = "SEC N-PORT portfolio security identifiers"


def _normalized_name(value: str | None) -> str:
    return re.sub(r"[^A-Z0-9]", "", (value or "").upper())


def _compatible_names(fund_name: str, security_name: str) -> bool:
    fund = _normalized_name(fund_name)
    security = _normalized_name(security_name)
    return len(security) >= 10 and (fund.startswith(security) or security.startswith(fund))


def _valid_isin(isin: str, cusip: str) -> bool:
    if len(isin) != 12 or not isin.startswith("US") or isin[2:11] != cusip:
        return False
    expanded = "".join(str(ord(char) - 55) if char.isalpha() else char for char in isin)
    total = 0
    for index, char in enumerate(reversed(expanded)):
        digit = int(char) * (2 if index % 2 else 1)
        total += digit // 10 + digit % 10
    return total % 10 == 0


def collect_candidates(session) -> tuple[list[dict[str, Any]], dict[str, int]]:
    rows = session.execute(
        select(
            Fund.id.label("fund_id"), Fund.name.label("fund_name"),
            Fund.ticker.label("fund_ticker"), Fund.isin.label("existing_isin"),
            PortfolioHolding.security_name, PortfolioHolding.cusip,
            PortfolioHolding.isin, PortfolioHolding.reporting_date,
            PortfolioHolding.source_url,
        )
        .join(PortfolioHolding, func.upper(func.btrim(PortfolioHolding.ticker))
              == func.upper(func.btrim(Fund.ticker)))
        .where(
            Fund.domicile_country == "US",
            Fund.ticker.is_not(None),
            PortfolioHolding.isin.is_not(None),
            PortfolioHolding.cusip.is_not(None),
        )
    ).mappings().all()

    by_fund: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if not _compatible_names(row["fund_name"], row["security_name"]):
            continue
        if not _valid_isin(row["isin"], row["cusip"]):
            continue
        by_fund[row["fund_id"]].append(dict(row))

    counters = defaultdict(int)
    candidates = []
    for fund_id, evidence in by_fund.items():
        pairs = {(item["cusip"], item["isin"]) for item in evidence}
        if len(pairs) != 1:
            counters["ambiguous_identifier_pair"] += 1
            continue
        existing = {item["existing_isin"] for item in evidence if item["existing_isin"]}
        cusip, isin = next(iter(pairs))
        if existing and existing != {isin}:
            counters["conflicts_with_existing_isin"] += 1
            continue
        evidence.sort(key=lambda item: item["reporting_date"] or date.min, reverse=True)
        candidates.append({**evidence[0], "cusip": cusip, "isin": isin,
                           "filing_rows": len(evidence)})

    isin_owners: dict[str, set[int]] = defaultdict(set)
    for item in candidates:
        isin_owners[item["isin"]].add(item["fund_id"])
    reused = {isin for isin, owners in isin_owners.items() if len(owners) > 1}
    if reused:
        candidates = [item for item in candidates if item["isin"] not in reused]
        counters["ISIN_shared_by_multiple_local_funds"] = len(reused)
    counters["candidate_funds"] = len(candidates)
    counters["source_rows_examined"] = len(rows)
    return candidates, dict(counters)


def backfill(*, apply: bool = False) -> dict[str, Any]:
    with SessionLocal() as session:
        candidates, skipped = collect_candidates(session)
        if not apply:
            return {"dry_run": True, "candidate_funds": len(candidates), "skipped": skipped}

        source = {
            "source_id": SOURCE_ID, "country_code": "US",
            "organization": "U.S. Securities and Exchange Commission",
            "source_name": SOURCE_NAME,
            "endpoint_url": "https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets",
            "verification_status": "Usable Fund Data Confirmed",
            "integration_status": "Integrated", "license_status": "Public SEC filing",
        }
        session.execute(insert(Source).values(**source).on_conflict_do_update(
            index_elements=[Source.source_id],
            set_={key: value for key, value in source.items() if key != "source_id"},
        ))
        updated = already_set = 0
        for item in candidates:
            fund = session.get(Fund, item["fund_id"])
            if fund.isin is None:
                fund.isin = item["isin"]
                updated += 1
            else:
                already_set += 1
            payload = {
                "ticker": item["fund_ticker"], "share_class_name": item["fund_name"],
                "security_name_as_reported": item["security_name"],
                "cusip": item["cusip"], "isin": item["isin"],
                "evidence_method": "Exact ticker, compatible name, one consistent CUSIP/ISIN pair, valid ISIN check digit",
                "filing_rows_with_same_identifiers": item["filing_rows"],
            }
            key = hashlib.sha256(json.dumps(
                [SOURCE_ID, item["fund_id"], item["isin"]], separators=(",", ":")
            ).encode()).hexdigest()
            statement = insert(FundProfileSnapshot).values(
                fund_id=item["fund_id"], source_id=SOURCE_ID, dataset="identifiers",
                source_report_date=item["reporting_date"], snapshot_key=key,
                payload=payload, source_url=item["source_url"],
            )
            session.execute(statement.on_conflict_do_update(
                constraint="uq_fund_profile_source_snapshot", set_={
                    "source_report_date": statement.excluded.source_report_date,
                    "payload": statement.excluded.payload,
                    "source_url": statement.excluded.source_url,
                }
            ))
        session.commit()
        return {"dry_run": False, "candidate_funds": len(candidates),
                "fund_isins_newly_set": updated, "fund_isins_already_set": already_set,
                "skipped": skipped}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Write exact, validated identifier matches")
    args = parser.parse_args()
    print(json.dumps(backfill(apply=args.apply), indent=2))


if __name__ == "__main__":
    main()
