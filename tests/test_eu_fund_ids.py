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
