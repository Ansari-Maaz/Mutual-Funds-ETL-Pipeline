"""UK FCA fund register snapshot (fund master only; no NAV data)."""
from __future__ import annotations

import csv
import hashlib
import json
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.config import timeout_seconds, user_agent
from app.connectors.base import BaseConnector

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "united_kingdom"
REPORTS = ROOT / "reports"
URL = "https://www.fca.org.uk/publication/fca/foi2026_01166-annex-a.csv"


def download_fca_fund_register(*, refresh: bool = False) -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / "fca_fund_register.csv"
    downloaded = refresh or not target.exists()
    if downloaded:
        request = urllib.request.Request(URL, headers={"User-Agent": user_agent(), "Accept": "text/csv,*/*"})
        with urllib.request.urlopen(request, timeout=timeout_seconds()) as response:
            payload = response.read()
        if not payload.startswith(b"FRN,Operator Name,PRN,Fund Name"):
            raise ValueError("FCA response did not match the expected fund register CSV")
        target.write_bytes(payload)
    payload = target.read_bytes()
    manifest = {"source_id": "fca_authorised_funds", "url": URL,
        "path": str(target.relative_to(ROOT)), "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(), "downloaded": downloaded,
        "checked_at": datetime.now(timezone.utc).isoformat()}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "fca_dataset_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


class FcaFundsConnector(BaseConnector):
    source_id = "fca_authorised_funds"
    country_code = "GB"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "GB", "organization": "Financial Conduct Authority",
            "source_name": "Authorised and recognised fund register (UK authorised/approved subset)",
            "endpoint_url": URL, "license_status": "Unknown"}

    def _load(self) -> None:
        download_fca_fund_register()
        output: dict[str, dict[str, Any]] = {}
        with (RAW / "fca_fund_register.csv").open("r", encoding="cp1252", newline="") as stream:
            reader = csv.DictReader(stream)
            required = {"PRN", "Fund Name", "Status", "Effective Date"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError(f"Unexpected FCA CSV columns: {reader.fieldnames}")
            for row in reader:
                # FCA says Authorised/Approved are UK-domiciled; Recognised rows
                # are overseas schemes and are deliberately excluded here.
                if row.get("Status", "").strip() not in {"Authorised", "Approved"}:
                    continue
                product_id = (row.get("PRN") or "").strip()
                name = (row.get("Fund Name") or "").strip()
                if not product_id or not name:
                    continue
                output.setdefault(product_id, {"source_fund_id": product_id, "name": name,
                    "domicile_country": "GB", "currency": None, "isin": None,
                    "manager": (row.get("Operator Name") or "").strip() or None,
                    "category": (row.get("Scheme Type") or row.get("Product Type") or "").strip() or None,
                    "fund_type": (row.get("Product Type") or "Mutual fund").strip() or "Mutual fund",
                    "status": row.get("Status", "").strip() or None})
        self._records = list(output.values())

    def check_availability(self) -> dict[str, Any]:
        self._load()
        return {"available": True, "fund_records": len(self._records or [])}

    def extract_funds(self, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load()
        return iter(self._records or [])
