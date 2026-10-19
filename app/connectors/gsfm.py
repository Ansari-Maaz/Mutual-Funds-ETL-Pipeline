"""GSFM official combined unit prices; ingest only currency-explicit rows."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import urllib.request
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from app.config import timeout_seconds, user_agent
from app.connectors.base import BaseConnector

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "australia"
REPORTS = ROOT / "reports"
URL = "https://www.gsfm.com.au/funds-data/combined-unit-prices/?export=csv"


def download_gsfm_prices(*, refresh: bool = False) -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / "gsfm_unit_prices.csv"
    downloaded = refresh or not target.exists()
    if downloaded:
        request = urllib.request.Request(URL, headers={"User-Agent": user_agent(), "Accept": "text/csv,*/*"})
        with urllib.request.urlopen(request, timeout=timeout_seconds()) as response:
            payload = response.read()
        if not payload.startswith(b"fund,code,as_at_date,nav_price"):
            raise ValueError("GSFM response did not match the expected unit-price CSV")
        target.write_bytes(payload)
    payload = target.read_bytes()
    manifest = {"source_id": "gsfm_unit_prices", "url": URL,
        "path": str(target.relative_to(ROOT)), "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(), "downloaded": downloaded,
        "checked_at": datetime.now(timezone.utc).isoformat()}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "gsfm_dataset_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


class GsfmConnector(BaseConnector):
    source_id = "gsfm_unit_prices"
    country_code = "AU"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None
        self._rejects: list[dict[str, str]] = []

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "AU", "organization": "Global Select Funds Management Limited (GSFM)",
            "source_name": "Combined Australian unit prices", "endpoint_url": URL,
            "license_status": "Unknown"}

    def _load(self, start_date: date | None = None, end_date: date | None = None) -> None:
        download_gsfm_prices()
        output: dict[str, dict[str, Any]] = {}
        self._rejects = []
        with (RAW / "gsfm_unit_prices.csv").open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            required = {"fund", "code", "as_at_date", "nav_price"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError(f"Unexpected GSFM CSV columns: {reader.fieldnames}")
            for row in reader:
                code = (row.get("code") or "").strip()
                name = (row.get("fund") or "").strip()
                # GSFM's combined export spans fund classes and currencies. Only
                # accept rows whose published name states the denomination.
                if "(AUD)" not in name:
                    self._rejects.append({"code": code, "reason": "currency not explicit in source fund name"})
                    continue
                try:
                    valuation_date = date.fromisoformat(row["as_at_date"])
                    nav = Decimal(row["nav_price"])
                except (ValueError, InvalidOperation, TypeError):
                    self._rejects.append({"code": code, "reason": "invalid valuation date or NAV"})
                    continue
                if start_date and valuation_date < start_date: continue
                if end_date and valuation_date > end_date: continue
                if not nav.is_finite() or nav <= 0 or not code or not name:
                    self._rejects.append({"code": code, "reason": "invalid code, name, or non-positive NAV"})
                    continue
                fund = output.setdefault(code, {"source_fund_id": code, "name": name,
                    "domicile_country": "AU", "currency": "AUD", "isin": None, "_navs": []})
                fund["_navs"].append({"source_fund_id": code, "valuation_date": valuation_date.isoformat(),
                    "nav": str(nav), "currency": "AUD"})
        self._records = list(output.values())
        (REPORTS / "gsfm_rejected_records.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in self._rejects))

    def check_availability(self) -> dict[str, Any]:
        self._load()
        return {"available": True, "fund_records": len(self._records or []), "rejected_records": len(self._rejects)}

    def extract_funds(self, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load(start_date, end_date)
        return iter(self._records or [])

    def extract_nav_history(self, source_fund_id: str, start_date: date | None = None,
                            end_date: date | None = None) -> Iterable[dict[str, Any]]:
        return ()
