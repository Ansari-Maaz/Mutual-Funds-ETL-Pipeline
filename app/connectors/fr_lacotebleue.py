"""Public French fund NAV table from La Cote Bleue (ISIN-linked snapshot)."""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from app.connectors.base import BaseConnector
from app.connectors.euronext_base import category
from app.connectors.snapshots import probe_snapshot

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/france/lacote_bleue_navs.csv"
URL = "https://actusite.lacotebleue.fr/opcvm/"


class FrLaCoteBleueConnector(BaseConnector):
    source_id = "fr_lacotebleue_navs"
    country_code = "FR"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None
        self._navs: dict[str, list[dict[str, Any]]] = {}

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "FR", "organization": "La Cote Bleue",
                "source_name": "Public French fund NAV table", "endpoint_url": URL,
                "license_status": "Public; terms to confirm"}

    def _load(self) -> None:
        records = []
        navs = {}
        with RAW.open(encoding="utf-8", newline="") as stream:
            for row in csv.DictReader(stream):
                isin = (row.get("isin") or "").strip().upper()
                name = (row.get("name") or "").strip()
                currency = (row.get("currency") or "").strip().upper()
                try:
                    nav = float(row.get("nav") or "")
                except (TypeError, ValueError):
                    continue
                if not isin or not name or len(currency) != 3 or nav <= 0:
                    continue
                source_fund_id = f"FR-LCB-{isin}"
                records.append({"source_fund_id": source_fund_id, "name": name,
                    "legal_name": name, "provider": (row.get("provider") or "").strip() or None,
                    "category": category(name), "fund_type": "Mutual fund",
                    "domicile_country": "FR", "currency": currency, "isin": isin,
                    "status": "NAV published", "official_url": URL})
                navs[source_fund_id] = [{"source_fund_id": source_fund_id,
                    "valuation_date": row["valuation_date"], "nav": row["nav"],
                    "currency": currency}]
        self._records = records
        self._navs = navs

    def check_availability(self) -> dict[str, Any]:
        result = probe_snapshot(self.source_id, URL, RAW)
        if not result["available"]:
            return result
        self._load()
        return {**result, "available": bool(self._records),
                "fund_records": len(self._records), "nav_records": len(self._navs)}

    def extract_funds(self, start_date: date | None = None,
                      end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load()
        return iter(self._records)

    def extract_nav_history(self, source_fund_id: str, start_date: date | None = None,
                            end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load()
        return iter(self._navs.get(source_fund_id, []))
