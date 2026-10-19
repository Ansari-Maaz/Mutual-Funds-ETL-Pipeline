"""Open-ended European fund masters from Banco de España's country CSVs."""
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
REPORTS = ROOT / "reports"
BASE_URL = "https://www.bde.es/webbe/en/estadisticas/otras-clasificaciones/clasificacion-entidades/listas-instituciones-financieras/listas-fondos-inversion-pais/lista-if-{country}.csv"
COUNTRIES = {
    "DE": ("germany", "Germany"),
    "IT": ("italy", "Italy"),
    "NL": ("netherlands", "Netherlands"),
    "LU": ("luxembourg", "Luxembourg"),
}


def download_bde_fund_list(country_code: str, *, refresh: bool = False) -> dict[str, Any]:
    country_code = country_code.upper()
    if country_code not in COUNTRIES:
        raise ValueError(f"Unsupported BDE country code: {country_code}")
    folder, _ = COUNTRIES[country_code]
    target = ROOT / "data" / "raw" / folder / f"bde_{country_code.lower()}_nonmonetary_funds.csv"
    downloaded = refresh or not target.exists()
    if downloaded:
        url = BASE_URL.format(country=country_code.lower())
        request = urllib.request.Request(url, headers={"User-Agent": user_agent(), "Accept": "text/csv,*/*"})
        with urllib.request.urlopen(request, timeout=timeout_seconds()) as response:
            payload = response.read()
        if b"EUROPEAN CODE" not in payload[:500] or b"FUND NAME" not in payload[:500]:
            raise ValueError(f"Banco de España response did not match the {country_code} fund CSV")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
    payload = target.read_bytes()
    manifest = {"source_id": f"{country_code.lower()}_bde_nonmonetary_funds",
        "url": BASE_URL.format(country=country_code.lower()), "path": str(target.relative_to(ROOT)),
        "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
        "downloaded": downloaded, "checked_at": datetime.now(timezone.utc).isoformat()}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / f"{country_code.lower()}_bde_dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n")
    return manifest


class BdeEuropeanFundsConnector(BaseConnector):
    country_code: str
    source_id: str

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None
        self._rejects: list[dict[str, str]] = []

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": self.country_code, "organization": "Banco de España",
            "source_name": f"List of non-monetary investment funds in {COUNTRIES[self.country_code][1]}",
            "endpoint_url": BASE_URL.format(country=self.country_code.lower()), "license_status": "Unknown"}

    def _load(self) -> None:
        download_bde_fund_list(self.country_code)
        folder, _ = COUNTRIES[self.country_code]
        path = ROOT / "data" / "raw" / folder / f"bde_{self.country_code.lower()}_nonmonetary_funds.csv"
        records: list[dict[str, Any]] = []
        rejects: list[dict[str, str]] = []
        seen: set[str] = set()
        with path.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.reader(stream)
            header = next(reader, [])
            if len(header) < 7 or not header[0].strip().startswith("EUROPEAN CODE"):
                raise ValueError(f"Unexpected BDE CSV header: {header[:7]}")
            for row in reader:
                # The source pads each row with a very wide empty column.
                row = (row + [""] * 7)[:7]
                code, lei, name, manager, address, policy, capital = (value.strip() for value in row)
                if not code or not name or code in seen:
                    if code or name:
                        rejects.append({"source_fund_id": code, "reason": "missing code/name or duplicate source code"})
                    continue
                seen.add(code)
                if capital.casefold() != "open-ended":
                    continue
                records.append({"source_fund_id": code, "name": name,
                    "domicile_country": self.country_code, "currency": None,
                    "isin": None, "_navs": []})
        if not records:
            raise ValueError(f"No open-ended funds parsed for {self.country_code}")
        self._records, self._rejects = records, rejects
        (REPORTS / f"{self.country_code.lower()}_bde_rejected_records.jsonl").write_text(
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


class BdeGermanyConnector(BdeEuropeanFundsConnector):
    country_code = "DE"
    source_id = "de_bde_nonmonetary_funds"


class BdeItalyConnector(BdeEuropeanFundsConnector):
    country_code = "IT"
    source_id = "it_bde_nonmonetary_funds"


class BdeNetherlandsConnector(BdeEuropeanFundsConnector):
    country_code = "NL"
    source_id = "nl_bde_nonmonetary_funds"


class BdeLuxembourgConnector(BdeEuropeanFundsConnector):
    country_code = "LU"
    source_id = "lu_bde_nonmonetary_funds"
