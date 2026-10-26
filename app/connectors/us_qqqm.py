"""Verified QQQM ETF identity and daily NAV/close import."""
from __future__ import annotations
import csv
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from app.connectors.base import BaseConnector

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / 'data/raw/united_states/qqqm_nav.csv'

class QqqmEtfConnector(BaseConnector):
    source_id = 'us_qqqm_etf'
    country_code = 'US'

    def __init__(self): self._fund = None; self._navs = []
    def get_source_metadata(self) -> dict[str, Any]:
        return {'country_code':'US','organization':'Invesco','source_name':'Invesco NASDAQ 100 ETF (QQQM)','endpoint_url':'https://query1.finance.yahoo.com/v8/finance/chart/QQQM?interval=1d&range=1mo','license_status':'Public reference data'}
    def _load(self):
        self._navs=[]
        with RAW.open(encoding='utf-8-sig',newline='') as f:
            rows=list(csv.DictReader(f))
        self._fund={'source_fund_id':'QQQM','name':'Invesco NASDAQ 100 ETF','legal_name':'Invesco NASDAQ 100 ETF','domicile_country':'US','currency':'USD','isin':'US46138G6492','provider':'Invesco','manager':'Invesco','category':'US Equity','fund_type':'ETF','status':'Active','official_url':'https://www.invesco.com/us/en/financial-products/etfs/invesco-nasdaq-100-etf.html','ticker':'QQQM'}
        for row in rows:
            self._navs.append({'source_fund_id':'QQQM','valuation_date':row['valuation_date'],'nav':row['nav'],'currency':'USD'})
    def check_availability(self):
        self._load(); return {'available':True,'fund_records':1,'nav_records':len(self._navs)}
    def extract_funds(self, start_date=None, end_date=None):
        if self._fund is None: self._load()
        return iter([self._fund])
    def extract_nav_history(self, source_fund_id, start_date=None, end_date=None):
        if self._fund is None: self._load()
        return iter(r for r in self._navs if (not start_date or date.fromisoformat(r['valuation_date']) >= start_date) and (not end_date or date.fromisoformat(r['valuation_date']) <= end_date))
