import io
import zipfile
from datetime import date
import datetime as datetime_module
from urllib.error import HTTPError

from app.connectors import cvm, fi_sweden, gsfm
from app.holdings.sec_nport import parse_nport_xml


def test_gsfm_availability_does_not_cache_unfiltered_rows(tmp_path, monkeypatch):
    raw_dir = tmp_path / "raw"
    reports = tmp_path / "reports"
    raw_dir.mkdir()
    reports.mkdir()
    (raw_dir / "gsfm_unit_prices.csv").write_text(
        "fund,code,as_at_date,nav_price\n"
        "Example Fund (AUD),EX,2026-10-14,1.25\n"
        "Example Fund (AUD),EX,2026-10-15,1.30\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(gsfm, "RAW", raw_dir)
    monkeypatch.setattr(gsfm, "REPORTS", reports)
    monkeypatch.setattr(gsfm, "download_gsfm_prices", lambda: {"sha256": "test"})

    connector = gsfm.GsfmConnector()
    assert connector.check_availability()["available"] is True
    rows = list(connector.extract_funds(start_date=date(2030, 1, 1)))
    assert rows == []


def test_sweden_refresh_removes_xml_from_old_quarters(tmp_path, monkeypatch):
    raw = tmp_path / "sweden"
    reports = tmp_path / "reports"
    xml_dir = raw / "xml"
    xml_dir.mkdir(parents=True)
    reports.mkdir()
    (xml_dir / "stale-2026Q2.xml").write_text("<old />", encoding="utf-8")

    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("FondInnehav_2026Q3.xml", "<Fondinformation />")
    archive_bytes = archive_buffer.getvalue()
    html = (b'<a href="/FondInnehavLista/download?filnamn=FondInnehav_2026Q3_2026-10-14 08.12.zip">'
            b"Fondinnehav 2026Q3</a>")

    class Response:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def read(self):
            return self.payload

    responses = iter([Response(html), Response(archive_bytes)])
    monkeypatch.setattr(fi_sweden, "RAW", raw)
    monkeypatch.setattr(fi_sweden, "ROOT", tmp_path)
    monkeypatch.setattr(fi_sweden, "REPORTS", reports)
    monkeypatch.setattr(fi_sweden.urllib.request, "urlopen", lambda *_args, **_kwargs: next(responses))

    manifest = fi_sweden.download_fi_sweden(refresh=True)
    assert manifest["period"] == "2026Q3"
    assert manifest["url"].endswith("filnamn=FondInnehav_2026Q3_2026-10-14%2008.12.zip")
    assert sorted(path.name for path in xml_dir.glob("*.xml")) == ["FondInnehav_2026Q3.xml"]


def test_cvm_current_month_404_falls_back_to_latest_published_month(tmp_path, monkeypatch):
    raw = tmp_path / "cvm"
    reports = tmp_path / "reports"
    monkeypatch.setattr(cvm, "RAW", raw)
    monkeypatch.setattr(cvm, "ROOT", tmp_path)
    monkeypatch.setattr(cvm, "REPORTS", reports)
    class FrozenDateTime(datetime_module.datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 11, 2, tzinfo=tz or datetime_module.timezone.utc)

    monkeypatch.setattr(cvm, "datetime", FrozenDateTime)
    downloaded = []

    def fake_download(url, destination):
        downloaded.append(url)
        if "202611" in url:
            raise HTTPError(url, 404, "Not Found", {}, None)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(b"archive")

    monkeypatch.setattr(cvm, "_download", fake_download)
    monkeypatch.setattr(cvm, "_sha256", lambda _path: "hash")
    monkeypatch.setattr(cvm, "REGISTRY_URL", "https://example.test/registry")
    monkeypatch.setattr(cvm, "CURRENT_CAD_URL", "https://example.test/current")

    rows = cvm.download_cvm_data()
    assert "202611" in downloaded[0]
    assert "202610" in downloaded[1]
    assert rows[0]["path"].endswith("inf_diario_fi_202610.zip")
    assert cvm._downloaded_months(rows) == ["202610"]


def test_nport_parser_preserves_series_level_net_assets_and_holdings():
    payload = b"""<edgarSubmission><formData><genInfo>
      <seriesId>S000002839</seriesId><repPdDate>2026-06-30</repPdDate>
      <netAssets>1671231561960.14</netAssets>
    </genInfo><invstOrSec><name>Example issuer</name><cusip>123456789</cusip>
      <balance>10</balance><valUSD>1000</valUSD><pctVal>0.25</pctVal>
    </invstOrSec></formData></edgarSubmission>"""
    parsed = parse_nport_xml(payload, accession_number="0000036405-26-000473",
                             source_url="https://www.sec.gov/Archives/example.txt")
    assert parsed is not None
    assert parsed["series_id"] == "S000002839"
    assert parsed["report_date"] == date(2026, 6, 30)
    assert str(parsed["net_assets"]) == "1671231561960.14"
    assert parsed["holdings"][0]["security_name"] == "Example issuer"
    assert str(parsed["holdings"][0]["portfolio_weight"]) == "0.25"


def test_sec_class_master_exposes_official_share_class_and_registrant_fields():
    from app.connectors.sec import URL, _fund_record_from_row

    record = _fund_record_from_row({
        "Entity Org Type": "30", "Reporting File Number": "033-12345",
        "CIK Number": "0000123456", "Entity Name": "Example Registrant",
        "Series ID": "S000000123", "Series Name": "Example Fund",
        "Class ID": "C000000456", "Class Name": "Investor Shares",
        "Class Ticker": "EXIVX", "Address_1": "100 Main Street",
        "City": "New York", "State": "NY", "Zip Code": "10001",
    })

    assert record is not None
    assert record["ticker"] == "EXIVX"
    assert record["isin"] is None
    summary = record["profile_data"]["summary"]
    assert summary["share_class"] == "Investor Shares"
    assert summary["class_id"] == "C000000456"
    assert summary["series_id"] == "S000000123"
    assert summary["registrant_name"] == "Example Registrant"
    assert summary["registrant_address"] == {
        "address_1": "100 Main Street", "city": "New York", "state": "NY", "postal_code": "10001"
    }
    assert summary["identifier_note"] == "SEC class master does not provide ISIN or CUSIP"
    assert record["profile_source_url"] == URL


def test_sec_class_profile_snapshot_key_is_stable():
    from app.holdings.sec_class_profiles import _snapshot_key

    payload = {"share_class": "Investor Shares", "class_id": "C000000456"}
    assert _snapshot_key(payload) == _snapshot_key(dict(reversed(list(payload.items()))))


def test_sec_class_master_ignores_non_open_end_org_types():
    from app.connectors.sec import _fund_record_from_row

    assert _fund_record_from_row({
        "Entity Org Type": "32", "Series ID": "S000000123",
        "Series Name": "Separate Account", "Class ID": "C000000456",
    }) is None


def test_vanguard_profile_parser_keeps_source_fields_and_precision():
    from scripts.sync_vanguard_profiles import parse_vanguard_product_page

    html = '''<script type="application/ld+json">{"@graph":[
      {"@type":"Organization","@id":"https://vanguard.test/#org","name":"The Vanguard Group"},
      {"@type":"FinancialProduct","name":"Example Admiral (VFIAX)","url":"https://vanguard.test/vfiax",
       "provider":{"@id":"https://vanguard.test/#org"},"description":"Objective text",
       "category":["Mutual fund","Large Blend"],"dateIssued":"2000-11-13",
       "feesAndCommissionsSpecification":"Expense ratio: 0.04% (as of 2026-04-28).",
       "identifier":[{"propertyID":"Ticker","value":"VFIAX"},{"propertyID":"CUSIP","value":"922908710"}],
       "additionalProperty":[{"name":"Benchmark","value":"S&P 500 Index"},
         {"name":"Net assets","value":"USD 677.1B (as of 2026-10-31)"}]}
    ]}</script>'''
    result = parse_vanguard_product_page(html, ticker="VFIAX", page_url="https://vanguard.test/vfiax")
    assert result["provider"] == "The Vanguard Group"
    assert result["cusip"] == "922908710"
    assert result["expense_ratio"]["reported_value"] == "0.04%"
    assert result["net_assets"]["displayed_amount_usd"] == "677100000000.0"
    assert "rounded" in result["net_assets"]["precision"]


def test_vanguard_profile_parser_reads_dated_published_performance_and_risk():
    from scripts.sync_vanguard_profiles import parse_vanguard_product_page

    html = '''<script type="application/ld+json">{"@type":"FinancialProduct","name":"Example Admiral",
      "url":"https://vanguard.test/vfiax","category":["Mutual fund","Large Blend"],
      "dateIssued":"2000-11-13","identifier":[{"propertyID":"Ticker","value":"VFIAX"}]}</script>
      <script>window.__INITIAL_FUND_DATA__ = {"portId":"0540","fundIdentifier":"VFIAX","isMutualFund":true,"isETF":false};</script>
      <script>window.__FEES_AND_EXPENSE__ = {"adjustedExpenseRatio":{"value":"0.04","effectiveDate":"2026-04-28"},"purchaseFee":"","redemptionFee":""};</script>
      <script>window.__MANAGED_ASSETS__ = {"fundNetAssetsData":{"effectiveDate":"2026-10-31","amount":677080852387.99}};</script>
      <script>window.__HERO_STATS__ = {"ytdReturn":{"value":11.5,"effectiveDate":"2026-11-03"},"oneYearReturn":{"value":12.0,"effectiveDate":"2026-10-31"},"threeYearStandardDeviation":{"value":"12.4","effectiveDate":"2026-09-30"},"dividendYield":{"value":"1.05","effectiveDate":"2026-09-30"}};</script>'''
    result = parse_vanguard_product_page(html, ticker="VFIAX", page_url="https://vanguard.test/vfiax")
    assert result["expense_ratio"]["reported_value"] == "0.04"
    assert result["expense_ratio"]["unit"] == "percent"
    assert result["net_assets"]["amount"] == "677080852387.99"
    assert result["net_assets"]["effective_date"] == "2026-10-31"
    assert result["performance"]["ytdReturn"]["value"] == 11.5
    assert result["performance"]["oneYearReturn"]["effective_date"] == "2026-10-31"
    assert result["risk"]["three_year_standard_deviation"]["value"] == "12.4"
    assert result["dividend_yield"]["value"] == "1.05"
    assert result["provider_instrument_flags"] == {"isETF": False, "isMutualFund": True}
