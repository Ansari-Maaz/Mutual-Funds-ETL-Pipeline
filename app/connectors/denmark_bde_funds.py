"""Danish open-ended fund master from Banco de España's official CSV list."""
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
RAW = ROOT / "data" / "raw" / "denmark"
REPORTS = ROOT / "reports"
URL = "https://www.bde.es/webbe/en/estadisticas/otras-clasificaciones/clasificacion-entidades/listas-instituciones-financieras/listas-fondos-inversion-pais/lista-if-dk.csv"


def download_denmark_fund_list(*, refresh: bool = False) -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / "bde_denmark_non_monetary_funds.csv"
    downloaded = refresh or not target.exists()
    if downloaded:
        request = urllib.request.Request(URL, headers={"User-Agent": user_agent(), "Accept": "text/csv,*/*"})
        with urllib.request.urlopen(request, timeout=timeout_seconds()) as response:
            payload = response.read()
        if b"EUROPEAN CODE" not in payload[:500] or b"FUND NAME" not in payload[:500]:
            raise ValueError("Banco de España response did not match the Danish fund CSV")
        target.write_bytes(payload)
    payload = target.read_bytes()
    manifest = {"source_id": "dk_bde_nonmonetary_funds", "url": URL,
        "path": str(target.relative_to(ROOT)), "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(), "downloaded": downloaded,
        "checked_at": datetime.now(timezone.utc).isoformat()}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "denmark_dataset_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


class DenmarkBdeFundsConnector(BaseConnector):
    source_id = "dk_bde_nonmonetary_funds"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None
        self._rejects: list[dict[str, str]] = []

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "DK", "organization": "Banco de España",
            "source_name": "List of non-monetary investment funds in Denmark",
            "endpoint_url": URL, "license_status": "Unknown"}

    def _load(self) -> None:
        download_denmark_fund_list()
        rows: list[dict[str, Any]] = []
        rejects: list[dict[str, str]] = []
        seen: set[str] = set()
        with (RAW / "bde_denmark_non_monetary_funds.csv").open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream)
            header = next(reader, [])
            if len(header) < 7 or not header[0].strip().startswith("EUROPEAN CODE"):
                raise ValueError(f"Unexpected Danish fund CSV header: {header[:7]}")
            for row in reader:
                # The source appends a very wide blank column. The first seven
                # columns are the published fields used by its web table.
                row = (row + [""] * 7)[:7]
                code, lei, name, manager, address, policy, capital = (value.strip() for value in row)
                if not code.startswith("DKFT") or not name or code in seen:
                    if any((code, name)):
                        rejects.append({"source_fund_id": code, "reason": "missing Danish fund code/name or duplicate"})
                    continue
                seen.add(code)
                # This is a broader non-monetary investment-fund register. Keep
                # only open-ended vehicles; record source-native classification
                # in the name suffix only when available, without guessing NAV.
                if capital.casefold() != "open-ended":
                    continue
                rows.append({"source_fund_id": code, "name": name,
                    "domicile_country": "DK", "currency": None, "isin": None, "_navs": []})
        if not rows:
            raise ValueError("No open-ended Danish fund rows were found in the official CSV")
        self._records, self._rejects = rows, rejects
        (REPORTS / "denmark_rejected_records.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rejects))

    def check_availability(self) -> dict[str, Any]:
        self._load()
        return {"available": True, "fund_records": len(self._records or []),
            "rejected_records": len(self._rejects)}

    def extract_funds(self, start_date: date | None = None,
                      end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load()
        return iter(self._records or [])
