from datetime import date

from sqlalchemy.dialects import postgresql

from app.etl.load import dedupe_funds_last_wins, dedupe_navs_last_wins, fund_upsert_statement
from app.schemas.canonical import CanonicalFund, CanonicalNav


def test_fund_upsert_preserves_enrichment_fields_on_null_refresh():
    statement = fund_upsert_statement([
        {"source_id": "sec_open_end_fund_classes", "source_fund_id": "C000000001", "name": "Fund"},
    ])
    sql = str(statement.compile(dialect=postgresql.dialect()))

    # Identity fields are always refreshed from the source master.
    assert "name = excluded.name" in sql
    assert "provider = excluded.provider" in sql
    # Enrichment-owned fields keep an existing value when the refresh sends null.
    for column in ("isin", "ticker", "category", "inception_date", "manager",
                   "administrator", "net_assets", "net_assets_date", "target_audience"):
        assert f"{column} = coalesce(excluded.{column}, funds.{column})" in sql


def test_fund_batch_dedupes_native_id_with_last_record_winning():
    rows = [
        CanonicalFund(source_id="source", source_fund_id="same", name="Earlier", domicile_country="US"),
        CanonicalFund(source_id="source", source_fund_id="same", name="Latest", domicile_country="US"),
    ]
    result = dedupe_funds_last_wins(rows)
    assert len(result) == 1
    assert result[0]["source_fund_id"] == "same"
    assert result[0]["name"] == "Latest"


def test_nav_batch_dedupes_conflict_key_with_last_observation_winning():
    valuation_date = date(2026, 10, 1)
    rows = [
        (9, CanonicalNav(source_id="earlier", source_fund_id="same", valuation_date=valuation_date, nav=1.0, currency="USD", source_url="https://example.test/old")),
        (9, CanonicalNav(source_id="latest", source_fund_id="same", valuation_date=valuation_date, nav=2.0, currency="USD", source_url="https://example.test/latest")),
    ]
    result = dedupe_navs_last_wins(rows)
    assert len(result) == 1
    assert result[0]["nav"] == 2.0
    assert result[0]["source_id"] == "latest"
    assert result[0]["source_url"] == "https://example.test/latest"
