"""Free daily NAV observations published by Borsa Italiana for open funds."""
from __future__ import annotations
import csv
from datetime import date
from pathlib import Path
from typing import Any
from app.connectors.base import BaseConnector

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data/raw/italy/borsa_italiana_daily_nav.csv"
URL = "https://www.borsaitaliana.it/fondi/fondi-aperti/nav/nav.en.htm"

class ItBorsaNavConnector(BaseConnector):
    source_id = "it_borsa_navs"
    country_code = "IT"
    def __init__(self): self._records = None; self._navs = {}
    def get_source_metadata(self) -> dict[str, Any]:
        return {"country_code":"IT","organization":"Borsa Italiana",
          "source_name":"Daily NAV of open funds","endpoint_url":URL,
          "license_status":"Public; terms to confirm"}
    def _load(self):
        self._records=[]; self._navs={}
        with RAW.open(encoding="utf-8-sig",newline="") as f:
            for row in csv.DictReader(f):
                isin=row["isin"].strip(); cur=row["currency"].strip().upper()
                if not isin or len(cur)!=3: continue
                sid=f"IT-BORSA-{isin}"
                self._records.append({"source_fund_id":sid,
                  "name":f"Open fund — {isin}","legal_name":None,
                  "provider":"Borsa Italiana","category":"Open fund (category not published in NAV file)",
                  "fund_type":"Mutual fund","domicile_country":"IT" if isin.startswith("IT") else None,
                  "currency":cur,"isin":isin,"status":"NAV published","official_url":URL})
                self._navs[sid]=[{"source_fund_id":sid,"valuation_date":row["valuation_date"],"nav":row["nav"],"currency":cur}]
    def check_availability(self):
        self._load(); return {"available":True,"fund_records":len(self._records),"nav_records":len(self._navs)}
    def extract_funds(self,start_date:date|None=None,end_date:date|None=None):
        if self._records is None:self._load()
        return iter(self._records)
    def extract_nav_history(self,source_fund_id,start_date:date|None=None,end_date:date|None=None):
        if self._records is None:self._load()
        return iter(self._navs.get(source_fund_id,[]))
