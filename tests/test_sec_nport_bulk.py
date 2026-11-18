from app.holdings.sec_nport_bulk import (
    ASSET_CATEGORY_LABELS, _asset_label_sql, _clean_isin, _clean_text, latest_quarter,
)
from datetime import date

# Every ASSET_CAT value observed in the 2026q3 SEC DERA holding file.
FILED_ASSET_CATEGORIES = {
    "EC", "DBT", "LON", "ABS-MBS", "DFE", "ABS-O", "ABS-CBDO", "DE", "DIR",
    "OTHER", "STIV", "EP", "DCR", "DCO", "RA", "SN", "DO", "RE", "ABS-APCP",
    "COMM",
}


def test_every_filed_asset_category_has_a_label():
    assert FILED_ASSET_CATEGORIES <= set(ASSET_CATEGORY_LABELS)


def test_asset_label_sql_maps_codes_and_falls_back_to_the_code():
    sql = _asset_label_sql()
    assert "WHEN 'EC' THEN 'Common equity'" in sql
    assert "WHEN 'DBT' THEN 'Debt'" in sql
    assert sql.startswith("CASE c.code")
    assert sql.endswith("ELSE c.code END")


def test_latest_quarter_lags_publication_by_about_six_weeks():
    # 2026-11-17 is inside Q4, whose data set cannot be published yet.
    assert latest_quarter(date(2026, 11, 17)) == "2026q3"
    assert latest_quarter(date(2026, 8, 20)) == "2026q2"


def test_filed_placeholders_become_null():
    assert _clean_text("N/A") is None
    assert _clean_text(" n/a ") is None
    assert _clean_text("None") is None
    assert _clean_text("--") is None
    assert _clean_text("  Acme Corp  ") == "Acme Corp"
    assert _clean_text("Acme Corporation", limit=4) == "Acme"


def test_only_valid_isins_are_kept():
    assert _clean_isin("US1746101054") == "US1746101054"
    assert _clean_isin("us1746101054") == "US1746101054"
    assert _clean_isin("US1746101055") is None  # bad Luhn check digit
    assert _clean_isin("N/A") is None
    assert _clean_isin("0") is None
    assert _clean_isin("3487") is None
