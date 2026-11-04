"""SEC registered open-end mutual-fund series/share-class snapshot."""
from __future__ import annotations

import csv
import hashlib
import json
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from app.config import timeout_seconds, user_agent
from app.connectors.base import BaseConnector

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw" / "united_states"
NAV_RAW = RAW / "nasdaq_mutual_fund_navs.csv"
YAHOO_NAV_RAW = RAW / "yahoo_mutual_fund_navs.csv"
REPORTS = ROOT / "reports"
URL = "https://www.sec.gov/files/investment/data/other/investment-company-series-class-information/investment-company-series-class-2026.csv"
TICKER_URL = "https://www.sec.gov/files/company_tickers_mf.json"


def _fund_record_from_row(row: dict[str, str]) -> dict[str, Any] | None:
    """Map one SEC series/class row without treating registrant data as adviser data."""
    class_id = (row.get("Class ID") or "").strip()
    series_id = (row.get("Series ID") or "").strip()
    series_name = (row.get("Series Name") or "").strip()
    class_name = (row.get("Class Name") or "").strip()
    cik = (row.get("CIK Number") or "").strip()
    if (row.get("Entity Org Type") or "").strip() != "30" or not class_id or not (series_name or class_name):
        return None

    registrant = (row.get("Entity Name") or "").strip() or None
    ticker = (row.get("Class Ticker") or "").strip() or None
    name = f"{series_name} — {class_name}" if series_name and class_name and series_name != class_name else (series_name or class_name)
    address = {
        key: (row.get(source_key) or "").strip()
        for key, source_key in (("address_1", "Address_1"), ("address_2", "Address_2"),
                                ("city", "City"), ("state", "State"), ("postal_code", "Zip Code"))
        if (row.get(source_key) or "").strip()
    }
    profile = {
        "registrant_name": registrant,
        "registrant_cik": cik or None,
        "sec_filing_number": (row.get("Reporting File Number") or "").strip() or None,
        "series_id": series_id or None,
        "series_name": series_name or None,
        "class_id": class_id,
        "class_name": class_name or None,
        "share_class": class_name or None,
        "class_ticker": ticker,
        "registrant_address": address or None,
        "source_scope": "SEC registrant/series/class master; registrant is not asserted to be the investment adviser",
        "identifier_note": "SEC class master does not provide ISIN or CUSIP",
    }
    return {
        "source_fund_id": class_id,
        "name": name,
        "legal_name": class_name or series_name,
        "domicile_country": "US",
        "currency": "USD",
        "isin": None,
        "provider": registrant,
        "manager": None,
        "fund_type": "Open-end mutual fund",
        "status": "Registered",
        "ticker": ticker,
        "official_url": URL,
        "profile_data": {"summary": profile},
        "profile_source_url": URL,
    }


def download_sec_series_classes(*, refresh: bool = False) -> dict[str, Any]:
    RAW.mkdir(parents=True, exist_ok=True)
    target = RAW / "sec_series_classes.csv"
    downloaded = refresh or not target.exists()
    if downloaded:
        request = urllib.request.Request(URL, headers={"User-Agent": user_agent(), "Accept": "text/csv,*/*"})
        with urllib.request.urlopen(request, timeout=timeout_seconds()) as response:
            payload = response.read()
        if b"Entity Org Type,Series ID,Series Name,Class ID" not in payload[:1000]:
            raise ValueError("SEC response did not match the expected series/class CSV")
        target.write_bytes(payload)
    payload = target.read_bytes()
    manifest = {"source_id": "sec_open_end_fund_classes", "url": URL,
        "path": str(target.relative_to(ROOT)), "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(), "downloaded": downloaded,
        "checked_at": datetime.now(timezone.utc).isoformat()}
    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "sec_dataset_manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    return manifest


class SecFundsConnector(BaseConnector):
    source_id = "sec_open_end_fund_classes"
    country_code = "US"

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] | None = None
        self._navs: dict[str, list[dict[str, Any]]] = {}

    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code": "US", "organization": "U.S. Securities and Exchange Commission",
            "source_name": "Investment Company Series and Class Information (Form N-1A subset)",
            "endpoint_url": URL, "license_status": "Unknown",
            "nav_sources": [
                {"source_id": "us_yahoo_mutual_fund_navs", "country_code": "US",
                 "organization": "Yahoo Finance", "source_name": "US mutual fund daily NAV observations",
                 "endpoint_url": "https://query1.finance.yahoo.com/v8/finance/spark", "license_status": "Unknown"},
                {"source_id": "us_nasdaq_mutual_fund_navs", "country_code": "US",
                 "organization": "Nasdaq", "source_name": "US mutual fund daily NAV observations",
                 "endpoint_url": "https://api.nasdaq.com/api/quote/QQQM/historical?assetclass=mutualfunds", "license_status": "Unknown"},
            ]}

    def _load(self) -> None:
        download_sec_series_classes()
        output: dict[str, dict[str, Any]] = {}
        with (RAW / "sec_series_classes.csv").open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            required = {"Entity Org Type", "Series ID", "Series Name", "Class ID", "Class Name"}
            if not reader.fieldnames or not required.issubset(reader.fieldnames):
                raise ValueError(f"Unexpected SEC CSV columns: {reader.fieldnames}")
            for row in reader:
                record = _fund_record_from_row(row)
                if record is None:
                    continue
                output.setdefault(record["source_fund_id"], record)
        # The SEC ticker JSON is a compact supplemental mapping of class ID to
        # ticker. It has no fund names, so it enriches the CSV master rather
        # than creating duplicate fund rows.
        ticker_json = RAW / "sec_company_tickers_mf.json"
        if ticker_json.exists():
            payload = json.loads(ticker_json.read_text(encoding="utf-8"))
            for row in payload.get("data", []):
                if len(row) < 4:
                    continue
                class_id, ticker = str(row[2]).strip(), str(row[3]).strip()
                if class_id in output and ticker:
                    output[class_id]["ticker"] = ticker
                    output[class_id]["profile_data"]["summary"]["class_ticker"] = ticker
        self._records = list(output.values())
        self._navs = {}
        if NAV_RAW.exists() or YAHOO_NAV_RAW.exists():
            by_ticker = {(r.get("ticker") or "").casefold(): r for r in self._records if r.get("ticker")}
            # Keep provider outputs separate on disk; merge at read time with
            # Nasdaq preferred when both publish the same ticker/date key.
            for nav_path, nav_source_id in ((YAHOO_NAV_RAW, "us_yahoo_mutual_fund_navs"),
                                            (NAV_RAW, "us_nasdaq_mutual_fund_navs")):
                if not nav_path.exists():
                    continue
                with nav_path.open("r", encoding="utf-8-sig", newline="") as stream:
                    for row in csv.DictReader(stream):
                        fund = by_ticker.get((row.get("ticker") or "").strip().casefold())
                        if not fund or not row.get("valuation_date") or not row.get("nav"):
                            continue
                        reported_ohlc = {key: (row.get(key) or "").strip() or None
                                         for key in ("open", "high", "low", "close")}
                        is_etf_class = "ETF" in fund["name"].upper()
                        if all(reported_ohlc.values()):
                            ohlc_basis = "source_reported_ohlc"
                        elif not is_etf_class:
                            # An open-end mutual fund has one daily NAV point,
                            # not an intraday trading range. Keep that basis explicit.
                            reported_ohlc = {key: row["nav"] for key in ("open", "high", "low", "close")}
                            ohlc_basis = "single_daily_nav"
                        else:
                            ohlc_basis = None
                        self._navs.setdefault(fund["source_fund_id"], []).append({
                            "source_fund_id": fund["source_fund_id"],
                            "valuation_date": row["valuation_date"],
                            "nav": row["nav"], **reported_ohlc,
                            "ohlc_basis": ohlc_basis, "currency": "USD",
                            "source_id": nav_source_id,
                            "source_url": row.get("source_url") or (
                                f"https://query1.finance.yahoo.com/v8/finance/spark?symbols={row.get('ticker','')}&range=1mo&interval=1d"
                                if nav_source_id == "us_yahoo_mutual_fund_navs"
                                else f"https://api.nasdaq.com/api/quote/{row.get('ticker','')}/historical?assetclass=mutualfunds"
                            ),
                        })

    def check_availability(self) -> dict[str, Any]:
        self._load()
        return {"available": True, "fund_records": len(self._records or [])}

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
