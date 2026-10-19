from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.schema import Fund, NavObservation
from typing import Iterable

def upsert_fund(session: Session, source_id: str, fund) -> None:
    stmt = insert(Fund).values(source_id=source_id, source_fund_id=fund.source_fund_id, name=fund.name, domicile_country=fund.domicile_country, currency=fund.currency, isin=fund.isin)
    stmt = stmt.on_conflict_do_update(constraint="uq_fund_source_native", set_={"name": stmt.excluded.name, "domicile_country": stmt.excluded.domicile_country, "currency": stmt.excluded.currency, "isin": stmt.excluded.isin})
    session.execute(stmt)

def upsert_nav(session: Session, fund_id: int, nav) -> None:
    stmt = insert(NavObservation).values(fund_id=fund_id, valuation_date=nav.valuation_date, nav=nav.nav, currency=nav.currency)
    stmt = stmt.on_conflict_do_update(constraint="uq_nav_fund_date_currency", set_={"nav": stmt.excluded.nav})
    session.execute(stmt)

def upsert_funds_batch(session: Session, source_id: str, funds: Iterable) -> dict[str, int]:
    """Upsert a bounded batch of funds and return native-id to database-id mapping."""
    rows=[{"source_id":source_id,"source_fund_id":f.source_fund_id,"name":f.name,
      "domicile_country":f.domicile_country,"currency":f.currency,"isin":f.isin} for f in funds]
    if not rows:
        return {}
    stmt=insert(Fund).values(rows)
    stmt=stmt.on_conflict_do_update(constraint="uq_fund_source_native",set_={
      "name":stmt.excluded.name,"domicile_country":stmt.excluded.domicile_country,
      "currency":stmt.excluded.currency,"isin":stmt.excluded.isin})
    session.execute(stmt)
    ids=session.execute(select(Fund.source_fund_id,Fund.id).where(
      Fund.source_id==source_id,Fund.source_fund_id.in_([r["source_fund_id"] for r in rows])))
    return {source_fund_id:fund_id for source_fund_id,fund_id in ids}

def upsert_navs_batch(session: Session, observations: Iterable[tuple[int, object]]) -> None:
    """Upsert a bounded batch of (fund_id, validated NAV) pairs."""
    rows=[{"fund_id":fund_id,"valuation_date":nav.valuation_date,"nav":nav.nav,
      "currency":nav.currency} for fund_id,nav in observations]
    if not rows:
        return
    stmt=insert(NavObservation).values(rows)
    stmt=stmt.on_conflict_do_update(constraint="uq_nav_fund_date_currency",set_={"nav":stmt.excluded.nav})
    session.execute(stmt)
