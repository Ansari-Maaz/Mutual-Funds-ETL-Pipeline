from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.schema import Fund, NavObservation
from typing import Iterable


def dedupe_funds_last_wins(funds: Iterable) -> list[dict]:
    """Prepare unique source-native IDs while preserving last-record semantics."""
    by_id = {}
    for fund in funds:
        row = fund_values("", fund)
        by_id[row["source_fund_id"]] = row
    return list(by_id.values())


def dedupe_navs_last_wins(observations: Iterable[tuple[int, object]]) -> list[dict]:
    """Prepare unique fund/date/currency keys, with the last observation winning."""
    by_key = {}
    for fund_id, nav in observations:
        by_key[(fund_id, nav.valuation_date, nav.currency)] = {
            "fund_id": fund_id, "valuation_date": nav.valuation_date,
            "nav": nav.nav, "currency": nav.currency,
        }
    return list(by_key.values())

def upsert_funds_batch(session: Session, source_id: str, funds: Iterable) -> dict[str, int]:
    """Upsert a bounded batch of funds and return native-id to database-id mapping."""
    # PostgreSQL cannot update the same conflict target twice in one INSERT.
    # Keep input order so the last source record wins deterministically.
    rows = dedupe_funds_last_wins(funds)
    for row in rows:
        row["source_id"] = source_id
    if not rows:
        return {}
    stmt=insert(Fund).values(rows)
    stmt=stmt.on_conflict_do_update(constraint="uq_fund_source_native",set_={
      "name":stmt.excluded.name,"domicile_country":stmt.excluded.domicile_country,
      "currency":stmt.excluded.currency,"isin":stmt.excluded.isin,
      "legal_name":stmt.excluded.legal_name,"provider":stmt.excluded.provider,
      "category":stmt.excluded.category,"fund_type":stmt.excluded.fund_type,
      "inception_date":stmt.excluded.inception_date,"status":stmt.excluded.status,
      "official_url":stmt.excluded.official_url,"ticker":stmt.excluded.ticker,
      "manager":stmt.excluded.manager,"administrator":stmt.excluded.administrator,
      "net_assets":stmt.excluded.net_assets,"net_assets_date":stmt.excluded.net_assets_date,
      "target_audience":stmt.excluded.target_audience})
    session.execute(stmt)
    ids=session.execute(select(Fund.source_fund_id,Fund.id).where(
      Fund.source_id==source_id,Fund.source_fund_id.in_([r["source_fund_id"] for r in rows])))
    return {source_fund_id:fund_id for source_fund_id,fund_id in ids}

def upsert_navs_batch(session: Session, observations: Iterable[tuple[int, object]]) -> None:
    """Upsert a bounded batch of (fund_id, validated NAV) pairs."""
    rows = dedupe_navs_last_wins(observations)
    if not rows:
        return
    stmt=insert(NavObservation).values(rows)
    stmt=stmt.on_conflict_do_update(constraint="uq_nav_fund_date_currency",set_={"nav":stmt.excluded.nav})
    session.execute(stmt)


def fund_values(source_id: str, fund) -> dict:
    return {
        "source_id": source_id,
        "source_fund_id": fund.source_fund_id,
        "name": fund.name,
        "domicile_country": fund.domicile_country,
        "currency": fund.currency,
        "isin": fund.isin,
        "legal_name": fund.legal_name,
        "provider": fund.provider,
        "category": fund.category,
        "fund_type": fund.fund_type,
        "inception_date": fund.inception_date,
        "status": fund.status,
        "official_url": fund.official_url,
        "ticker": fund.ticker,
        "manager": fund.manager,
        "administrator": fund.administrator,
        "net_assets": fund.net_assets,
        "net_assets_date": fund.net_assets_date,
        "target_audience": fund.target_audience,
    }
