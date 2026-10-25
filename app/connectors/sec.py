"""SEC registered open-end mutual-fund series/share-class snapshot."""
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
RAW = ROOT / "data" / "raw" / "united_states"
REPORTS = ROOT / "reports"
URL = "https://www.sec.gov/files/investment/data/other/investment-company-series-class-information/investment-company-series-class-2026.csv"


def download_sec_series_classes(*, refresh: bool = False) -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / "sec_series_classes.csv"
    downloaded = refresh or not target.exists()
    if downloaded:
        request = urllib.request.Request(URL, headers={"User-Agent": user_agent(), "Accept": "text/csv,*/*"})
        with urllib.request.urlopen(request, timeout=timeout_seconds()) as response:
            payload = response.read()
        if b"Entity Org Type,Series ID,Series Name,Class ID" not in payload[:1000]:
            raise ValueError("SEC response did not match the expected series/class CSV")
        target.write_bytes(payload)
    payload = target.read_bytes()
    manifest = {"source_id": "sec_open_end_fund_classes", "url": URL,
        "path": str(target.relative_to(ROOT)), "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(), "downloaded": downloaded,
        "checked_at": datetime.now(timezone.utc).isoformat()}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "sec_dataset_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


class SecFundsConnector(BaseConnector):
    source_id = "sec_open_end_fund_classes"
    country_code = "US"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "US", "organization": "U.S. Securities and Exchange Commission",
            "source_name": "Investment Company Series and Class Information (Form N-1A subset)",
            "endpoint_url": URL, "license_status": "Unknown"}

    def _load(self) -> None:
        download_sec_series_classes()
        output: dict[str, dict[str, Any]] = {}
        with (RAW / "sec_series_classes.csv").open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            required = {"Entity Org Type", "Series ID", "Series Name", "Class ID", "Class Name"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError(f"Unexpected SEC CSV columns: {reader.fieldnames}")
            for row in reader:
                # Type 30 identifies Form N-1A open-end mutual fund filers.
                if (row.get("Entity Org Type") or "").strip() != "30":
                    continue
                class_id = (row.get("Class ID") or "").strip()
                series_name = (row.get("Series Name") or "").strip()
                class_name = (row.get("Class Name") or "").strip()
                if not class_id or not (series_name or class_name):
                    continue
                name = f"{series_name} — {class_name}" if series_name and class_name and series_name != class_name else (series_name or class_name)
                output.setdefault(class_id, {"source_fund_id": class_id, "name": name,
                    "legal_name": class_name or series_name,
                    "domicile_country": "US", "currency": "USD", "isin": None,
                    "provider": (row.get("Entity Name") or "").strip() or None,
                    "manager": (row.get("Entity Name") or "").strip() or None,
                    "fund_type": "Open-end mutual fund",
                    "status": "Registered",
                    "ticker": (row.get("Class Ticker") or "").strip() or None,
                    "official_url": URL})
        self._records = list(output.values())

    def check_availability(self) -> dict[str, Any]:
        self._load()
        return {"available": True, "fund_records": len(self._records or [])}

    def extract_funds(self, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load()
        return iter(self._records or [])
