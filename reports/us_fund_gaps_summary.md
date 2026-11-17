# U.S. fund coverage audit

Generated: 2026-11-16T16:31:34.129403+00:00
SEC N-PORT data set inspected: 2026q3

## Coverage

| Metric | Funds |
| --- | ---: |
| U.S. fund records | 39,139 |
| With NAV observations | 25,675 (65.6%) |
| With official portfolio holdings | 33,372 (85.27%) |
| With both | 25,258 (64.53%) |
| Missing NAV | 13,464 |
| Missing holdings | 5,767 |
| Missing both | 5,350 |

## Why NAV is missing

| Reason | Funds |
| --- | ---: |
| `no_public_ticker_in_sec_class_snapshot` | 9,429 |
| `issuer_not_yet_mapped` | 2,634 |
| `issuer_site_does_not_expose_machine_readable_nav` | 677 |
| `issuer_adapter_not_implemented` | 527 |
| `ticker_not_returned_by_integrated_issuer_adapter` | 197 |

## Why holdings are missing

| Reason | Funds |
| --- | ---: |
| `series_absent_from_latest_n_port_dataset` | 5,762 |
| `latest_n_port_filing_reports_no_positions` | 4 |
| `no_sec_series_identifier` | 1 |

## NAV observations by source

| Source | Funds |
| --- | ---: |
| `us_yahoo_mutual_fund_navs` | 23,529 |
| `us_capital_group_fund_pages` | 869 |
| `us_nasdaq_mutual_fund_navs` | 516 |
| `us_vanguard_fund_products` | 414 |
| `sec_nmfp_money_market` | 169 |
| `us_ssga_spdr_navs` | 143 |
| `us_graniteshares_fund_pages` | 34 |
| `us_nasdaq_etf_market_prices` | 1 |

## Holdings by source

| Source | Funds |
| --- | ---: |
| `sec_edgar_nport_bulk` | 29,737 |
| `sec_edgar_nport` | 2,542 |
| `sec_nmfp_bulk` | 1,093 |

## Largest remaining gaps

| Provider | Funds | Missing NAV | Missing holdings | Missing both |
| --- | ---: | ---: | ---: | ---: |
| ETF Opportunities Trust | 569 | 485 | 471 | 460 |
| GraniteShares ETF Trust | 527 | 464 | 442 | 439 |
| Themes ETF Trust | 484 | 419 | 343 | 342 |
| Tidal Trust II | 548 | 385 | 346 | 338 |
| Corgi ETF Trust I | 328 | 328 | 193 | 193 |
| Direxion Shares ETF Trust | 364 | 217 | 218 | 212 |
| Investment Managers Series Trust II | 332 | 214 | 200 | 180 |
| MASSMUTUAL SELECT FUNDS | 282 | 235 | 118 | 118 |
| NATIONWIDE VARIABLE INSURANCE TRUST | 235 | 230 | 50 | 50 |
| LINCOLN VARIABLE INSURANCE PRODUCTS TRUST | 258 | 256 | 21 | 21 |
| JNL SERIES TRUST | 260 | 258 | 2 | 2 |
| Innovator ETFs Trust | 212 | 210 | 27 | 27 |
| NATIONWIDE MUTUAL FUNDS | 299 | 143 | 74 | 74 |
| PROSHARES TRUST | 264 | 107 | 107 | 107 |
| ETF Series Solutions | 176 | 105 | 105 | 101 |
| EQ ADVISORS TRUST | 206 | 204 | 0 | 0 |
| Volatility Shares Trust | 110 | 107 | 91 | 91 |
| John Hancock Funds II | 387 | 125 | 66 | 66 |
| Milliman Variable Insurance Trust | 95 | 95 | 93 | 93 |
| RBB FUND, INC. | 183 | 98 | 75 | 69 |
| AMERICAN FUNDS INSURANCE SERIES | 163 | 163 | 4 | 4 |
| Tidal Trust III | 117 | 81 | 72 | 66 |
| SUNAMERICA SERIES TRUST | 143 | 143 | 0 | 0 |
| Roundhill ETF Trust | 113 | 72 | 68 | 68 |
| SPDR INDEX SHARES FUNDS | 99 | 66 | 74 | 66 |

## Official-source constraints observed

See `docs/US_OFFICIAL_SOURCES.md` for the verified status of every issuer site.
Automated access is blocked or unusable at several large issuers (Fidelity,
John Hancock, MassMutual, Invesco, Charles Schwab); Nationwide renders NAV only
in client-side JavaScript. Those gaps stay empty rather than being filled from a
non-official feed.
