"""Mexican fund master and latest NAVs from the public BMV JSON service."""
from __future__ import annotations
import csv
from datetime import date, datetime
from pathlib import Path
from typing import Any
from app.connectors.base import BaseConnector

ROOT = Path(__file__).resolve().parents[2]
FUNDS = ROOT / 'data/raw/mexico/bmv_mexico_funds.csv'
NAVS = ROOT / 'data/raw/mexico/bmv_mexico_navs.csv'
URL = 'https://www.bmv.com.mx/es/Grupo_BMV/BmvJsonOperadora'

class BmvMexicoConnector(BaseConnector):
    source_id = 'bmv_mexico_funds'
    country_code = 'MX'
    def __init__(self): self._funds = None; self._navs = {}
    def get_source_metadata(self) -> dict[str, Any]:
        return {'country_code':'MX','organization':'BMV','source_name':'BMV Mexico fund prices','endpoint_url':URL,'license_status':'Public; terms to confirm'}
    def _load(self):
        self._funds=[]; self._navs={}
        with FUNDS.open(encoding='utf-8-sig', newline='') as f:
            allowed={'source_fund_id','ticker','name','legal_name','manager','category','fund_type','currency','isin','domicile_country','status','official_url'}
            self._funds=[{k:v for k,v in r.items() if k in allowed} for r in csv.DictReader(f)]
        with NAVS.open(encoding='utf-8-sig', newline='') as f:
            for r in csv.DictReader(f):
                raw=(r.get('valuation_date') or '').strip()
                try: d=datetime.strptime(raw,'%d/%m/%Y').date().isoformat()
                except ValueError:
                    try: d=date.fromisoformat(raw).isoformat()
                    except ValueError: continue
                try: valid_nav = float(r.get('nav')) > 0
                except (TypeError, ValueError): valid_nav = False
                if valid_nav:
                    self._navs.setdefault(r['source_fund_id'],[]).append({'source_fund_id':r['source_fund_id'],'valuation_date':d,'nav':r['nav'],'currency':r.get('currency') or 'MXN'})
    def check_availability(self):
        self._load(); return {'available':True,'fund_records':len(self._funds),'nav_records':sum(map(len,self._navs.values()))}
    def extract_funds(self,start_date=None,end_date=None):
        if self._funds is None: self._load()
        return iter(self._funds)
    def extract_nav_history(self,source_fund_id,start_date=None,end_date=None):
        if self._funds is None: self._load()
        return iter(r for r in self._navs.get(source_fund_id,[]) if (not start_date or date.fromisoformat(r['valuation_date'])>=start_date) and (not end_date or date.fromisoformat(r['valuation_date'])<=end_date))
