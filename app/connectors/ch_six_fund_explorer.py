"""Public SIX fund-explorer snapshot for Swiss-domiciled investment funds."""
from __future__ import annotations
import json
import urllib.parse
import urllib.request
from datetime import date
from typing import Any, Iterable
from app.config import timeout_seconds, user_agent
from app.connectors.base import BaseConnector

URL = "https://www.six-group.com/fqs/ref.json"
SELECT = ",".join(["FundLongName","FundCurrency","ISIN","ClosingPrice","MarketDate","LegalStructureCountryDesc","LegalStructureCountryCode","AssetClassDesc","IssuerLongNameDesc"])


def _category(asset_class: str | None, name: str) -> str:
    value = (asset_class or "").strip().casefold()
    n = name.casefold()
    if "real estate" in value or any(x in n for x in ("property", "immobilier", "real estate")): return "Real estate"
    if any(x in value for x in ("fixed income", "bond", "money")) or any(x in n for x in ("bond", "obligation", "money market")): return "Fixed income"
    if "equity" in value or any(x in n for x in ("equity", "equities", "stock", "actions")): return "Equity"
    if any(x in value for x in ("mixed", "multi", "allocation")): return "Mixed allocation"
    return (asset_class or "Other").strip() or "Other"


class ChSixFundExplorerConnector(BaseConnector):
    source_id = "ch_six_fund_explorer_navs"
    country_code = "CH"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None
        self._navs: dict[str, list[dict[str, Any]]] = {}

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "CH", "organization": "SIX Group",
                "source_name": "Public Swiss fund explorer (delayed closing NAV/price)",
                "endpoint_url": "https://www.six-group.com/en/market-data/mutual-funds/fund-explorer.html",
                "license_status": "Public; terms to confirm"}

    def _load(self) -> None:
        params = {"select": SELECT, "where": "ProductLine=IF", "page": "1", "pagesize": "99999", "orderby": "FundLongName"}
        request = urllib.request.Request(URL + "?" + urllib.parse.urlencode(params), headers={"User-Agent": user_agent(), "Accept": "application/json"})
        with urllib.request.urlopen(request, timeout=timeout_seconds()) as response:
            payload = json.load(response)
        names = payload.get("colNames") or []
        rows = payload.get("rowData") or []
        indexes = {name: i for i, name in enumerate(names)}
        self._records, self._navs = [], {}
        for row in rows:
            def get(key: str):
                i = indexes.get(key)
                return row[i] if i is not None and i < len(row) else None
            isin = str(get("ISIN") or "").strip().upper()
            name = str(get("FundLongName") or "").strip()
            currency = str(get("FundCurrency") or "").strip().upper()
            value = get("ClosingPrice")
            day = str(get("MarketDate") or "").strip()
            # SIX's ProductLine=IF result is Swiss investment funds; retain only
            # rows with a Swiss legal domicile and a positive published value.
            if get("LegalStructureCountryCode") != "CH" or not isin or not name or len(currency) != 3 or not value or float(value) <= 0 or len(day) != 8:
                continue
            sid = f"CH-SIX-{isin}"
            valuation_date = f"{day[:4]}-{day[4:6]}-{day[6:]}"
            record = {"source_fund_id": sid, "name": name, "legal_name": name,
                      "provider": str(get("IssuerLongNameDesc") or "").strip() or "SIX Group",
                      "category": _category(get("AssetClassDesc"), name), "fund_type": "Mutual fund",
                      "domicile_country": "CH", "currency": currency, "isin": isin,
                      "status": "NAV published (delayed)",
                      "official_url": "https://www.six-group.com/en/market-data/mutual-funds/fund-explorer.html"}
            self._records.append(record)
            self._navs[sid] = [{"source_fund_id": sid, "valuation_date": valuation_date, "nav": value, "currency": currency}]

    def check_availability(self) -> dict[str, Any]:
        self._load()
        return {"available": True, "fund_records": len(self._records or []), "nav_records": len(self._navs)}

    def extract_funds(self, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None: self._load()
        return iter(self._records or [])

    def extract_nav_history(self, source_fund_id: str, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None: self._load()
        return iter(self._navs.get(source_fund_id, []))
