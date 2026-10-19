"""Central Bank of Ireland authorised UCITS register PDF (fund master)."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx
from pypdf import PdfReader

from app.config import timeout_seconds, user_agent
from app.connectors.base import BaseConnector

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "ireland"
REPORTS = ROOT / "reports"
URL = "https://registers.centralbank.ie/downloadspage.aspx"
DATE_RE = re.compile(r"^\d{1,2}[ -](?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*[ -]\d{2,4}$", re.I)


def download_ireland_ucits_register(*, refresh: bool = False) -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / "central_bank_authorised_ucits.pdf"
    downloaded = refresh or not target.exists()
    checked_at = datetime.now(timezone.utc).isoformat()
    if downloaded:
        headers = {"User-Agent": user_agent()}
        with httpx.Client(follow_redirects=True, timeout=timeout_seconds(), headers=headers) as client:
            response = client.get(URL)
            response.raise_for_status()
            html = response.text
            match = re.search(r"__doPostBack\('([^']*cphRegistersMasterPage\$ctl\d+)',''\)\"><span[^>]*>Authorised UCITS, European Communities", html, re.I)
            if not match:
                raise ValueError("Central Bank page did not expose its authorised UCITS PDF download control")
            hidden = {}
            for tag in re.findall(r"<input\b[^>]*>", html, re.I):
                if not re.search(r'type="hidden"', tag, re.I):
                    continue
                name_match = re.search(r'name="([^"]+)"', tag, re.I)
                value_match = re.search(r'value="([^"]*)"', tag, re.I)
                if name_match:
                    hidden[name_match.group(1)] = value_match.group(1) if value_match else ""
            hidden["__EVENTTARGET"] = match.group(1)
            hidden["__EVENTARGUMENT"] = ""
            response = client.post(URL, data=hidden, headers={"Referer": URL})
            response.raise_for_status()
            if not response.content.startswith(b"%PDF"):
                raise ValueError("Central Bank register response was not a PDF")
            target.write_bytes(response.content)
    payload = target.read_bytes()
    manifest = {"source_id": "cbi_authorised_ucits", "url": URL,
        "path": str(target.relative_to(ROOT)), "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(), "downloaded": downloaded,
        "checked_at": checked_at}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "cbi_dataset_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


class CbiUcitsConnector(BaseConnector):
    source_id = "cbi_authorised_ucits"
    country_code = "IE"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "IE", "organization": "Central Bank of Ireland",
            "source_name": "Authorised UCITS register", "endpoint_url": URL,
            "license_status": "Unknown"}

    def _load(self) -> None:
        download_ireland_ucits_register()
        text = "\n".join(page.extract_text() or "" for page in PdfReader(RAW / "central_bank_authorised_ucits.pdf").pages)
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        seen: set[str] = set()
        records: list[dict[str, Any]] = []
        for index, line in enumerate(lines):
            if not DATE_RE.fullmatch(line) or index == 0:
                continue
            name = lines[index - 1].strip(" \t•·")
            if len(name) < 5 or name.lower() in {"name of ucits", "date of", "authorisation", "management company", "trustee"}:
                continue
            key = " ".join(name.casefold().split())
            if key in seen:
                continue
            seen.add(key)
            source_id = hashlib.sha256(key.encode("utf-8")).hexdigest()[:24]
            records.append({"source_fund_id": source_id, "name": name,
                "domicile_country": "IE", "currency": None, "isin": None})
        self._records = records

    def check_availability(self) -> dict[str, Any]:
        self._load()
        return {"available": True, "fund_records": len(self._records or [])}

    def extract_funds(self, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load()
        return iter(self._records or [])
