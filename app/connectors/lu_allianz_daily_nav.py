"""Official Allianz Global Investors Luxembourg daily-NAV table."""
from __future__ import annotations
import csv
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from app.connectors.base import BaseConnector
ROOT=Path(__file__).resolve().parents[2]; RAW=ROOT/'data/raw/luxembourg/allianz_luxembourg_daily_nav.csv'
URL='https://regulatory.allianzgi.com/en-gb/facilities-services/luxemburg-en/funds/mutual-funds'
class LuAllianzDailyNavConnector(BaseConnector):
 source_id='lu_allianz_daily_navs'; country_code='LU'
 def __init__(self): self._records=None;self._navs={}
 def get_source_metadata(self)->dict[str,Any]: return {'country_code':'LU','organization':'Allianz Global Investors','source_name':'Official Luxembourg daily NAV table','endpoint_url':URL,'license_status':'Public; terms to confirm'}
 def _load(self):
  self._records=[];self._navs={}
  with RAW.open(encoding='utf-8',newline='') as f:
   for row in csv.DictReader(f):
    isin=row['isin'].strip().upper();name=row['name'].strip();cur=row['currency'].strip().upper()
    try: nav=float(row['nav'])
    except: continue
    if not isin or not name or len(cur)!=3 or nav<=0: continue
    sid=f'LU-ALLIANZ-{isin}-{row["share_class"].strip()}'
    self._records.append({'source_fund_id':sid,'name':name,'legal_name':name,'provider':row['provider'],'category':row['asset_class'] or 'Other','fund_type':'Mutual fund','domicile_country':'LU','currency':cur,'isin':isin,'status':'NAV published','official_url':URL,'target_audience':row['sfdr_category'] or None})
    self._navs[sid]=[{'source_fund_id':sid,'valuation_date':row['valuation_date'],'nav':row['nav'],'currency':cur}]
 def check_availability(self):self._load();return {'available':True,'fund_records':len(self._records),'nav_records':len(self._navs)}
 def extract_funds(self,start_date:date|None=None,end_date:date|None=None)->Iterable[dict[str,Any]]:
  if self._records is None:self._load()
  return iter(self._records)
 def extract_nav_history(self,source_fund_id:str,start_date:date|None=None,end_date:date|None=None)->Iterable[dict[str,Any]]:
  if self._records is None:self._load()
  return iter(self._navs.get(source_fund_id,[]))
