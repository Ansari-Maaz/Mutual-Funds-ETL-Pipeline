"""Public UK FundsLibrary unit-price snapshot with Investment Association sectors."""
from __future__ import annotations
import csv
from datetime import date
from pathlib import Path
from typing import Any
from app.connectors.base import BaseConnector

ROOT=Path(__file__).resolve().parents[2]
RAW=ROOT/'data/raw/united_kingdom/fundslibrary_unit_prices.csv'
URL='https://www.fundslibrary.co.uk/FundsLibrary.BrandedTools/OnlineIps/FundCentral/Collective/UnitPrices'

class UkFundsLibraryConnector(BaseConnector):
    source_id='uk_fundslibrary_unit_prices'; country_code='GB'
    def __init__(self): self._records=None; self._navs={}
    def get_source_metadata(self)->dict[str,Any]:
        return {'country_code':'GB','organization':'FundsLibrary','source_name':'UK public unit prices','endpoint_url':URL,'license_status':'Public; terms to confirm'}
    def _load(self):
        self._records=[]; self._navs={}
        with RAW.open(encoding='utf-8-sig',newline='') as f:
            for r in csv.DictReader(f):
                sid=r['source_fund_id']; self._records.append({k:r.get(k,'') for k in ['source_fund_id','ticker','name','legal_name','category','fund_type','currency','isin','domicile_country','status','official_url']})
                self._navs[sid]=[{'source_fund_id':sid,'valuation_date':r['valuation_date'],'nav':r['nav'],'currency':'GBP'}]
    def check_availability(self): self._load(); return {'available':True,'fund_records':len(self._records),'nav_records':sum(map(len,self._navs.values()))}
    def extract_funds(self,start_date=None,end_date=None):
        if self._records is None:self._load()
        return iter(self._records)
    def extract_nav_history(self,source_fund_id,start_date=None,end_date=None):
        if self._records is None:self._load()
        return iter(r for r in self._navs.get(source_fund_id,[]) if not start_date or date.fromisoformat(r['valuation_date'])>=start_date)
