"""Korean fund products in the open public-data CSV published for IBK Bank."""
from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode

import httpx

from app.config import timeout_seconds, user_agent
from app.connectors.base import BaseConnector

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "south_korea"
REPORTS = ROOT / "reports"
DATASET_ID = "15020770"
DETAIL_ID = "uddi:cda5d2bd-5a73-4bb6-a71e-e333948bba43"
DATASET_PAGE = f"https://www.data.go.kr/data/{DATASET_ID}/fileData.do"
DOWNLOAD_META_URL = "https://www.data.go.kr/tcs/dss/selectFileDataDownload.do"
FILE_URL = "https://www.data.go.kr/cmm/cmm/fileDownload.do"


def download_ibk_funds(*, refresh: bool = False) -> dict[str, Any]:
    manifest_path = REPORTS / "kr_ibk_fund_information_dataset_manifest.json"
    if manifest_path.exists() and not refresh:
        cached_manifest = json.loads(manifest_path.read_text())
        cached_file = ROOT / cached_manifest.get("path", "")
        if cached_file.is_file():
            return cached_manifest
    page = httpx.get(DATASET_PAGE, timeout=timeout_seconds(), follow_redirects=True,
                     headers={"User-Agent": user_agent()})
    page.raise_for_status()
    detail_match = re.search(r'id="publicDataDetailPk"[^>]*value="([^"]+)"', page.text)
    if detail_match:
        detail_id = detail_match.group(1)
    else:
        detail_id = DETAIL_ID
    metadata = httpx.get(DOWNLOAD_META_URL, params={
        "publicDataDetailPk": detail_id,
        "publicDataPk": DATASET_ID,
        "atchFileId": "",
        "fileDetailSn": "1",
        "url": "/tcs/dss/selectFileDataDownload.do",
    }, timeout=timeout_seconds(), headers={"User-Agent": user_agent()})
    metadata.raise_for_status()
    payload_info = metadata.json()
    if not payload_info.get("status") or not payload_info.get("atchFileId"):
        raise ValueError("IBK fund CSV download metadata was not available")
    file_name = payload_info.get("dataSetFileDetailInfo", {}).get("dataNm", "")
    report_match = re.search(r"(20\d{6})", file_name)
    report_date = report_match.group(1) if report_match else "unknown"
    target = RAW / f"ibk_fund_information_{report_date}.csv"
    downloaded = refresh or not target.exists()
    if downloaded:
        response = httpx.get(FILE_URL, params={
            "atchFileId": payload_info["atchFileId"],
            "fileDetailSn": payload_info.get("fileDetailSn", "1"),
            "dataNm": file_name,
        }, timeout=timeout_seconds(), follow_redirects=True,
           headers={"User-Agent": user_agent(), "Accept": "text/csv,application/octet-stream,*/*"})
        response.raise_for_status()
        content = response.content
        if not content or content.lstrip().startswith(b"<!DOCTYPE") or b"," not in content[:4096]:
            raise ValueError("IBK data portal did not return the expected CSV")
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(content)
        temporary.replace(target)
    content = target.read_bytes()
    manifest = {
        "source_id": KoreaIbkFundsConnector.source_id,
        "organization": "Industrial Bank of Korea (IBK)",
        "dataset_id": DATASET_ID,
        "dataset_name": file_name,
        "url": DATASET_PAGE,
        "path": str(target.relative_to(ROOT)),
        "bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
        "source_report_date": date.fromisoformat(f"{report_date[:4]}-{report_date[4:6]}-{report_date[6:8]}").isoformat() if report_date != "unknown" else None,
        "downloaded": downloaded,
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Funds handled by IBK Bank; not an exhaustive list of South Korean-domiciled funds. The source does not provide domicile, currency, or NAV values.",
        "license_status": "Permitted per data.go.kr (unrestricted-use designation)",
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def _number(value: str | None) -> str | None:
    raw = (value or "").strip().replace(",", "")
    if not raw or raw in {"-", "N/A"}:
        return None
    try:
        parsed = float(raw)
    except ValueError:
        return None
    if not (-float("inf") < parsed < float("inf")):
        return None
    return str(raw)


def _fund_id(manager: str, code: str) -> str:
    clean = code.strip()
    if clean:
        return clean
    digest = hashlib.sha256(f"{manager.strip()}|{code.strip()}".encode("utf-8")).hexdigest()[:24].upper()
    return f"IBK-KR-{digest}"


class KoreaIbkFundsConnector(BaseConnector):
    source_id = "kr_ibk_fund_information"
    country_code = "KR"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None
        self._source_date: date | None = None
        self._source_url = DATASET_PAGE

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "KR", "organization": "Industrial Bank of Korea (IBK), via the Korean Public Data Portal",
                "source_name": "IBK fund information (annual product, return and fee snapshot)",
                "endpoint_url": DATASET_PAGE, "license_status": "Permitted"}

    def _load(self) -> None:
        manifest = download_ibk_funds()
        self._source_url = manifest["url"]
        self._source_date = date.fromisoformat(manifest["source_report_date"]) if manifest["source_report_date"] else None
        path = ROOT / manifest["path"]
        records: dict[str, dict[str, Any]] = {}
        with path.open("r", encoding="cp949", newline="") as stream:
            reader = csv.DictReader(stream)
            required = {"운용사명", "펀드코드", "상품명", "펀드유형"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError(f"Unexpected IBK fund CSV columns: {reader.fieldnames}")
            risk_column = next((column for column in reader.fieldnames if re.fullmatch(r"20\d{6}기준 위험등급", column)), None)
            for row in reader:
                manager = (row.get("운용사명") or "").strip()
                fund_code = (row.get("펀드코드") or "").strip()
                name = (row.get("상품명") or "").strip()
                if not manager or not fund_code or not name:
                    continue
                source_fund_id = _fund_id(manager, fund_code)
                profile = {
                    "manager_name": manager,
                    "fund_code": fund_code,
                    "fund_type": (row.get("펀드유형") or "").strip() or None,
                    "risk_grade": (row.get(risk_column) or "").strip() if risk_column else None,
                    "cumulative_return_percent": {
                        "1_month": _number(row.get("1개월누적수익률(퍼센트)")),
                        "3_month": _number(row.get("3개월누적수익률(퍼센트)")),
                        "6_month": _number(row.get("6개월누적수익률(퍼센트)")),
                        "12_month": _number(row.get("12개월누적수익률(퍼센트)")),
                    },
                    "upfront_fee_percent": _number(row.get("선취수수료(퍼센트)")),
                    "total_fee_percent": _number(row.get("총보수(퍼센트)")),
                    "return_definition": "Change in the fund's reference price over each period, as described by IBK; not an account-level investor return.",
                    "market_scope": "Products currently handled by IBK; domicile is not supplied by this file.",
                }
                records[source_fund_id] = {
                    "source_fund_id": source_fund_id,
                    "name": name,
                    "legal_name": name,
                    "domicile_country": None,
                    "currency": None,
                    "manager": manager,
                    "provider": manager,
                    "category": (row.get("펀드유형") or "").strip() or None,
                    "fund_type": (row.get("펀드유형") or "").strip() or None,
                    "official_url": self._source_url,
                    "_profile_data": {"ibk_fund_information": profile},
                    "_profile_as_of_date": self._source_date,
                    "_profile_source_url": self._source_url,
                }
        self._records = list(records.values())

    def check_availability(self) -> dict[str, Any]:
        self._load()
        return {"available": bool(self._records), "fund_records": len(self._records or [])}

    def extract_funds(self, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load()
        return iter(self._records or [])
