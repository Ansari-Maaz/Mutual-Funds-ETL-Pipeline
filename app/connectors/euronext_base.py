"""Shared Euronext snapshot parsing and fund-category labeling."""
from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any, Iterable

from app.connectors.base import BaseConnector
from app.connectors.snapshots import probe_snapshot


def category(name: str) -> str:
    value = name.casefold()
    if any(word in value for word in ("bond", "oblig", "rente", "fixed income")):
        return "Fixed income"
    if any(word in value for word in ("property", "real estate", "vastgoed", "immobilier")):
        return "Real estate"
    if any(word in value for word in ("mix", "balanced", "allocation", "diversif", "patrimoine", "horizon", "multi")):
        return "Mixed allocation"
    if any(word in value for word in ("money market", "monétaire", "liquid")):
        return "Money market"
    if any(word in value for word in ("etf", "index")):
        return "Index/ETF"
    if any(word in value for word in ("equity", "aandelen", "actions", "stock", "world", "monde", "global", "euro", "europe", "value")):
        return "Equity"
    return "Other"


class EuronextSnapshotConnector(BaseConnector):
    source_id: str
    country_code: str
    organization: str
    source_name: str
    endpoint_url: str
    raw_path: Path
    id_prefix: str

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None
        self._navs: dict[str, list[dict[str, Any]]] = {}

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": self.country_code, "organization": self.organization,
                "source_name": self.source_name, "endpoint_url": self.endpoint_url,
                "license_status": "Public; terms to confirm"}

    def _load(self) -> None:
        records = []
        navs = {}
        with self.raw_path.open(encoding="utf-8-sig", newline="") as stream:
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
                source_fund_id = f"{self.id_prefix}-{isin}"
                records.append({"source_fund_id": source_fund_id, "name": name,
                    "legal_name": name, "provider": self.organization,
                    "category": category(name), "fund_type": "Mutual fund",
                    "domicile_country": self.country_code, "currency": currency,
                    "isin": isin, "ticker": row.get("ticker") or None,
                    "status": "NAV/last price published", "official_url": self.endpoint_url})
                navs[source_fund_id] = [{"source_fund_id": source_fund_id,
                    "valuation_date": row["valuation_date"], "nav": row["nav"], "currency": currency}]
        self._records = records
        self._navs = navs

    def check_availability(self) -> dict[str, Any]:
        status = probe_snapshot(self.source_id, self.endpoint_url, self.raw_path)
        if not status["available"]:
            return status
        self._load()
        return {**status, "available": bool(self._records),
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
