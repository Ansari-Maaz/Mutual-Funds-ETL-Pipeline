from app.holdings.sec_nmfp import parse_nmfp_xml


def test_parse_nmfp_class_daily_nav_preserves_source_and_unknown_currency():
    payload = b'''<?xml version="1.0" encoding="UTF-8"?>
    <edgarSubmission xmlns="https://www.sec.gov/edgar/nmfp">
      <seriesId>S000000001</seriesId><repPdEnd>2026-09-30</repPdEnd>
      <classLevelInfo>
        <classFullName>Institutional Shares</classFullName><classesId>C000000001</classesId>
        <netAssetsOfClass>1200000.50</netAssetsOfClass><numberOfSharesOutstanding>1200000.00</numberOfSharesOutstanding>
        <dailyNetAssetValuePerShareClass><dailyNetAssetValuePerShareClass>1.0001</dailyNetAssetValuePerShareClass><dailyNetAssetValuePerShareDateClass>2026-09-01</dailyNetAssetValuePerShareDateClass></dailyNetAssetValuePerShareClass>
        <dailyNetAssetValuePerShareClass><dailyNetAssetValuePerShareClass>1.0002</dailyNetAssetValuePerShareClass><dailyNetAssetValuePerShareDateClass>2026-09-02</dailyNetAssetValuePerShareDateClass></dailyNetAssetValuePerShareClass>
      </classLevelInfo>
    </edgarSubmission>'''

    parsed = parse_nmfp_xml(payload, accession_number="0000000001-26-000001",
                            source_url="https://www.sec.gov/Archives/example.xml")

    assert parsed["series_id"] == "S000000001"
    assert parsed["report_date"] == "2026-09-30"
    assert parsed["classes"][0]["class_id"] == "C000000001"
    assert parsed["classes"][0]["class_name"] == "Institutional Shares"
    assert parsed["classes"][0]["observations"] == [
        {"valuation_date": "2026-09-01", "nav": "1.0001", "currency": None,
         "value_type": "SEC-reported class NAV per share"},
        {"valuation_date": "2026-09-02", "nav": "1.0002", "currency": None,
         "value_type": "SEC-reported class NAV per share"},
    ]


def test_parse_nmfp_ignores_incomplete_class_observations():
    payload = b'''<submission><classLevelInfo><classesId>C1</classesId>
    <dailyNetAssetValuePerShareClass><dailyNetAssetValuePerShareClass>n/a</dailyNetAssetValuePerShareClass>
    <dailyNetAssetValuePerShareDateClass>2026-09-02</dailyNetAssetValuePerShareDateClass>
    </dailyNetAssetValuePerShareClass></classLevelInfo></submission>'''
    assert parse_nmfp_xml(payload, accession_number="a", source_url="u") is None
