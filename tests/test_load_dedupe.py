from datetime import date

from app.etl.load import dedupe_funds_last_wins, dedupe_navs_last_wins
from app.schemas.canonical import CanonicalFund, CanonicalNav


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
        (9, CanonicalNav(source_id="source", source_fund_id="same", valuation_date=valuation_date, nav=1.0, currency="USD")),
        (9, CanonicalNav(source_id="source", source_fund_id="same", valuation_date=valuation_date, nav=2.0, currency="USD")),
    ]
    result = dedupe_navs_last_wins(rows)
    assert len(result) == 1
    assert result[0]["nav"] == 2.0
