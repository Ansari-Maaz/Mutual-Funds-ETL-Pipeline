"""SFC-authorised unit trusts and mutual funds offered to the public in HK."""
from __future__ import annotations

import hashlib
import html
import json
import re
import urllib.request
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

from app.config import timeout_seconds, user_agent
from app.connectors.base import BaseConnector

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "hong_kong"
REPORTS = ROOT / "reports"
URL = "https://apps.sfc.hk/productlistWeb/searchProduct/UTMF.do?lang=EN"


class _ProductTableParser(HTMLParser):
    """Extract the SFC product-list table without a third-party HTML parser."""
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.table_index = -1
        self.in_target = False
        self.in_row = False
        self.in_cell = False
        self.rows: list[list[str]] = []
        self.row: list[str] = []
        self.cell: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self.table_index += 1
            if self.table_index == 1:
                self.in_target = True
        elif self.in_target and tag == "tr":
            self.in_row, self.row = True, []
        elif self.in_target and self.in_row and tag in {"td", "th"}:
            self.in_cell, self.cell = True, []
        elif self.in_target and self.in_cell and tag == "br":
            self.cell.append(" ")

    def handle_endtag(self, tag: str) -> None:
        if self.in_target and tag in {"td", "th"} and self.in_cell:
            self.row.append(" ".join("".join(self.cell).split()))
            self.in_cell = False
        elif self.in_target and tag == "tr" and self.in_row:
            if self.row:
                self.rows.append(self.row)
            self.in_row = False
        elif tag == "table" and self.in_target:
            self.in_target = False

    def handle_data(self, data: str) -> None:
        if self.in_cell:
            self.cell.append(data)


def download_hk_sfc_fund_list(*, refresh: bool = False) -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / "sfc_unit_trusts_mutual_funds.html"
    downloaded = refresh or not target.exists()
    if downloaded:
        request = urllib.request.Request(URL, headers={"User-Agent": user_agent(), "Accept": "text/html,*/*"})
        with urllib.request.urlopen(request, timeout=timeout_seconds()) as response:
            payload = response.read()
        if b"Product (CE No.)" not in payload or b"Sub-fund" not in payload:
            raise ValueError("SFC response did not match the unit-trust/mutual-fund product list")
        target.write_bytes(payload)
    payload = target.read_bytes()
    manifest = {"source_id": "hk_sfc_authorised_unit_trusts", "url": URL,
        "path": str(target.relative_to(ROOT)), "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(), "downloaded": downloaded,
        "checked_at": datetime.now(timezone.utc).isoformat()}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "hong_kong_dataset_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


class HkSfcFundsConnector(BaseConnector):
    source_id = "hk_sfc_authorised_unit_trusts"
    country_code = "HK"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None
        self._rejects: list[dict[str, str]] = []

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "HK", "organization": "Securities and Futures Commission of Hong Kong",
            "source_name": "SFC-authorised unit trusts and mutual funds for public offering",
            "endpoint_url": URL, "license_status": "Unknown"}

    def _load(self) -> None:
        download_hk_sfc_fund_list()
        parser = _ProductTableParser()
        parser.feed((RAW / "sfc_unit_trusts_mutual_funds.html").read_text(encoding="utf-8", errors="replace"))
        records: dict[str, dict[str, Any]] = {}
        rejects: list[dict[str, str]] = []
        # Columns: product (CE number), sub-fund (CE number), issuer, date, docs, derivative status.
        for row in parser.rows[1:]:
            if len(row) < 3:
                continue
            product, subfund, issuer = row[:3]
            target = subfund or product
            match = re.search(r"\(([A-Za-z0-9]+)\)", target)
            if not match:
                rejects.append({"product": product, "subfund": subfund, "reason": "no SFC CE number"})
                continue
            code = match.group(1).upper()
            name = re.sub(r"\s*\([A-Za-z0-9]+\)\s*$", "", target).strip()
            if not name:
                rejects.append({"source_fund_id": code, "reason": "missing product name"})
                continue
            record = records.get(code)
            if record and record["name"] != name:
                rejects.append({"source_fund_id": code, "reason": "duplicate CE number with conflicting names"})
                continue
            records.setdefault(code, {"source_fund_id": code, "name": name,
                # The source lists public-offer authorization, not product domicile.
                "domicile_country": None, "currency": None, "isin": None, "_navs": []})
        if not records:
            raise ValueError("No SFC fund product rows parsed; inspect the downloaded HTML snapshot")
        self._records, self._rejects = list(records.values()), rejects
        (REPORTS / "hong_kong_rejected_records.jsonl").write_text(
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
