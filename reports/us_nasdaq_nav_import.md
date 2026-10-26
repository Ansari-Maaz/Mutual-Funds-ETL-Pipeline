# US mutual-fund NAV import

The SEC fund-master connector now also reads the raw ticker-matched NAV file
`data/raw/united_states/nasdaq_mutual_fund_navs.csv`. The initial VFIAX history
was verified against Nasdaq; the completed full-universe refresh used Yahoo's
public multi-symbol chart endpoint as the free fallback so the entire ticker
universe could be processed efficiently.

## Import result

- Fund master records processed: 39,138
- Distinct ticker symbols queried: 29,264
- NAV observations imported: 24,825
- Fund classes with NAV: 24,825
- Fund matched: Vanguard 500 Index Fund — Admiral Shares (`VFIAX`)
- Currency: USD
- Latest valuation date: 2026-10-23
- Latest NAV: 703.82 USD

The original verified NAV values came from Nasdaq's public historical endpoint:
`https://api.nasdaq.com/api/quote/VFIAX/historical?assetclass=mutualfunds`

The completed batch refresh used Yahoo's public chart endpoint:
`https://query1.finance.yahoo.com/v8/finance/spark?symbols=...&range=1mo&interval=1d`

The importer matches by ticker, stores the valuation date and USD currency, and
does not create a NAV when the response cannot be matched to a fund in the SEC
master. The same connector can be extended with additional ticker/date rows;
large-scale refreshes must remain rate-limited because these public endpoints
are not official bulk NAV services. Tickers with no usable daily close remain
without a NAV and are not fabricated.
