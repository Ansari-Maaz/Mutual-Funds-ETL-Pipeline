from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.schema import Fund, NavObservation
from typing import Iterable

def upsert_fund(session: Session, source_id: str, fund) -> None:
    stmt = insert(Fund).values(**fund_values(source_id, fund))
    stmt = stmt.on_conflict_do_update(constraint="uq_fund_source_native", set_={
        "name": stmt.excluded.name,
        "domicile_country": stmt.excluded.domicile_country,
        "currency": stmt.excluded.currency,
        "isin": stmt.excluded.isin,
        "legal_name": stmt.excluded.legal_name,
        "provider": stmt.excluded.provider,
        "category": stmt.excluded.category,
        "fund_type": stmt.excluded.fund_type,
        "inception_date": stmt.excluded.inception_date,
        "status": stmt.excluded.status,
        "official_url": stmt.excluded.official_url,
        "ticker": stmt.excluded.ticker,
        "manager": stmt.excluded.manager,
        "administrator": stmt.excluded.administrator,
        "net_assets": stmt.excluded.net_assets,
        "net_assets_date": stmt.excluded.net_assets_date,
        "target_audience": stmt.excluded.target_audience,
    })
    session.execute(stmt)

def upsert_nav(session: Session, fund_id: int, nav) -> None:
    stmt = insert(NavObservation).values(fund_id=fund_id, valuation_date=nav.valuation_date, nav=nav.nav, currency=nav.currency)
    stmt = stmt.on_conflict_do_update(constraint="uq_nav_fund_date_currency", set_={"nav": stmt.excluded.nav})
    session.execute(stmt)

def upsert_funds_batch(session: Session, source_id: str, funds: Iterable) -> dict[str, int]:
    """Upsert a bounded batch of funds and return native-id to database-id mapping."""
    rows=[fund_values(source_id, f) for f in funds]
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
    rows=[{"fund_id":fund_id,"valuation_date":nav.valuation_date,"nav":nav.nav,
      "currency":nav.currency} for fund_id,nav in observations]
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
