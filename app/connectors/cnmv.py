"""CNMV monthly Spanish mutual-fund register snapshot (FI entities/classes)."""
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

from app.config import timeout_seconds, user_agent
from app.connectors.base import BaseConnector

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "spain"
REPORTS = ROOT / "reports"
INDEX_URL = "https://www.cnmv.es/portal/Publicaciones/descarga-informacion-individual?ejercicio=2026"


def download_cnmv_fund_register(*, refresh: bool = False) -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / "cnmv_monthly_fund_data.zip"
    downloaded = refresh or not target.exists()
    source_url = INDEX_URL
    period = ""
    if downloaded:
        req = urllib.request.Request(INDEX_URL, headers={"User-Agent": user_agent(), "Accept": "text/html"})
        with urllib.request.urlopen(req, timeout=timeout_seconds()) as response:
            page = response.read().decode("utf-8", errors="replace")
        match = re.search(r'<td\s+data-th="Mes">([^<]+)</td>\s*<td[^>]*>\s*<a[^>]*id="[^"]*lnkZip"[^>]*href="([^"]+)"', page, re.I)
        if not match:
            raise ValueError("CNMV page did not expose a current monthly ZIP archive")
        month_name, source_url = match.groups()
        source_url = source_url.replace("&amp;", "&")
        period = f"2026-{month_name.strip()}"
        req = urllib.request.Request(source_url, headers={"User-Agent": user_agent(), "Accept": "application/zip,*/*"})
        with urllib.request.urlopen(req, timeout=timeout_seconds()) as response:
            payload = response.read()
        if not payload.startswith(b"PK\x03\x04"):
            raise ValueError("CNMV response was not a ZIP archive")
        target.write_bytes(payload)
    payload = target.read_bytes()
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        candidates = [n for n in archive.namelist() if re.fullmatch(r"FONDREGISTRO_\d{6}\.xml", Path(n).name, re.I)]
        if len(candidates) != 1:
            raise ValueError(f"Expected one CNMV fund-register XML, found: {candidates}")
        xml_bytes = archive.read(candidates[0])
        period = Path(candidates[0]).stem.rsplit("_", 1)[-1]
    (RAW / f"FONDREGISTRO_{period}.xml").write_bytes(xml_bytes)
    manifest = {"source_id": "cnmv_spanish_fund_register", "url": source_url,
        "index_url": INDEX_URL, "period": period, "path": str(target.relative_to(ROOT)),
        "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
        "downloaded": downloaded, "checked_at": datetime.now(timezone.utc).isoformat()}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "cnmv_dataset_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


class CnmvFundsConnector(BaseConnector):
    source_id = "cnmv_spanish_fund_register"
    country_code = "ES"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "ES", "organization": "Comisión Nacional del Mercado de Valores",
            "source_name": "Monthly individual CIS data; Spanish FI fund register",
            "endpoint_url": INDEX_URL, "license_status": "Unknown"}

    def _load(self) -> None:
        manifest = download_cnmv_fund_register()
        xml_path = RAW / f"FONDREGISTRO_{manifest['period']}.xml"
        root = ET.parse(xml_path).getroot()
        records: list[dict[str, Any]] = []
        for entity in root.findall("Entidad"):
            if (entity.findtext("Tipo") or "").strip() != "FI":
                continue
            reg_id = (entity.findtext("NumeroRegistro") or "").strip()
            fund_name = (entity.findtext("Denominacion") or "").strip()
            if not reg_id or not fund_name:
                continue
            found_class = False
            for compartment in entity.findall("Compartimento"):
                compartment_id = (compartment.findtext("NumeroCompartimento") or "0").strip()
                compartment_name = (compartment.findtext("DenominacionCompartimento") or "").strip()
                for share_class in compartment.findall("Clase"):
                    class_id = (share_class.findtext("NumeroClase") or "0").strip()
                    class_name = (share_class.findtext("DenominacionClase") or "").strip()
                    isin = (share_class.findtext("ISIN") or "").strip() or None
                    parts = [fund_name]
                    if compartment_id != "0" and compartment_name:
                        parts.append(compartment_name)
                    if class_name:
                        parts.append(class_name)
                    records.append({"source_fund_id": f"{reg_id}:{compartment_id}:{class_id}",
                        "name": " — ".join(parts), "domicile_country": "ES", "currency": None, "isin": isin})
                    found_class = True
            if not found_class:
                records.append({"source_fund_id": reg_id, "name": fund_name,
                    "domicile_country": "ES", "currency": None, "isin": None})
        self._records = records

    def check_availability(self) -> dict[str, Any]:
        self._load()
        return {"available": True, "fund_records": len(self._records or [])}

    def extract_funds(self, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load()
        return iter(self._records or [])
