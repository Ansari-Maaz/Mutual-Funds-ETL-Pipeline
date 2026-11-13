# Twelve Data vs FundFlow US mutual fund comparison — 2026-10-30

Generated 2026-11-06T13:51:43.691508+00:00.

## Scope

Ten US mutual-fund share classes were compared using Twelve Data's standard fund directory and daily time-series endpoints. The requested valuation date was matched exactly. This run did not call the premium full-profile endpoint or write Twelve Data values into FundFlow.

FundFlow's comparison values are the stored daily observations for the same fund/date. In this database snapshot they come from Yahoo Finance, so this is a vendor-to-vendor price comparison, not a comparison against issuer-verified NAV.

## Daily price comparison

| Ticker | FundFlow fund name | Twelve Data close | FundFlow value | TD − FundFlow, rounded to cents | Same to nearest cent |
|---|---|---:|---:|---:|:---:|
| VFIAX | Vanguard 500 Index Fund — Admiral Shares | 699.87000 | 699.8700000000 | 0.00 | Yes |
| VTSAX | Vanguard Total Stock Market Index Fund — Admiral Shares | 180.85001 | 180.8500000000 | 0.00 | Yes |
| FXAIX | Fidelity 500 Index Fund | 263.5 | 263.5000000000 | 0.00 | Yes |
| SWPPX | Schwab S&P 500 Index Fund | 19.59000 | 19.5900000000 | 0.00 | Yes |
| FCNTX | Fidelity Contrafund | 26.71000 | 26.7100000000 | 0.00 | Yes |
| DODGX | Dodge & Cox Stock Fund — Class I | 17.89000 | 17.8900000000 | 0.00 | Yes |
| FBALX | Fidelity Balanced Fund | 32.090000 | 32.0900000000 | 0.00 | Yes |
| VWELX | VANGUARD WELLINGTON FUND — Investor Shares | 46.64000 | 46.6400000000 | 0.00 | Yes |
| VBTLX | Vanguard Total Bond Market Index Fund — Admiral Shares | 9.40000 | 9.3800000000 | 0.02 | No |
| VTIAX | Vanguard Total International Stock Index Fund — Admiral Shares | 44.19000 | 44.1900000000 | 0.00 | Yes |

## Findings

- Exact ticker, country, currency, and valuation-date comparisons matched for all 10 funds; endpoint errors: 0.
- Daily values were exactly equal for 8/10 funds and equal to the nearest cent for 9/10. VTSAX differs by $0.00001/share, which rounds to the same cent; VBTLX differs by $0.02/share (Twelve Data $9.40 vs FundFlow $9.38).
- Names differ in six rows only by capitalization and share-class punctuation. Twelve Data labels all 10 as `Mutual Fund`; FundFlow labels them `Open-end mutual fund`.
- Twelve Data returned `request_access_via_add_ons` for ISIN and CUSIP, so those fields are marked unavailable to this subscription, not as data mismatches.
- Exchange/MIC/timezone are returned by Twelve Data but are not stored in the FundFlow core profile. FundFlow stores one daily NAV/price value rather than OHLC; Twelve Data's open/high/low are not separate FundFlow observations.

## Field-level counts

There are 200 comparisons: 72 exact matches, 28 exact-value/label differences, 80 fields not stored in FundFlow, and 20 identifier fields unavailable under the Twelve Data subscription. These totals describe field coverage and exact labels as well as NAV values; the price comparison above is the useful parity metric.

Detailed values, types, and per-endpoint outcomes are in the adjacent JSON report.
