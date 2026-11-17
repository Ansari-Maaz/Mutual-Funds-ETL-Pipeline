# Current DB coverage by country (funds table, snapshot 2026-11-17)

Columns = number of funds having that field (nav/hold = funds with >=1 NAV observation / holding). Funds table fields: isin, ticker, manager, administrator, category, fund_type, inception_date, net_assets(+date), currency, provider, official_url, target_audience, status. Other tables: nav_observations, portfolio_holdings, holding_metrics, fund_profile_snapshots (JSONB payload).

```
country funds nav hold isin ticker mgr adm cat incep netassets cur
US 39139 25694 33372 169 31688 33080 32219 1095 16838 34130 39139
BR 37875 25678 0 0 0 37765 37873 27739 37875 35002 37875
FR 28465 90 0 25570 0 0 0 90 0 0 28465
LU 25901 1944 0 1944 49 16824 0 1944 0 0 25901
CN 14170 0 0 0 0 0 0 0 0 0 14170
IE 6725 0 0 0 0 0 0 0 0 0 6725
DE 6429 0 0 0 0 6377 0 0 0 0 6429
MX 5151 3486 0 5151 5151 5151 0 5151 0 0 5151
GB 4261 286 0 33 33 3975 0 4261 0 0 4261
?? 3689 302 0 302 0 1132 0 1434 0 0 302
ES 3116 0 0 3116 0 0 0 0 0 0 3116
JP 2741 0 0 0 0 2741 0 2741 2375 0 0
CH 2054 47 0 47 0 0 0 47 0 0 2054
ZA 1945 0 0 0 0 0 0 0 0 0 1945
DK 1486 0 0 0 0 1088 0 0 0 0 1486
NL 1397 84 0 84 84 1112 0 84 0 0 1397
IT 1360 14 0 14 0 1332 0 14 0 0 1360
SE 726 0 0 688 0 0 0 0 0 0 726
CA 373 373 0 0 323 373 0 373 0 0 373
AU 97 5 0 0 0 96 0 96 0 0 97
```

Existing registered sources per country: see app/catalog.py and app/connectors/*.py in /media/asim/4_TB_1/MFAPI/MF ETL PIPELINE
