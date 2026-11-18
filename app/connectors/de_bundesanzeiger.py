"""Bundesanzeiger Fondsdata: daily price list of funds published in the German market.

The Federal Gazette publishes a free CSV of the prices published that day (about 400 funds, German number
format). There is no history file, so this connector downloads the file once per run into
data/raw/germany/bundesanzeiger_daily/ and builds NAV history from every stored daily file. Run it on weekday
evenings (after 18:00 CET). The site's terms on automated download are unconfirmed: keep this to one request a day.
"""
from __future__ import annotations

import csv
import re
import urllib.request
from datetime import date
from decimal import Decimal, InvalidOperation
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Iterable

from app.config import timeout_seconds, user_agent
from app.connectors.base import BaseConnector

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "data/raw/germany/bundesanzeiger_daily"
URL = "https://www.bundesanzeiger.de/pub/en/fondsdata"
_LINK = re.compile(r'href="([^"]*daily~csv[^"]*)"')


def download_daily_prices() -> Path:
    """Fetch today's published-price CSV (needs the session cookie from the Fondsdata page)."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    headers = {"User-Agent": user_agent(), "Accept": "*/*"}
    page = opener.open(urllib.request.Request(URL, headers=headers), timeout=timeout_seconds()).read().decode("utf-8", "replace")
    match = _LINK.search(page)
    if not match:
        raise ValueError("Bundesanzeiger Fondsdata page did not expose the daily CSV link")
    response = opener.open(urllib.request.Request(match.group(1).replace("&amp;", "&"), headers=headers), timeout=timeout_seconds())
    disposition = response.headers.get("Content-Disposition", "")
    name = re.search(r'filename="?([^";]+)', disposition)
    payload = response.read()
    if b"NAV" not in payload[:400]:
        raise ValueError("Bundesanzeiger daily CSV did not have the expected header")
    target = RAW_DIR / (name.group(1) if name else f"tagesaktuelle_preise_{date.today().isoformat()}.csv")
    target.write_bytes(payload)
    return target


def german_decimal(value: str) -> Decimal | None:
    text = (value or "").strip().replace(".", "").replace(",", ".")
    try:
        parsed = Decimal(text)
    except InvalidOperation:
        return None
    return parsed if parsed.is_finite() and parsed > 0 else None


def parse_daily_file(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.reader(stream):
            if not row or row[0].startswith("Fondspreis") or len(row) < 9:
                continue
            valuation, name, isin, wkn, provider, currency, redemption, issue, nav = (c.strip() for c in row[:9])
            value = german_decimal(nav)
            if not isin or not name or value is None or len(currency) != 3:
                continue
            yield {"valuation_date": valuation, "name": name, "isin": isin.split("/")[0].strip(), "wkn": wkn or None,
                   "provider": provider or None, "currency": currency.upper(), "nav": value}


def _category(name: str) -> str:
    n = name.casefold()
    if any(x in n for x in ("money market", "geldmarkt", "liquidity")): return "Money market"
    if any(x in n for x in ("bond", "renten", "fixed income", "credit", "oblig")): return "Fixed income"
    if any(x in n for x in ("real estate", "immobil", "property")): return "Real estate"
    if any(x in n for x in ("balanced", "multi asset", "allocation", "vermögens")): return "Mixed allocation"
    if any(x in n for x in ("commodity", "gold", "rohstoff")): return "Commodities"
    if any(x in n for x in ("index", "etf")): return "Index/ETF"
    if any(x in n for x in ("equity", "aktien", "stock", "global", "europe", "asia", "world")): return "Equity"
    return "Other"


class DeBundesanzeigerConnector(BaseConnector):
    source_id = "de_bundesanzeiger_navs"
    country_code = "DE"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None
        self._navs: dict[str, list[dict[str, Any]]] = {}

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "DE", "organization": "Bundesanzeiger / Federal Gazette",
                "source_name": "Public German-market fund prices and NAVs (Fondsdata daily CSV)",
                "endpoint_url": URL, "license_status": "Public; terms on automated use to confirm"}

    def _load(self, *, download: bool = True) -> None:
        if download:
            download_daily_prices()
        funds: dict[str, dict[str, Any]] = {}
        navs: dict[str, dict[str, dict[str, Any]]] = {}
        for path in sorted(RAW_DIR.glob("*.csv")):
            for row in parse_daily_file(path):
                sid = f"DE-BANZ-{row['isin']}"
                funds[sid] = {"source_fund_id": sid, "name": row["name"], "legal_name": row["name"], "provider": row["provider"],
                              "category": _category(row["name"]), "fund_type": "Mutual fund",
                              "domicile_country": "DE" if row["isin"].startswith("DE") else None,
                              "currency": row["currency"], "isin": row["isin"], "status": "Price published", "official_url": URL}
                navs.setdefault(sid, {})[row["valuation_date"]] = {
                    "source_fund_id": sid, "valuation_date": row["valuation_date"], "nav": str(row["nav"]), "currency": row["currency"]}
        self._records = list(funds.values())
        self._navs = {sid: sorted(by_date.values(), key=lambda r: r["valuation_date"]) for sid, by_date in navs.items()}

    def check_availability(self) -> dict[str, Any]:
        self._load()
        return {"available": True, "fund_records": len(self._records or []),
                "nav_records": sum(len(v) for v in self._navs.values())}

    def extract_funds(self, start_date: date | None = None, end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load()
        return iter(self._records or [])

    def extract_nav_history(self, source_fund_id: str, start_date: date | None = None,
                            end_date: date | None = None) -> Iterable[dict[str, Any]]:
        if self._records is None:
            self._load()
        return iter(self._navs.get(source_fund_id, []))
