from app.holdings.sec_nport_bulk import ASSET_CATEGORY_LABELS, _asset_label_sql, latest_quarter
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
