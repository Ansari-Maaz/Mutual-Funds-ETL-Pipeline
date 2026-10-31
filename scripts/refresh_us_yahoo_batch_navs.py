"""Batch Yahoo chart refresh for US mutual-fund daily NAVs.

Yahoo's public spark endpoint accepts multiple tickers per request. The daily
close is treated as NAV, matching the project's documented fallback source.
"""
from __future__ import annotations
import csv, json, logging, urllib.parse, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path
import psycopg
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.config import database_url
OUT = ROOT / 'data/raw/united_states/yahoo_mutual_fund_navs.csv'
URL = 'https://query1.finance.yahoo.com/v8/finance/spark'
LOGGER = logging.getLogger(__name__)

def load_existing_rows(path):
    if not path.exists():
        return {}
    with path.open(newline='', encoding='utf-8-sig') as stream:
        return {
            row['ticker']: row
            for row in csv.DictReader(stream)
            if row.get('ticker')
        }


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    with temporary.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['ticker', 'valuation_date', 'nav', 'source_url'])
        writer.writeheader()
        writer.writerows(sorted(rows.values(), key=lambda row: row['ticker']))
        stream.flush()
    temporary.replace(path)


def main():
    db_url = database_url().replace('postgresql+psycopg://', 'postgresql://', 1)
    with psycopg.connect(db_url) as c:
        tickers=[r[0] for r in c.execute("select distinct ticker from funds where source_id='sec_open_end_fund_classes' and ticker is not null and ticker<>'' order by ticker")]
    found=load_existing_rows(OUT)
    failed_batches=0
    updated=0
    for i in range(0,len(tickers),20):
        batch=tickers[i:i+20]
        query='symbols='+','.join(batch)+'&range=1mo&interval=1d'
        req=urllib.request.Request(URL+'?'+query,headers={'User-Agent':'Mozilla/5.0','Accept':'application/json'})
        try:
            with urllib.request.urlopen(req,timeout=30) as r: payload=json.load(r)
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError) as exc:
            failed_batches += 1
            LOGGER.warning('Yahoo batch %d failed: %s: %s', i // 20 + 1, type(exc).__name__, exc)
            continue
        for ticker, data in payload.items():
            ts=data.get('timestamp') or []; closes=data.get('close') or []
            pairs=[(t,v) for t,v in zip(ts,closes) if v is not None]
            if not pairs: continue
            stamp, nav=pairs[-1]
            found[ticker]={'ticker':ticker,'valuation_date':datetime.fromtimestamp(stamp,tz=timezone.utc).date().isoformat(),'nav':str(nav),'source_url':URL+'?symbols='+ticker+'&range=1mo&interval=1d'}
            updated += 1
        if (i//20+1)%25==0 or i+20>=len(tickers): print(f'processed={min(i+20,len(tickers))}/{len(tickers)} updated={updated} retained={len(found) - updated}',flush=True)
    write_rows(OUT, found)
    print(f'updated={updated} retained={len(found) - updated} total={len(found)} path={OUT}')
    if tickers and not updated:
        raise SystemExit(f'No Yahoo NAV rows were retrieved; {failed_batches} batches failed or returned no data')

if __name__=='__main__': main()
