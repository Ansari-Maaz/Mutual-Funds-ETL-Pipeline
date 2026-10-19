"""AMF GECO French-domiciled active collective investment product classes."""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import httpx

from app.config import timeout_seconds, user_agent
from app.connectors.base import BaseConnector

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "france"
REPORTS = ROOT / "reports"
INDEX_URL = "https://geco.amf-france.org/liste-des-produits-d-epargne"
EXPORT_URL = "https://geco.amf-france.org/back-office/funds/compartments"


def download_amf_geco(*, refresh: bool = False) -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / "geco_compartments.json"
    downloaded = refresh or not target.exists()
    if downloaded:
        body = json.dumps({"idThirdParty": 0, "productType": "FR",
            "lazyLoadEvent": {"first": 0, "rows": 10, "sortField": "", "sortOrder": 1,
                "multiSortMeta": [], "filters": {}, "globalFilter": None}, "total": 100000})
        headers = {"User-Agent": user_agent(), "Origin": "https://geco.amf-france.org",
            "Referer": INDEX_URL, "Content-Type": "text/plain;charset=UTF-8", "Accept": "application/json"}
        with httpx.Client(follow_redirects=True, timeout=max(timeout_seconds(), 120), headers=headers) as client:
            response = client.post(EXPORT_URL, content=body)
            response.raise_for_status()
            document = response.json()
        rows = document.get("compartmentDtos")
        if not isinstance(rows, list) or not rows:
            raise ValueError("AMF GECO export did not contain product records")
        target.write_text(json.dumps(document, ensure_ascii=False) + "\n")
    payload = target.read_bytes()
    document = json.loads(payload)
    manifest = {"source_id": "amf_geco", "url": EXPORT_URL, "index_url": INDEX_URL,
        "records": len(document.get("compartmentDtos", [])), "path": str(target.relative_to(ROOT)),
        "bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest(),
        "downloaded": downloaded, "checked_at": datetime.now(timezone.utc).isoformat()}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "amf_geco_dataset_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


class AmfGecoConnector(BaseConnector):
    source_id = "amf_geco"
    country_code = "FR"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "FR", "organization": "Autorité des marchés financiers",
            "source_name": "GECO active French-domiciled OPC products and share classes",
            "endpoint_url": EXPORT_URL, "license_status": "Unknown"}

    def _load(self) -> None:
        download_amf_geco()
        document = json.loads((RAW / "geco_compartments.json").read_text())
        output: dict[str, dict[str, Any]] = {}
        for row in document.get("compartmentDtos", []):
            fund = row.get("fundDTO") or {}
            if row.get("prdDomcltn") != "FR" or row.get("cmpStatutCode") != "VIV" or fund.get("prdStatutCode") != "VIV":
                continue
            product_name = (fund.get("prdNom") or "").strip()
            compartment_name = (row.get("cmpNom") or "").strip()
            class_label = compartment_name if compartment_name and compartment_name.casefold() not in {"fonds dédié***", "fonds dédié"} else ""
            ids = [x.strip() for x in (row.get("sharesIsins") or []) if isinstance(x, str) and x.strip()]
            if not ids:
                ids = [None]
            for isin in ids:
                class_id = (row.get("cmpId") or row.get("cmpAmfId") or "").strip()
                if not class_id or not product_name:
                    continue
                source_fund_id = f"{class_id}:{isin}" if isin else class_id
                name = " — ".join(x for x in (product_name, class_label) if x)
                output.setdefault(source_fund_id, {"source_fund_id": source_fund_id, "name": name,
                    "domicile_country": "FR", "currency": None, "isin": isin})
        self._records = list(output.values())

    def check_availability(self) -> dict[str, Any]:
        self._load()
        return {"available": True, "fund_records": len(self._records or [])}

    def extract_funds(self, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load()
        return iter(self._records or [])
