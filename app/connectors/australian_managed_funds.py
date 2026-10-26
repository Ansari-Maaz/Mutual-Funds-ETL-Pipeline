"""User-provided Australian managed-fund catalogue.

The supplied CSV is a fund-master snapshot. It has no populated ISIN or NAV
columns, so this connector deliberately leaves those fields null rather than
inventing or scraping values from unrelated pages.
"""
from __future__ import annotations

import csv
import hashlib
import json
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from app.connectors.base import BaseConnector

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "australia" / "australian_managed_funds.csv"
NAV_RAW = ROOT / "data" / "raw" / "australia" / "australian_managed_fund_navs.csv"
REPORTS = ROOT / "reports"


def _source_fund_id(manager: str, name: str) -> str:
    value = f"{manager.strip().casefold()}|{name.strip().casefold()}".encode("utf-8")
    return f"AU-MF-{hashlib.sha256(value).hexdigest()[:20].upper()}"


def write_manifest() -> dict[str, Any]:
    if not RAW.exists():
        raise FileNotFoundError(f"Missing supplied Australian fund CSV: {RAW}")
    payload = RAW.read_bytes()
    manifest = {
        "source_id": "au_user_managed_funds",
        "origin": "User-provided file",
        "path": str(RAW.relative_to(ROOT)),
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "limitations": "All 96 rows have empty ISIN and nav_aud fields in the supplied CSV.",
    }
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "au_user_managed_funds_dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n"
    )
    return manifest


class AustralianManagedFundsConnector(BaseConnector):
    source_id = "au_user_managed_funds"
    country_code = "AU"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None
        self._rejects: list[dict[str, str]] = []
        self._navs: dict[str, list[dict[str, Any]]] = {}

    def get_source_metadata(self) -> dict[str, Any]:
        return {
            "country_code": "AU",
            "organization": "User-provided Australian managed-fund dataset",
            "source_name": "Australian managed-fund metadata catalogue",
            "endpoint_url": None,
            "license_status": "User supplied",
        }

    def _load(self) -> None:
        write_manifest()
        self._rejects = []
        records: dict[str, dict[str, Any]] = {}
        with RAW.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            required = {
                "fund_name", "manager", "subcategory", "structure",
                "base_currency", "isin", "nav_aud", "official_source",
            }
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError(f"Unexpected Australian managed-fund CSV columns: {reader.fieldnames}")
            for row_number, row in enumerate(reader, start=2):
                name = (row.get("fund_name") or "").strip()
                manager = (row.get("manager") or "").strip()
                currency = (row.get("base_currency") or "").strip().upper() or None
                if not name or not manager:
                    self._rejects.append({"row": str(row_number), "reason": "missing fund name or manager"})
                    continue
                if currency != "AUD":
                    self._rejects.append({"row": str(row_number), "reason": "missing or unsupported base currency"})
                    continue
                source_fund_id = _source_fund_id(manager, name)
                records.setdefault(source_fund_id, {
                    "source_fund_id": source_fund_id,
                    "name": name,
                    "legal_name": name,
                    "domicile_country": "AU",
                    "currency": currency,
                    "isin": (row.get("isin") or "").strip() or None,
                    "provider": manager,
                    "manager": manager,
                    "category": (row.get("subcategory") or "").strip() or None,
                    "fund_type": (row.get("structure") or "").strip() or None,
                    "status": "Listed in supplied catalogue",
                    "official_url": (row.get("official_source") or "").strip() or None,
                    "ticker": None,
                })
        self._records = list(records.values())
        self._navs = {}
        if NAV_RAW.exists():
            with NAV_RAW.open("r", encoding="utf-8-sig", newline="") as stream:
                nav_reader = csv.DictReader(stream)
                required_nav = {"manager", "fund_name", "valuation_date", "nav", "source_url"}
                if not nav_reader.fieldnames or not required_nav.issubset(nav_reader.fieldnames):
                    raise ValueError(f"Unexpected Australian NAV CSV columns: {nav_reader.fieldnames}")
                by_name = {(r["provider"].casefold(), r["name"].casefold()): r for r in self._records}
                for row in nav_reader:
                    key = ((row.get("manager") or "").strip().casefold(), (row.get("fund_name") or "").strip().casefold())
                    fund = by_name.get(key)
                    if not fund:
                        self._rejects.append({"fund_name": row.get("fund_name", ""), "reason": "NAV fund does not exactly match catalogue"})
                        continue
                    try:
                        valuation_date = date.fromisoformat((row.get("valuation_date") or "").strip())
                        nav = Decimal((row.get("nav") or "").strip())
                    except (ValueError, InvalidOperation):
                        self._rejects.append({"fund_name": row.get("fund_name", ""), "reason": "invalid NAV or valuation date"})
                        continue
                    if not nav.is_finite() or nav <= 0:
                        self._rejects.append({"fund_name": row.get("fund_name", ""), "reason": "NAV must be positive"})
                        continue
                    self._navs.setdefault(fund["source_fund_id"], []).append({
                        "source_fund_id": fund["source_fund_id"],
                        "valuation_date": valuation_date.isoformat(),
                        "nav": str(nav), "currency": "AUD",
                    })
        (REPORTS / "au_user_managed_funds_rejected_records.jsonl").write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in self._rejects)
        )

    def check_availability(self) -> dict[str, Any]:
        self._load()
        return {"available": True, "fund_records": len(self._records or []), "rejected_records": len(self._rejects)}

    def extract_funds(self, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load()
        return iter(self._records or [])

    def extract_nav_history(self, source_fund_id: str, start_date: date | None = None,
                            end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load()
        rows = self._navs.get(source_fund_id, [])
        return iter(row for row in rows if (not start_date or date.fromisoformat(row["valuation_date"]) >= start_date)
                    and (not end_date or date.fromisoformat(row["valuation_date"]) <= end_date))
