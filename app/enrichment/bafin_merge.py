"""Merge BaFin Investmentfonds-Datenbank fields into German funds already loaded from the Banco de España list."""
from __future__ import annotations

import collections
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.connectors.de_bafin_funds import ATTRIBUTION, BASE, RAW, parse_rows
from app.db.session import SessionLocal
from app.enrichment.eu_fund_ids import norm_name
from app.models.schema import Fund, FundIdentifier, FundProfileSnapshot
import csv

SOURCE_ID = "de_bafin_investmentfonds"


def match_by_name(funds: list[tuple[int, str]], bafin: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    """Unique normalised-name matches only: a name shared by several funds on either side is never merged."""
    by_db: dict[str, list[int]] = collections.defaultdict(list)
    for fund_id, name in funds:
        by_db[norm_name(name)].append(fund_id)
    by_bafin: dict[str, list[dict[str, Any]]] = collections.defaultdict(list)
    for record in bafin:
        by_bafin[norm_name(record["name"])].append(record)
    return {ids[0]: by_bafin[key][0] for key, ids in by_db.items()
            if key and len(ids) == 1 and len(by_bafin.get(key, [])) == 1}


def merge_bafin_into_existing() -> dict[str, int]:
    with (RAW / "bafin_investmentfonds.csv").open(encoding="utf-8", newline="") as stream:
        reader = csv.reader(stream, delimiter=";")
        next(reader, None)
        bafin, _rejects = parse_rows(reader)
    now = datetime.now(timezone.utc)
    stats = {"existing_de_funds": 0, "matched": 0, "isin_set": 0, "inception_set": 0, "fund_type_set": 0}
    with SessionLocal() as session:
        funds = session.execute(select(Fund.id, Fund.name).where(Fund.domicile_country == "DE",
                                                                 Fund.source_id != SOURCE_ID)).all()
        stats["existing_de_funds"] = len(funds)
        matches = match_by_name(funds, bafin)
        stats["matched"] = len(matches)
        sources = dict(session.execute(select(Fund.id, Fund.source_id).where(Fund.id.in_(list(matches)))).all())
        for fund_id, record in matches.items():
            if record["isin"]:
                session.execute(pg_insert(FundIdentifier.__table__).values(
                    fund_id=fund_id, id_type="ISIN", value=record["isin"], source_id=SOURCE_ID, share_class=record["name"],
                    attributes={"bafin_id": record["source_fund_id"], "attribution": ATTRIBUTION}, source_url=BASE,
                    retrieved_at=now).on_conflict_do_nothing(constraint="uq_fund_identifier"))
                if session.execute(update(Fund).where(Fund.id == fund_id, Fund.isin.is_(None)).values(isin=record["isin"])).rowcount:
                    stats["isin_set"] += 1
            if record["inception_date"] and session.execute(update(Fund).where(Fund.id == fund_id, Fund.inception_date.is_(None))
                    .values(inception_date=date.fromisoformat(record["inception_date"]))).rowcount:
                stats["inception_set"] += 1
            if record["fund_type"] and session.execute(update(Fund).where(Fund.id == fund_id, Fund.fund_type.is_(None))
                    .values(fund_type=record["fund_type"])).rowcount:
                stats["fund_type_set"] += 1
            payload = {**record["_profile_data"]["summary"], "bafin_id": record["source_fund_id"],
                       "bafin_umbrella": record["legal_name"], "bafin_fund_kind": record["fund_type"]}
            stmt = pg_insert(FundProfileSnapshot.__table__).values(
                fund_id=fund_id, source_id=sources[fund_id], dataset="bafin_register", source_report_date=None,
                snapshot_key="bafin", payload=payload, source_url=BASE, retrieved_at=now)
            session.execute(stmt.on_conflict_do_update(constraint="uq_fund_profile_source_snapshot",
                set_={"payload": stmt.excluded.payload, "retrieved_at": stmt.excluded.retrieved_at}))
        session.commit()
    return stats
