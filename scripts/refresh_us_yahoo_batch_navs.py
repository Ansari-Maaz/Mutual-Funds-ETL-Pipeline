"""Batch Yahoo chart refresh for US mutual-fund daily NAVs.

Yahoo's public spark endpoint accepts multiple tickers per request. The daily
close is treated as NAV, matching the project's documented fallback source.
"""
from __future__ import annotations
import csv, json, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path
import psycopg

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'data/raw/united_states/nasdaq_mutual_fund_navs.csv'
URL = 'https://query1.finance.yahoo.com/v8/finance/spark'

def main():
    with psycopg.connect('postgresql://mfetl:mfetl@localhost:5433/mfetl') as c:
        tickers=[r[0] for r in c.execute("select distinct ticker from funds where source_id='sec_open_end_fund_classes' and ticker is not null and ticker<>'' order by ticker")]
    found={}
    for i in range(0,len(tickers),20):
        batch=tickers[i:i+20]
        query='symbols='+','.join(batch)+'&range=1mo&interval=1d'
        req=urllib.request.Request(URL+'?'+query,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=30) as r: payload=json.load(r)
        except Exception as exc:
            print(f'batch={i//100+1} error={exc}',flush=True); continue
        for ticker, data in payload.items():
            ts=data.get('timestamp') or []; closes=data.get('close') or []
            pairs=[(t,v) for t,v in zip(ts,closes) if v is not None]
            if not pairs: continue
            stamp, nav=pairs[-1]
            found[ticker]={'ticker':ticker,'valuation_date':datetime.fromtimestamp(stamp,tz=timezone.utc).date().isoformat(),'nav':str(nav),'source_url':URL+'?symbols='+ticker+'&range=1mo&interval=1d'}
        if (i//20+1)%25==0 or i+20>=len(tickers): print(f'processed={min(i+20,len(tickers))}/{len(tickers)} successful={len(found)}',flush=True)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    with OUT.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=['ticker','valuation_date','nav','source_url']); w.writeheader(); w.writerows(sorted(found.values(),key=lambda x:x['ticker']))
    print(f'wrote={len(found)} path={OUT}')

if __name__=='__main__': main()
