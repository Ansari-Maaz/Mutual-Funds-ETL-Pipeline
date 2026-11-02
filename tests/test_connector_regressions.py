import io
import zipfile
from datetime import date
import datetime as datetime_module
from urllib.error import HTTPError

from app.connectors import cvm, fi_sweden, gsfm


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
