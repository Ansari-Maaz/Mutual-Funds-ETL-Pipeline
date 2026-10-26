"""Public French fund NAV table from La Cote Bleue (ISIN-linked snapshot)."""
from __future__ import annotations
import csv
from datetime import date
from pathlib import Path
from typing import Any, Iterable
from app.connectors.base import BaseConnector
ROOT=Path(__file__).resolve().parents[2]
RAW=ROOT/'data/raw/france/lacote_bleue_navs.csv'
URL='https://actusite.lacotebleue.fr/opcvm/'

def _category(name:str)->str:
 n=name.casefold()
 if any(x in n for x in ('oblig','bond','rente','fixed income')): return 'Fixed income'
 if any(x in n for x in ('monétaire','money market','liquid')): return 'Money market'
 if any(x in n for x in ('immobilier','property','real estate')): return 'Real estate'
 if any(x in n for x in ('diversif','allocation','patrimoine','horizon','multi')): return 'Mixed allocation'
 if any(x in n for x in ('etf','index','mib')): return 'Index/ETF'
 if any(x in n for x in ('equity','actions','euro','europe','world','monde','value')): return 'Equity'
 return 'Other'
class FrLaCoteBleueConnector(BaseConnector):
 source_id='fr_lacotebleue_navs'; country_code='FR'
 def __init__(self): self._records=None; self._navs={}
 def get_source_metadata(self)->dict[str,Any]: return {'country_code':'FR','organization':'La Cote Bleue','source_name':'Public French fund NAV table','endpoint_url':URL,'license_status':'Public; terms to confirm'}
 def _load(self):
  self._records=[]; self._navs={}
  with RAW.open(encoding='utf-8',newline='') as f:
   for row in csv.DictReader(f):
    isin=row['isin'].strip().upper(); name=row['name'].strip(); cur=row['currency'].strip().upper()
    if not isin or not name or len(cur)!=3: continue
    try: nav=float(row['nav'])
    except (TypeError,ValueError): continue
    if nav<=0: continue
    sid=f'FR-LCB-{isin}'
    self._records.append({'source_fund_id':sid,'name':name,'legal_name':name,'provider':row['provider'].strip() or None,'category':_category(name),'fund_type':'Mutual fund','domicile_country':'FR','currency':cur,'isin':isin,'status':'NAV published','official_url':URL})
    self._navs[sid]=[{'source_fund_id':sid,'valuation_date':row['valuation_date'],'nav':row['nav'],'currency':cur}]
 def check_availability(self): self._load(); return {'available':True,'fund_records':len(self._records),'nav_records':len(self._navs)}
 def extract_funds(self,start_date:date|None=None,end_date:date|None=None)->Iterable[dict[str,Any]]:
  if self._records is None:self._load()
  return iter(self._records)
 def extract_nav_history(self,source_fund_id,start_date:date|None=None,end_date:date|None=None)->Iterable[dict[str,Any]]:
  if self._records is None:self._load()
  return iter(self._navs.get(source_fund_id,[]))
