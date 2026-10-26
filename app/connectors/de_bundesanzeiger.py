"""Public Federal Gazette (Fondsdata) German-market fund prices and NAVs."""
from __future__ import annotations
import csv
from datetime import date
from pathlib import Path
from typing import Any
from app.connectors.base import BaseConnector

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/germany/bundesanzeiger_fund_prices.csv"
URL = "https://www.bundesanzeiger.de/pub/en/fondsdata"

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
    def __init__(self): self._records = None; self._navs = {}
    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code":"DE", "organization":"Bundesanzeiger / Federal Gazette",
          "source_name":"Public German-market fund prices and NAVs (Fondsdata)",
          "endpoint_url":URL, "license_status":"Public; terms to confirm"}
    def _load(self):
        self._records=[]; self._navs={}
        with RAW.open(encoding="utf-8-sig", newline="") as f:
            for row in csv.DictReader(f):
                isin=row["isin"].strip().split("/")[0].strip(); name=row["name"].strip()
                if not isin or not name: continue
                sid=f"DE-BANZ-{isin}"
                cur=row["currency"].strip().upper()
                try: nav_value=float(row["nav"])
                except ValueError: continue
                if len(cur)!=3 or nav_value<=0: continue
                self._records.append({"source_fund_id":sid,"name":name,"legal_name":name,
                  "provider":row["provider"].strip() or None,"category":_category(name),
                  "fund_type":"Mutual fund","domicile_country":"DE" if isin.startswith("DE") else None,
                  "currency":cur,"isin":isin,"status":"Price published","official_url":URL})
                self._navs[sid]=[{"source_fund_id":sid,"valuation_date":row["valuation_date"],"nav":row["nav"],"currency":cur}]
    def check_availability(self):
        self._load(); return {"available":True,"fund_records":len(self._records),"nav_records":len(self._navs)}
    def extract_funds(self,start_date:date|None=None,end_date:date|None=None):
        if self._records is None:self._load()
        return iter(self._records)
    def extract_nav_history(self,source_fund_id,start_date:date|None=None,end_date:date|None=None):
        if self._records is None:self._load()
        return iter(self._navs.get(source_fund_id,[]))
