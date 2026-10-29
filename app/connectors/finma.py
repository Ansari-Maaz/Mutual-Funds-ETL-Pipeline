"""FINMA approved Swiss collective investment schemes fund-list connector."""
from __future__ import annotations

import hashlib
import json
import logging
import re
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from pypdf import PdfReader

from app.config import timeout_seconds, user_agent
from app.connectors.base import BaseConnector

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "switzerland"
REPORTS = ROOT / "reports"
URL = "https://www.finma.ch/~/media/finma/dokumente/bewilligungstraeger/pdf/afch.pdf?la=en%3BApproved"
ID_PATTERN = re.compile(r"F\d{8}")


def download_finma_fund_list(*, refresh: bool = False) -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / "finma_approved_swiss_funds.pdf"
    downloaded = refresh or not target.exists()
    if downloaded:
        request = urllib.request.Request(URL, headers={"User-Agent": user_agent(), "Accept": "application/pdf,*/*"})
        with urllib.request.urlopen(request, timeout=timeout_seconds()) as response:
            payload = response.read()
        if not payload.startswith(b"%PDF"):
            raise ValueError("FINMA response is not a PDF file")
        target.write_bytes(payload)
    payload = target.read_bytes()
    manifest = {"source_id": "finma_swiss_fund_list", "url": URL,
        "path": str(target.relative_to(ROOT)), "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(), "downloaded": downloaded,
        "checked_at": datetime.now(timezone.utc).isoformat()}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "finma_dataset_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


class FinmaConnector(BaseConnector):
    source_id = "finma_swiss_fund_list"
    country_code = "CH"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None
        self._rejects: list[dict[str, Any]] = []

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "CH", "organization": "Swiss Financial Market Supervisory Authority (FINMA)",
            "source_name": "Approved Swiss collective investment schemes", "endpoint_url": URL,
            "license_status": "Unknown"}

    def _load(self) -> None:
        download_finma_fund_list()
        # The official landscape PDF is a 150-page table. Layout mode preserves
        # its name and FINMA-ID columns; suppress pypdf's warnings about the
        # rotated classification matrix elsewhere on each page.
        logging.getLogger("pypdf._text_extraction").setLevel(logging.ERROR)
        reader = PdfReader(RAW / "finma_approved_swiss_funds.pdf")
        records: list[dict[str, Any]] = []
        self._rejects = []
        seen: set[str] = set()
        for page_number, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text(extraction_mode="layout") or ""
            for line_number, line in enumerate(page_text.splitlines(), start=1):
                match = ID_PATTERN.search(line)
                if not match:
                    continue
                fund_id = match.group(0)
                prefix = line[:match.start()].strip()
                # FINMA's table has a separate umbrella column. Keep only the
                # individual fund/sub-fund name before that column.
                name = re.split(r"\s{2,}", prefix, maxsplit=1)[0].strip()
                if not name or fund_id in seen:
                    self._rejects.append({"page": page_number, "line": line_number,
                        "finma_id": fund_id, "reason": "missing name or duplicate FINMA ID"})
                    continue
                seen.add(fund_id)
                records.append({"source_fund_id": fund_id, "name": name,
                    "domicile_country": "CH", "currency": None, "isin": None, "_navs": []})
        if not records:
            raise ValueError("FINMA PDF parser found no fund rows; preserve the raw file and inspect the table layout")
        self._records = records
        (REPORTS / "finma_rejected_records.jsonl").write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in self._rejects))

    def check_availability(self) -> dict[str, Any]:
        self._load()
        return {"available": True, "fund_records": len(self._records or []), "rejected_records": len(self._rejects)}

    def extract_funds(self, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load()
        return iter(self._records or [])

    def extract_nav_history(self, source_fund_id: str, start_date: date | None = None,
                            end_date: date | None = None) -> Iterable[dict[str, Any]]:
        return ()
