import io
import zipfile
from datetime import date

from app.connectors import fi_sweden, gsfm


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
    html = (b'<a href="/FondInnehavLista/download?filnamn=FondInnehav_2026Q3.zip">'
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
    assert sorted(path.name for path in xml_dir.glob("*.xml")) == ["FondInnehav_2026Q3.xml"]
