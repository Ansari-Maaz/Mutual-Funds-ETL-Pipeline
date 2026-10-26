"""Public Euronext Amsterdam fund-list NAV/last-price snapshot."""
from __future__ import annotations
import csv
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from app.connectors.base import BaseConnector
ROOT=Path(__file__).resolve().parents[2]; RAW=ROOT/'data/raw/netherlands/euronext_amsterdam_funds.csv'
URL='https://live.euronext.com/nl/products/funds/list'
def _category(name:str)->str:
 n=name.casefold()
 if any(x in n for x in ('bond','oblig','fixed income')): return 'Fixed income'
 if any(x in n for x in ('property','real estate','vastgoed')): return 'Real estate'
 if any(x in n for x in ('mix','balanced','allocation')): return 'Mixed allocation'
 if any(x in n for x in ('money market','liquid')): return 'Money market'
 if any(x in n for x in ('etf','index')): return 'Index/ETF'
 if any(x in n for x in ('equity','aandelen','stock','world','global')): return 'Equity'
 return 'Other'
class NlEuronextFundsConnector(BaseConnector):
 source_id='nl_euronext_fund_navs'; country_code='NL'
 def __init__(self): self._records=None; self._navs={}
 def get_source_metadata(self)->dict[str,Any]: return {'country_code':'NL','organization':'Euronext Amsterdam','source_name':'Public Amsterdam fund list and NAV/last price','endpoint_url':URL,'license_status':'Public; terms to confirm'}
 def _load(self):
  self._records=[];self._navs={}
  with RAW.open(encoding='utf-8-sig',newline='') as f:
   for row in csv.DictReader(f):
    isin=row['isin'].strip().upper(); name=row['name'].strip(); cur=row['currency'].strip().upper()
    try: nav=float(row['nav'])
    except: continue
    if not isin or not name or len(cur)!=3 or nav<=0: continue
    sid=f'NL-EURONEXT-{isin}'
    self._records.append({'source_fund_id':sid,'name':name,'legal_name':name,'provider':'Euronext Amsterdam','category':_category(name),'fund_type':'Mutual fund','domicile_country':'NL','currency':cur,'isin':isin,'ticker':row.get('ticker') or None,'status':'NAV/last price published','official_url':URL})
    self._navs[sid]=[{'source_fund_id':sid,'valuation_date':row['valuation_date'],'nav':row['nav'],'currency':cur}]
 def check_availability(self): self._load(); return {'available':True,'fund_records':len(self._records),'nav_records':len(self._navs)}
 def extract_funds(self,start_date:date|None=None,end_date:date|None=None)->Iterable[dict[str,Any]]:
  if self._records is None:self._load()
  return iter(self._records)
 def extract_nav_history(self,source_fund_id:str,start_date:date|None=None,end_date:date|None=None)->Iterable[dict[str,Any]]:
  if self._records is None:self._load()
  return iter(self._navs.get(source_fund_id,[]))
