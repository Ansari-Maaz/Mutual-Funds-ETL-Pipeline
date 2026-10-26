"""Public FT/Morningstar UK fund price table snapshot.

The FT page publishes manager supplied bid prices (prices are in pence unless
the table marks another currency).  These are useful public fund prices, but
are not asserted to be official regulator supplied NAVs.
"""
from __future__ import annotations
import csv
from datetime import date
from pathlib import Path
from typing import Any
from app.connectors.base import BaseConnector

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/united_kingdom/ft_morningstar_fund_prices.csv"
URL = "https://markets.ft.markitdigital.com/data/dataarchive/ajax/fetchreport?documentKey=688_UTS~Combined_261024&reportCode=UTS_Combined"

class UkFtMorningstarConnector(BaseConnector):
    source_id = "uk_ft_morningstar_prices"
    country_code = "GB"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None
        self._navs: dict[str, list[dict[str, Any]]] = {}

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "GB", "organization": "Financial Times / ICE Data Services",
                "source_name": "Public UK fund price table (Morningstar/FT archive)",
                "endpoint_url": URL,
                "license_status": "Public; terms to confirm"}

    def _load(self) -> None:
        self._records, self._navs = [], {}
        with RAW.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                sid = row["source_fund_id"]
                self._records.append({k: row.get(k, "") or None for k in
                    ["source_fund_id", "ticker", "name", "legal_name", "category", "fund_type",
                     "currency", "isin", "domicile_country", "status", "official_url"]})
                self._navs[sid] = [{"source_fund_id": sid, "valuation_date": row["valuation_date"],
                                    "nav": row["nav"], "currency": row["currency"]}]

    def check_availability(self) -> dict[str, Any]:
        self._load()
        return {"available": True, "fund_records": len(self._records or []),
                "nav_records": sum(len(x) for x in self._navs.values())}

    def extract_funds(self, start_date: date | None = None, end_date: date | None = None):
        if self._records is None: self._load()
        return iter(self._records or [])

    def extract_nav_history(self, source_fund_id: str, start_date: date | None = None, end_date: date | None = None):
        if self._records is None: self._load()
        return iter(self._navs.get(source_fund_id, []))
