# U.S. fund reference-field gap audit

Generated: 2026-11-16T16:31:49.214205+00:00

## Completeness by field

| Field | Present | Missing | Complete | Official source | Action |
| --- | ---: | ---: | ---: | --- | --- |
| `ticker` | 29,543 | 9,596 | 75.48% | SEC EDGAR company_tickers_mf.json (class ID to ticker) | run enrich-us-funds --tickers |
| `isin` | 169 | 38,970 | 0.43% | SEC N-PORT holding identifiers with CUSIP/ISIN check-digit validation | run enrich-us-funds --isins (only classes that appear as another fund's holding) |
| `category` | 1,095 | 38,044 | 2.8% | Issuer fund directory / product page (e.g. Vanguard all-products directory) | run enrich-us-funds --vanguard; add issuers with published categories |
| `inception_date` | 392 | 38,747 | 1.0% | Issuer fund directory / product page | run enrich-us-funds --vanguard; add issuers with published inception dates |
| `manager` | 33,080 | 6,059 | 84.52% | SEC Form N-CEN ADVISER table (primary adviser) | run sync-sec-ncen-bulk |
| `administrator` | 32,219 | 6,920 | 82.32% | SEC Form N-CEN ADMIN table | run sync-sec-ncen-bulk |
| `net_assets` | 34,071 | 5,068 | 87.05% | SEC N-PORT quarterly bulk NET_ASSETS / N-CEN average net assets | run sync-sec-nport-bulk and sync-sec-ncen-bulk |

## Records by number of missing fields

| Missing fields | Funds |
| ---: | ---: |
| 1 | 32 |
| 2 | 1,310 |
| 3 | 25,255 |
| 4 | 6,321 |
| 5 | 776 |
| 6 | 2,292 |
| 7 | 3,153 |

## Largest providers by missing fields

| Provider | Funds | Missing values | Fields |
| --- | ---: | ---: | --- |
| ETF Opportunities Trust | 569 | 3,584 | category=569, inception_date=569, isin=568, manager=501, administrator=501, net_assets=472, ticker=404 |
| GraniteShares ETF Trust | 527 | 3,306 | isin=527, category=527, inception_date=527, manager=444, administrator=444, net_assets=444, ticker=393 |
| Themes ETF Trust | 484 | 3,070 | isin=484, category=484, inception_date=484, manager=431, administrator=431, ticker=403, net_assets=353 |
| Tidal Trust II | 548 | 3,044 | category=548, inception_date=548, isin=543, manager=415, administrator=415, net_assets=362, ticker=213 |
| Corgi ETF Trust I | 328 | 2,159 | ticker=328, isin=328, category=328, inception_date=328, manager=327, administrator=327, net_assets=193 |
| Direxion Shares ETF Trust | 364 | 1,986 | isin=364, category=364, inception_date=364, manager=241, administrator=241, net_assets=216, ticker=196 |
| Investment Managers Series Trust II | 332 | 1,778 | category=332, inception_date=332, isin=331, manager=251, administrator=251, net_assets=208, ticker=73 |
| GOLDMAN SACHS TRUST | 576 | 1,647 | inception_date=576, isin=572, category=497, net_assets=2 |
| John Hancock Funds II | 387 | 1,413 | isin=387, category=387, inception_date=387, manager=66, administrator=66, net_assets=66, ticker=54 |
| FIDELITY ABERDEEN STREET TRUST | 449 | 1,347 | isin=449, category=449, inception_date=449 |
| PROSHARES TRUST | 264 | 1,222 | inception_date=264, category=263, isin=256, manager=113, administrator=113, net_assets=113, ticker=100 |
| iSHARES TRUST | 390 | 1,196 | category=390, inception_date=390, isin=363, manager=24, administrator=24, net_assets=5 |
| PIMCO FUNDS | 378 | 1,190 | isin=378, inception_date=378, category=372, ticker=47, manager=5, administrator=5, net_assets=5 |
| NATIONWIDE MUTUAL FUNDS | 299 | 1,123 | isin=299, inception_date=299, category=296, manager=61, administrator=61, net_assets=61, ticker=46 |
| LINCOLN VARIABLE INSURANCE PRODUCTS TRUST | 258 | 1,106 | ticker=258, isin=258, inception_date=258, category=256, manager=28, administrator=28, net_assets=20 |
| NATIONWIDE VARIABLE INSURANCE TRUST | 235 | 1,072 | ticker=235, isin=235, inception_date=235, category=229, manager=46, administrator=46, net_assets=46 |
| JPMorgan Trust I | 365 | 1,059 | inception_date=365, isin=364, category=326, ticker=4 |
| JNL SERIES TRUST | 260 | 1,048 | ticker=260, isin=260, inception_date=260, category=258, manager=4, administrator=4, net_assets=2 |
| TIAA-CREF FUNDS | 336 | 1,002 | isin=336, inception_date=336, category=330 |
| ETF Series Solutions | 176 | 936 | category=176, inception_date=176, isin=174, manager=111, administrator=111, net_assets=101, ticker=87 |
| Innovator ETFs Trust | 212 | 933 | isin=212, category=212, inception_date=212, ticker=210, manager=36, administrator=36, net_assets=15 |
| MASSMUTUAL SELECT FUNDS | 282 | 918 | isin=282, category=282, inception_date=282, manager=24, administrator=24, net_assets=24 |
| PRINCIPAL FUNDS, INC. | 303 | 912 | isin=303, inception_date=303, category=299, manager=3, administrator=3, ticker=1 |
| HARTFORD MUTUAL FUNDS, INC | 297 | 891 | isin=297, category=297, inception_date=297 |
| RBB FUND, INC. | 183 | 860 | category=183, inception_date=183, isin=182, manager=88, administrator=88, net_assets=73, ticker=63 |
| EQ ADVISORS TRUST | 206 | 821 | ticker=206, isin=206, inception_date=206, category=203 |
| TRANSAMERICA FUNDS | 264 | 806 | isin=264, inception_date=264, category=257, ticker=18, manager=1, administrator=1, net_assets=1 |
| JANUS INVESTMENT FUND | 256 | 787 | isin=256, inception_date=256, category=250, manager=8, administrator=8, net_assets=8, ticker=1 |
| Volatility Shares Trust | 110 | 726 | isin=110, category=110, inception_date=110, ticker=107, manager=99, administrator=99, net_assets=91 |
| SUNAMERICA SERIES TRUST | 143 | 715 | ticker=143, isin=143, category=143, inception_date=143, administrator=143 |

The per-fund worklist is `reports/us_field_gaps.csv`. A value is never
inferred: the column names the official dataset that can supply it, and
funds whose publisher does not state a value stay null.
