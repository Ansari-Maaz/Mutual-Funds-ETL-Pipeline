"""Swedish FI quarterly UCITS XML snapshot (fund master only)."""
from __future__ import annotations

import hashlib
import io
import json
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import quote

from app.config import timeout_seconds, user_agent
from app.connectors.base import BaseConnector

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "sweden"
REPORTS = ROOT / "reports"
INDEX_URL = "https://www.fi.se/en/our-registers/quarterly-fund-holdings/?navigation=open"


def download_fi_sweden(*, refresh: bool = False) -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / "fi_quarterly_fund_holdings.zip"
    downloaded = refresh or not target.exists()
    source_url = ""
    period = ""
    if downloaded:
        req = urllib.request.Request(INDEX_URL, headers={"User-Agent": user_agent(), "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=timeout_seconds()) as response:
            page = response.read().decode("utf-8", errors="replace")
        match = re.search(r'href="([^"]*FondInnehavLista/download\?filnamn=Fondinnehav_[^"]+\.zip)"[^>]*>\s*Fondinnehav\s+(\d{4}Q\d)', page, re.I)
        if not match:
            raise ValueError("FI Sweden page did not expose a quarterly holdings archive")
        source_url, period = match.groups()
        source_url = quote("https://www.fi.se" + source_url.replace("&amp;", "&"), safe=":/?=&%")
        req = urllib.request.Request(source_url, headers={"User-Agent": user_agent(), "Accept": "application/zip,*/*"})
        with urllib.request.urlopen(req, timeout=timeout_seconds()) as response:
            payload = response.read()
        if not payload.startswith(b"PK\x03\x04"):
            raise ValueError("FI Sweden response was not a ZIP archive")
        target.write_bytes(payload)
    payload = target.read_bytes()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        period_files = [n for n in archive.namelist() if period in n and n.lower().endswith(".xml")]
        if not period_files:
            period_files = [n for n in archive.namelist() if n.lower().endswith(".xml")]
        xml_dir = RAW / "xml"
        xml_dir.mkdir(exist_ok=True)
        # Remove the previous period before extracting this archive so stale
        # quarter files cannot be merged into the current fund list.
        for old_xml in xml_dir.glob("*.xml"):
            old_xml.unlink()
        for name in period_files:
            target_xml = xml_dir / (Path(name).name.encode("ascii", "ignore").decode() or "fund.xml")
            target_xml.write_bytes(archive.read(name))
    manifest = {"source_id": "fi_sweden_ucits_holdings", "url": source_url or INDEX_URL,
        "index_url": INDEX_URL, "period": period, "path": str(target.relative_to(ROOT)),
        "files_extracted": len(period_files), "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(), "downloaded": downloaded,
        "checked_at": datetime.now(timezone.utc).isoformat()}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "fi_sweden_dataset_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


class FiSwedenConnector(BaseConnector):
    source_id = "fi_sweden_ucits_holdings"
    country_code = "SE"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "SE", "organization": "Finansinspektionen",
            "source_name": "Quarterly UCITS fund holdings (identity fields)",
            "endpoint_url": INDEX_URL, "license_status": "Unknown"}

    def _load(self) -> None:
        download_fi_sweden()
        output: dict[str, dict[str, Any]] = {}
        for path in sorted((RAW / "xml").glob("*.xml")):
            try:
                root = ET.parse(path).getroot()
            except ET.ParseError:
                continue
            ns = {"fi": root.tag.split("}")[0].lstrip("{")} if "}" in root.tag else {}
            def value(parent, tag):
                node = parent.find(f"fi:{tag}", ns) if ns else parent.find(tag)
                return (node.text or "").strip() if node is not None and node.text else ""
            fund = root.find("fi:Fondinformation", ns) if ns else root.find("Fondinformation")
            if fund is None:
                continue
            fund_id = value(fund, "Fond_institutnummer")
            name = value(fund, "Fond_namn")
            isin = value(fund, "Fond_ISIN-kod") or None
            if not fund_id or not name:
                continue
            output.setdefault(fund_id, {"source_fund_id": fund_id, "name": name,
                "domicile_country": "SE", "currency": None, "isin": isin})
        self._records = list(output.values())

    def check_availability(self) -> dict[str, Any]:
        self._load()
        return {"available": True, "fund_records": len(self._records or [])}

    def extract_funds(self, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load()
        return iter(self._records or [])
