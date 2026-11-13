# U.S. fund coverage audit

Generated: 2026-11-13T14:14:57.473686+00:00
SEC N-PORT data set inspected: 2026q3

## Coverage

| Metric | Funds |
| --- | ---: |
| U.S. fund records | 39,139 |
| With NAV observations | 25,263 (64.55%) |
| With official portfolio holdings | 31,634 (80.82%) |
| With both | 24,023 (61.38%) |
| Missing NAV | 13,876 |
| Missing holdings | 7,505 |
| Missing both | 6,265 |

## Why NAV is missing

| Reason | Funds |
| --- | ---: |
| `no_public_ticker_in_sec_class_snapshot` | 9,634 |
| `issuer_not_yet_mapped` | 2,825 |
| `issuer_site_does_not_expose_machine_readable_nav` | 678 |
| `issuer_adapter_not_implemented` | 531 |
| `ticker_not_returned_by_integrated_issuer_adapter` | 208 |

## Why holdings are missing

| Reason | Funds |
| --- | ---: |
| `series_absent_from_latest_n_port_dataset` | 7,496 |
| `latest_n_port_filing_reports_no_positions` | 8 |
| `no_sec_series_identifier` | 1 |

## NAV observations by source

| Source | Funds |
| --- | ---: |
| `us_yahoo_mutual_fund_navs` | 24,729 |
| `us_nasdaq_mutual_fund_navs` | 533 |
| `us_nasdaq_etf_market_prices` | 1 |

## Holdings by source

| Source | Funds |
| --- | ---: |
| `sec_edgar_nport` | 18,724 |
| `sec_edgar_nport_bulk` | 12,910 |

## Largest remaining gaps

| Provider | Funds | Missing NAV | Missing holdings | Missing both |
| --- | ---: | ---: | ---: | ---: |
| ETF Opportunities Trust | 569 | 486 | 471 | 461 |
| GraniteShares ETF Trust | 527 | 468 | 442 | 439 |
| Themes ETF Trust | 484 | 419 | 345 | 344 |
| Tidal Trust II | 548 | 385 | 347 | 339 |
| Corgi ETF Trust I | 328 | 328 | 193 | 193 |
| Direxion Shares ETF Trust | 364 | 219 | 231 | 217 |
| Investment Managers Series Trust II | 332 | 219 | 201 | 184 |
| MASSMUTUAL SELECT FUNDS | 282 | 235 | 118 | 118 |
| NATIONWIDE VARIABLE INSURANCE TRUST | 235 | 235 | 59 | 59 |
| LINCOLN VARIABLE INSURANCE PRODUCTS TRUST | 258 | 258 | 23 | 23 |
| JNL SERIES TRUST | 260 | 260 | 4 | 4 |
| Innovator ETFs Trust | 212 | 210 | 31 | 31 |
| PROSHARES TRUST | 264 | 107 | 114 | 107 |
| NATIONWIDE MUTUAL FUNDS | 299 | 143 | 77 | 74 |
| ETF Series Solutions | 176 | 106 | 105 | 101 |
| EQ ADVISORS TRUST | 206 | 206 | 3 | 3 |
| BLACKROCK LIQUIDITY FUNDS | 118 | 90 | 118 | 90 |
| John Hancock Funds II | 387 | 125 | 74 | 74 |
| Volatility Shares Trust | 110 | 107 | 91 | 91 |
| RBB FUND, INC. | 183 | 108 | 80 | 79 |
| Milliman Variable Insurance Trust | 95 | 95 | 93 | 93 |
| AMERICAN FUNDS INSURANCE SERIES | 163 | 163 | 4 | 4 |
| Tidal Trust III | 117 | 82 | 72 | 67 |
| GOLDMAN SACHS TRUST | 576 | 18 | 130 | 14 |
| BLACKROCK FUNDS | 146 | 109 | 38 | 34 |

## Official-source constraints observed

See `docs/US_OFFICIAL_SOURCES.md` for the verified status of every issuer site.
Automated access is blocked or unusable at several large issuers (Fidelity,
John Hancock, MassMutual, Invesco, Charles Schwab); Nationwide renders NAV only
in client-side JavaScript. Those gaps stay empty rather than being filled from a
non-official feed.
