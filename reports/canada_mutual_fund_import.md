# Canada mutual-fund NAV research and import

## Imported official source

Scotiabank/ScotiaFunds publishes a daily Excel workbook containing fund name,
series, fund code, currency, valuation date and NAV. The workbook was downloaded
from:

`https://2edd7e4a-a2d0-4023-bcb4-a5d649e18cd8-funds-sites.livedoc.transmissionmedia.ca/assets/static/daily-nav-exports/daily-nav-data-EN.xlsx`

## Result

- Rows extracted/imported: **373**
- NAV observations imported: **373**
- CAD rows: **346**
- USD rows: **27**
- ETF-labelled rows: **2**
- Mutual-fund rows: **371**
- Latest valuation date: **2026-10-23**
- Fund codes are retained as the source identifier/ticker field.

The workbook has no category column. The ETL derives a broad subcategory from
explicit fund-name terms such as Canadian equity, global equity, balanced,
fixed income, money market and infrastructure. These derived categories are
marked as classification metadata rather than source-published classifications.

## Coverage limitation

Canada does not publish one free government bulk file containing every Canadian
mutual-fund share class and daily NAV. Fundata and QuoteMedia describe broad
Canadian coverage, but their complete databases/NAV feeds are licensed. SIMA
publishes industry statistics rather than a fund-level NAV master. The project
therefore imports the complete public Scotia workbook and records the other
official/public sources as coverage candidates instead of claiming that 373
rows represent every Canadian fund in existence.

Research sources:

- [Scotia daily mutual-fund prices](https://gtb.scotiabank.com/content/scotiabank/ca/en/personal/rates-prices/mutual-fund-prices.html)
- [SIMA statistics](https://sima-amvi.ca/research-statistics/statistics/)
- [Fundata database description](https://mdl-data.library.utoronto.ca/items/show/1797)
- [QuoteMedia Canadian fund coverage](https://sanjose.wdev.quotemedia.com/coverage/fund_research)
