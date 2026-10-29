"""Official Allianz Global Investors Luxembourg daily-NAV table."""
from __future__ import annotations
import csv
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from app.connectors.base import BaseConnector
from app.connectors.snapshots import probe_snapshot
ROOT=Path(__file__).resolve().parents[2]; RAW=ROOT/'data/raw/luxembourg/allianz_luxembourg_daily_nav.csv'
URL='https://regulatory.allianzgi.com/en-gb/facilities-services/luxemburg-en/funds/mutual-funds'
class LuAllianzDailyNavConnector(BaseConnector):
    source_id = "lu_allianz_daily_navs"
    country_code = "LU"

    def __init__(self) -> None:
        self._records = None
        self._navs = {}

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "LU", "organization": "Allianz Global Investors",
                "source_name": "Official Luxembourg daily NAV table", "endpoint_url": URL,
                "license_status": "Public; terms to confirm"}

    def _load(self) -> None:
        self._records = []
        self._navs = {}
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
                source_fund_id = f"LU-ALLIANZ-{isin}-{(row.get('share_class') or '').strip()}"
                self._records.append({"source_fund_id": source_fund_id, "name": name,
                    "legal_name": name, "provider": row.get("provider"),
                    "category": row.get("asset_class") or "Other", "fund_type": "Mutual fund",
                    "domicile_country": "LU", "currency": currency, "isin": isin,
                    "status": "NAV published", "official_url": URL})
                # SFDR article classes describe sustainability disclosure, not audience.
                self._navs[source_fund_id] = [{"source_fund_id": source_fund_id,
                    "valuation_date": row["valuation_date"], "nav": row["nav"],
                    "currency": currency}]

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
