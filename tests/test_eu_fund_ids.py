import io
import zipfile

from app.enrichment import eu_fund_ids as ids


def _firds_zip(tmp_path):
    xml = ("<BizData xmlns='urn:x'><Pyld><Document><FinInstrmRptgRefDataRpt>"
           "<RefData><FinInstrmGnlAttrbts><Id>LU0000000014</Id><FullNm>Alpha Fund A</FullNm><ClssfctnTp>CIOGEU</ClssfctnTp><NtnlCcy>EUR</NtnlCcy></FinInstrmGnlAttrbts>"
           "<Issr>LEI000000000000000001</Issr><TradgVnRltdAttrbts><Id>XETR</Id><FrstTradDt>2020-05-01T00:00:00Z</FrstTradDt></TradgVnRltdAttrbts></RefData>"
           "<RefData><FinInstrmGnlAttrbts><Id>LU0000000014</Id><FullNm>Alpha Fund A</FullNm><ClssfctnTp>CIOGEU</ClssfctnTp><NtnlCcy>EUR</NtnlCcy></FinInstrmGnlAttrbts>"
           "<Issr>LEI000000000000000001</Issr><TradgVnRltdAttrbts><Id>XPAR</Id><FrstTradDt>2019-01-01T00:00:00Z</FrstTradDt></TradgVnRltdAttrbts></RefData>"
           "<RefData><FinInstrmGnlAttrbts><Id>BADISIN</Id><FullNm>x</FullNm></FinInstrmGnlAttrbts></RefData>"
           "</FinInstrmRptgRefDataRpt></Document></Pyld></BizData>")
    path = tmp_path / "f.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("FULINS_C.xml", xml)
    return path


def test_parse_firds_merges_venues_and_skips_invalid_isins(tmp_path):
    records = ids.parse_firds(_firds_zip(tmp_path))
    assert list(records) == ["LU0000000014"]
    record = records["LU0000000014"]
    assert record["lei"] == "LEI000000000000000001" and record["currency"] == "EUR"
    assert record["venues"] == ["XETR", "XPAR"]
    assert record["first_trade"] == "2019-01-01T00:00:00Z"  # earliest across venues


def test_match_lu_joins_on_lei(tmp_path):
    firds = ids.parse_firds(_firds_zip(tmp_path))
    matched = ids.match_lu([(1, "LEI000000000000000001"), (2, "OTHER"), (3, None)], firds)
    assert list(matched) == [1] and matched[1][0]["isin"] == "LU0000000014"


def test_match_ie_uses_exact_subfund_names_and_ignores_umbrellas():
    funds = [(10, "Lazard Diversified Return Fund"), (11, "Barings Umbrella Fund plc"),
             (12, "Twin Fund"), (13, "Twin Fund")]
    hmrc = [
        {"parent": "Lazard Global Investment Funds Plc", "class_ref": "O1", "sub": "Lazard Diversified Return Fund - AP Acc USD",
         "isin": "IE00B0000001", "reporting_from": "01/01/2020", "ceased": ""},
        {"parent": "Barings Umbrella Fund plc", "class_ref": "O2", "sub": "Barings Umbrella Fund plc", "isin": "IE00B0000002",
         "reporting_from": "", "ceased": ""},
        {"parent": "X", "class_ref": "O3", "sub": "Twin Fund", "isin": "IE00B0000003", "reporting_from": "", "ceased": ""},
        {"parent": "X", "class_ref": "O4", "sub": "Unknown Fund", "isin": "IE00B0000004", "reporting_from": "", "ceased": ""},
    ]
    matched = ids.match_ie(funds, {}, hmrc)
    assert set(matched) == {10}  # umbrella (11) and duplicate-name (12/13) funds are never matched
    assert matched[10]["IE00B0000001"]["attributes"]["parent_fund"] == "Lazard Global Investment Funds Plc"


def test_primary_isin_is_earliest_first_trade_then_lowest():
    items = [{"isin": "LU0000000022", "attributes": {"first_trade": "2021-01-01"}},
             {"isin": "LU0000000014", "attributes": {"first_trade": "2019-01-01"}},
             {"isin": "LU0000000006", "attributes": {}}]
    assert ids._primary_isin(items) == "LU0000000014"


def test_geco_nav_parser_skips_cancelled_points_and_keeps_currency():
    from app.enrichment.geco_nav import parse_nav_rows

    document = {"netAssetValueDTO": [
        {"valuationDate": "2026-11-02", "netAssetValue": 66.9, "assetUnderManagementK": 234058.7, "shareNumber": 3498415.4,
         "quotationCurrency": "EUR", "cancellation": False},
        {"valuationDate": "2026-11-03", "netAssetValue": 66.55, "assetUnderManagementK": 232858.0, "shareNumber": 3498754.4,
         "quotationCurrency": "EUR", "cancellation": False},
        {"valuationDate": "2026-11-04", "netAssetValue": 70.0, "quotationCurrency": "EUR", "cancellation": True},
        {"valuationDate": "2026-11-05", "netAssetValue": None, "quotationCurrency": "EUR", "cancellation": False}]}
    rows, latest = parse_nav_rows(document, 7, None)
    assert [str(r["valuation_date"]) for r in rows] == ["2026-11-02", "2026-11-03"]
    assert all(r["fund_id"] == 7 and r["currency"] == "EUR" for r in rows)
    assert str(latest["date"]) == "2026-11-03" and str(latest["assets_k"]) == "232858.0"


def test_bafin_parse_rows_keeps_german_subfunds_only():
    from app.connectors.de_bafin_funds import parse_rows

    rows = [
        ["70171613", "Alatus UCITS", "Luxemburg", "Umbrella", "", "", "EU-OGAW", "FundPartner", "", ""],
        ["", "Alatus UCITS - Inflection", "Luxemburg", "Teilfonds/-gesellschaftsvermögen", "Alatus UCITS", "17.10.2024", "EU-OGAW", "FundPartner", "", ""],
        ["1001", "Deka Umbrella", "Deutschland", "Umbrella", "", "", "OGAW", "Deka", "", ""],
        ["1002", "Deka Aktien", "Deutschland", "Teilfonds/-gesellschaftsvermögen", "Deka Umbrella", "01.02.2023", "OGAW", "Deka Investment GmbH", "", "DE000A0Q4R28"],
        ["", "Hansa Mix", "Deutschland", "Einzelfonds", "", "bad-date", "Spezial-AIF", "Hansa", "", "XX"],
    ]
    records, rejects = parse_rows(rows)
    by_name = {r["name"]: r for r in records}
    assert set(by_name) == {"Deka Aktien", "Hansa Mix"}  # foreign home state and umbrella shells are skipped
    assert by_name["Deka Aktien"]["isin"] == "DE000A0Q4R28" and by_name["Deka Aktien"]["inception_date"] == "2023-02-01"
    assert by_name["Deka Aktien"]["legal_name"] == "Deka Umbrella" and by_name["Deka Aktien"]["manager"] == "Deka Investment GmbH"
    assert by_name["Hansa Mix"]["isin"] is None and by_name["Hansa Mix"]["inception_date"] is None
    assert rejects == []


def test_bundesanzeiger_daily_file_parses_german_numbers(tmp_path):
    from app.connectors.de_bundesanzeiger import parse_daily_file, german_decimal

    path = tmp_path / "tagesaktuelle_preise_2026-11-17.csv"
    path.write_text('﻿"Fondspreis vom","Fondsname","ISIN","WKN","Investmentgesellschaft","Währung","Rücknahmepreis","Ausgabepreis","NAV"\n'
                    '"2026-11-17","AMUNDI EURO LIQUIDITY","FR0014004701","","Amundi","EUR","11.188,74","11.188,74","11.188,74"\n'
                    '"2026-11-17","BROKEN","","","x","EUR","1","1","1"\n'
                    '"2026-11-17","ZERO","LU0000000014","","x","EUR","0","0","0,00"\n', encoding="utf-8")
    rows = list(parse_daily_file(path))
    assert len(rows) == 1 and str(rows[0]["nav"]) == "11188.74" and rows[0]["isin"] == "FR0014004701"
    assert german_decimal("1.234,5") is not None and german_decimal("abc") is None


def test_bafin_merge_matches_only_unique_names():
    from app.enrichment.bafin_merge import match_by_name

    funds = [(1, "Alpha Aktienfonds"), (2, "Beta Fonds"), (3, "Beta Fonds"), (4, "Gamma")]
    bafin = [{"name": "Alpha Aktienfonds"}, {"name": "Beta Fonds"}, {"name": "Gamma"}, {"name": "Gamma"}]
    assert list(match_by_name(funds, bafin)) == [1]  # duplicates on either side are never merged
