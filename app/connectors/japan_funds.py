"""Official Japanese fund lists published by IMAJ and the Financial Services Agency."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urljoin

import httpx
from openpyxl import load_workbook

from app.config import timeout_seconds, user_agent
from app.connectors.base import BaseConnector

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "japan"
REPORTS = ROOT / "reports"
IMAJ_LIST_URL = (
    "https://www.imaj.or.jp/find/nisa_growth_productslist/"
    "xlsx-cms/unlisted_fund_for_investor.xlsx"
)
FSA_LIST_PAGE = "https://www.fsa.go.jp/policy/nisa2/products/index.html"
NEW_FUNDS_PAGE = "https://www.imaj.or.jp/find/newfunds/index.html"


def _download(url: str, target: Path, *, refresh: bool) -> dict[str, Any]:
    downloaded = refresh or not target.exists()
    if downloaded:
        response = httpx.get(
            url, timeout=timeout_seconds(), follow_redirects=True,
            headers={"User-Agent": user_agent(), "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,*/*"},
        )
        response.raise_for_status()
        payload = response.content
        if not payload.startswith(b"PK\x03\x04"):
            raise ValueError(f"Official Japan source did not return an XLSX: {response.url}")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(payload)
        temporary.replace(target)
        resolved_url = str(response.url)
    else:
        payload = target.read_bytes()
        resolved_url = url
    manifest = {
        "url": resolved_url,
        "path": str(target.relative_to(ROOT)),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "downloaded": downloaded,
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }
    return manifest


def download_imaj_growth_funds(*, refresh: bool = False) -> dict[str, Any]:
    path = RAW / "imaj_nisa_growth_unlisted_funds.xlsx"
    manifest = _download(IMAJ_LIST_URL, path, refresh=refresh)
    manifest.update({
        "source_id": ImajGrowthFundsConnector.source_id,
        "organization": "Investment Management Association of Japan",
        "source_report_date": "Current list; update date is in the workbook",
        "scope": "Domestic non-listed investment trusts reported as eligible for the NISA growth investment quota; not every Japanese fund.",
    })
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "jp_imaj_nisa_growth_dataset_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def _fsa_excel_url() -> str:
    response = httpx.get(FSA_LIST_PAGE, timeout=timeout_seconds(), follow_redirects=True,
                         headers={"User-Agent": user_agent()})
    response.raise_for_status()
    match = re.search(r"(?:href|HREF)=['\"]([^'\"]*/products/\d{8}/23\.xlsx)['\"]", response.text)
    if not match:
        raise ValueError("Could not find the current FSA fund-list Excel link")
    return urljoin(str(response.url), match.group(1))


def download_fsa_tsumitate_funds(*, refresh: bool = False) -> dict[str, Any]:
    cached = sorted(RAW.glob("fsa_tsumitate_funds_????????.xlsx"))
    if cached and not refresh:
        path = cached[-1]
        report_date = path.stem.rsplit("_", 1)[-1]
        url = f"https://www.fsa.go.jp/policy/nisa2/products/{report_date}/23.xlsx"
    else:
        page = httpx.get(FSA_LIST_PAGE, timeout=timeout_seconds(), follow_redirects=True,
                         headers={"User-Agent": user_agent()})
        page.raise_for_status()
        # FSA publishes a relative href such as 20261023/23.xlsx.
        match = re.search(r"(?:href|HREF)=['\"]([^'\"]*(\d{8})/23\.xlsx)['\"]", page.text)
        if not match:
            raise ValueError("Could not find the current FSA fund-list Excel link")
        url = urljoin(str(page.url), match.group(1))
        report_date = match.group(2)
        path = RAW / f"fsa_tsumitate_funds_{report_date}.xlsx"
    manifest = _download(url, path, refresh=refresh)
    manifest.update({
        "source_id": FsaTsumitateFundsConnector.source_id,
        "organization": "Financial Services Agency of Japan",
        "source_report_date": date.fromisoformat(f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:8]}").isoformat(),
        "scope": "Funds reported for the NISA tsumitate investment quota; excludes ETFs from ingestion and is not the full Japanese fund universe.",
    })
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "jp_fsa_tsumitate_dataset_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def download_imaj_new_funds(*, refresh: bool = False) -> dict[str, Any]:
    path = RAW / "imaj_new_funds.xlsx"
    manifest_path = REPORTS / "jp_imaj_new_funds_dataset_manifest.json"
    if path.exists() and manifest_path.exists() and not refresh:
        url = json.loads(manifest_path.read_text()).get("url", NEW_FUNDS_PAGE)
    else:
        page = httpx.get(NEW_FUNDS_PAGE, timeout=timeout_seconds(), follow_redirects=True,
                         headers={"User-Agent": user_agent()})
        page.raise_for_status()
        match = re.search(r"(?:href|HREF)=['\"]([^'\"]*/xlsx-cms/[^'\"]+\.xlsx)['\"]", page.text)
        if not match:
            raise ValueError("Could not find the current IMAJ new-fund Excel link")
        url = urljoin(str(page.url), match.group(1))
    manifest = _download(url, path, refresh=refresh)
    manifest.update({
        "source_id": ImajNewFundsConnector.source_id,
        "organization": "Investment Management Association of Japan",
        "scope": "Monthly new-fund list as published by IMAJ. The current workbook covers the sheet types it publishes and is not a complete fund register.",
    })
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "jp_imaj_new_funds_dataset_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def _date_value(value: Any) -> date | None:
    if value in (None, "", "-"):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    raw = str(value).strip()
    if re.fullmatch(r"\d{8}(?:\.0)?", raw):
        raw = raw[:8]
        return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8]))
    match = re.fullmatch(r"(\d{4})[./年-](\d{1,2})[./月-](\d{1,2})日?", raw)
    if match:
        return date(*(int(part) for part in match.groups()))
    return None


def _stable_id(prefix: str, *parts: str) -> str:
    key = "|".join(" ".join(part.split()).casefold() for part in parts)
    return f"{prefix}-{hashlib.sha256(key.encode('utf-8')).hexdigest()[:24].upper()}"


class ImajGrowthFundsConnector(BaseConnector):
    source_id = "jp_imaj_nisa_growth_funds"
    country_code = "JP"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "JP", "organization": "Investment Management Association of Japan",
                "source_name": "NISA growth-quota domestic non-listed investment trusts", "endpoint_url": IMAJ_LIST_URL,
                "license_status": "Unknown"}

    def _load(self) -> None:
        download_imaj_growth_funds()
        workbook = load_workbook(RAW / "imaj_nisa_growth_unlisted_funds.xlsx", read_only=True, data_only=True)
        sheet = workbook["対象商品一覧"]
        records: dict[str, dict[str, Any]] = {}
        for row in sheet.iter_rows(min_row=3, values_only=True):
            update_date, change, fund_code, name, manager, inception, maturity, eligible_date, closing, tsumitate = row[:10]
            code = str(fund_code or "").strip()
            name = str(name or "").strip()
            manager = str(manager or "").strip()
            if not code or not name or not manager:
                continue
            records[code] = {
                "source_fund_id": code,
                "name": name,
                "legal_name": name,
                "domicile_country": "JP",
                "manager": manager,
                "provider": manager,
                "category": "NISA growth investment quota eligible",
                "fund_type": "Domestic non-listed investment trust",
                "inception_date": _date_value(inception),
                "status": "Eligible (source snapshot)",
                "official_url": IMAJ_LIST_URL,
                "_profile_data": {"imaj_nisa_eligibility": {
                    "list_updated_at": _date_value(update_date).isoformat() if _date_value(update_date) else str(update_date or ""),
                    "change_type": str(change or "").strip() or None,
                    "growth_quota_eligible_from": _date_value(eligible_date).isoformat() if _date_value(eligible_date) else None,
                    "tsumitate_quota_eligible": str(tsumitate or "").strip() == "対象",
                    "reported_maturity_date": _date_value(maturity).isoformat() if _date_value(maturity) else None,
                    "closing_frequency": str(closing or "").strip() or None,
                }},
                "_profile_as_of_date": _date_value(update_date),
                "_profile_source_url": IMAJ_LIST_URL,
            }
        workbook.close()
        self._records = list(records.values())

    def check_availability(self) -> dict[str, Any]:
        self._load()
        return {"available": bool(self._records), "fund_records": len(self._records or [])}

    def extract_funds(self, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load()
        return iter(self._records or [])


class FsaTsumitateFundsConnector(BaseConnector):
    source_id = "jp_fsa_tsumitate_funds"
    country_code = "JP"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None
        self._source_date: date | None = None
        self._source_url = ""

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "JP", "organization": "Financial Services Agency of Japan",
                "source_name": "NISA tsumitate-quota fund disclosure list", "endpoint_url": FSA_LIST_PAGE,
                "license_status": "Unknown"}

    def _load(self) -> None:
        manifest = download_fsa_tsumitate_funds()
        self._source_url = manifest["url"]
        self._source_date = date.fromisoformat(manifest["source_report_date"])
        path = ROOT / manifest["path"]
        workbook = load_workbook(path, read_only=True, data_only=True)
        records: dict[str, dict[str, Any]] = {}
        for sheet in workbook.worksheets:
            if "ETF" in sheet.title:
                continue
            for row in sheet.iter_rows(min_row=7, values_only=True):
                name, manager = (str(row[0] or "").strip(), str(row[1] or "").strip())
                if not name or not manager or name.startswith("【"):
                    continue
                source_fund_id = _stable_id("FSA-JP", manager, name)
                records[source_fund_id] = {
                    "source_fund_id": source_fund_id,
                    "name": name,
                    "legal_name": name,
                    "domicile_country": "JP",
                    "manager": manager,
                    "provider": manager,
                    "category": "NISA tsumitate investment quota eligible",
                    "fund_type": "Domestic investment trust",
                    "status": "Eligible (source snapshot)",
                    "official_url": self._source_url,
                    "_profile_data": {"fsa_nisa_tsumitate_eligibility": {"reported_manager": manager}},
                    "_profile_as_of_date": self._source_date,
                    "_profile_source_url": self._source_url,
                }
        workbook.close()
        self._records = list(records.values())

    def check_availability(self) -> dict[str, Any]:
        self._load()
        return {"available": bool(self._records), "fund_records": len(self._records or [])}

    def extract_funds(self, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load()
        return iter(self._records or [])


class ImajNewFundsConnector(BaseConnector):
    source_id = "jp_imaj_new_funds"
    country_code = "JP"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "JP", "organization": "Investment Management Association of Japan",
                "source_name": "Monthly list of newly launched funds", "endpoint_url": NEW_FUNDS_PAGE,
                "license_status": "Unknown"}

    def _load(self) -> None:
        manifest = download_imaj_new_funds()
        path = ROOT / manifest["path"]
        workbook = load_workbook(path, read_only=True, data_only=True)
        records: dict[str, dict[str, Any]] = {}
        for sheet in workbook.worksheets:
            header_row = None
            for row_number, row in enumerate(sheet.iter_rows(values_only=True), start=1):
                values = [str(value or "").replace("\n", " ").strip() for value in row]
                if "Fund name Name of Funds" in values or any("Name of Funds" in value for value in values):
                    header_row = row_number
                    break
            if header_row is None:
                continue
            for row in sheet.iter_rows(min_row=header_row + 2, values_only=True):
                manager = str(row[2] or row[1] or "").strip()
                name = str(row[3] or "").strip()
                if not manager or not name:
                    continue
                source_fund_id = _stable_id("IMAJ-NEW", manager, name, str(row[8] or ""))
                records[source_fund_id] = {
                    "source_fund_id": source_fund_id,
                    "name": name,
                    "legal_name": name,
                    "domicile_country": "JP",
                    "manager": manager,
                    "provider": manager,
                    "category": str(row[5] or "").strip() or None,
                    "fund_type": "New domestic investment trust",
                    "inception_date": _date_value(row[8]),
                    "status": "Newly announced",
                    "official_url": manifest["url"],
                }
        workbook.close()
        self._records = list(records.values())

    def check_availability(self) -> dict[str, Any]:
        self._load()
        return {"available": bool(self._records), "fund_records": len(self._records or [])}

    def extract_funds(self, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load()
        return iter(self._records or [])
