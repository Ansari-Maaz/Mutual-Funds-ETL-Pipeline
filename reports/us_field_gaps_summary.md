# U.S. fund reference-field gap audit

Generated: 2026-11-19T20:18:47.585368+00:00

U.S. funds: 39,139 — reporting to the SEC in the observation window: 32,627; no filing in the window (dormant registration): 6,512.

## Completeness by field

| Field | Present | Missing | Complete | Official source | Action |
| --- | ---: | ---: | ---: | --- | --- |
| `ticker` | 32,008 | 7,131 | 81.78% | SEC company_tickers_mf.json, N-1A TradingSymbol/scn.tsv, N-CSR TradingSymbol | run enrich-us-funds --tickers and sync-sec-rr-profiles |
| `isin` | 770 | 38,369 | 1.97% | SEC N-PORT holding identifiers with CUSIP/ISIN check-digit validation | run enrich-us-funds --isins (only classes that appear as another fund's holding) |
| `category` | 1,095 | 38,044 | 2.8% | No official investment-style taxonomy; N-CEN flags are exposed as classification | leave null unless an issuer publishes a category; run enrich-us-fund-categories |
| `inception_date` | 16,838 | 22,301 | 43.02% | SEC N-1A prospectus XBRL PerfInceptionDate / N-CSR tailored shareholder report | run sync-sec-rr-profiles and sync-sec-ncsr-tsr |
| `manager` | 33,080 | 6,059 | 84.52% | SEC Form N-CEN ADVISER table (primary adviser) | run sync-sec-ncen-bulk |
| `administrator` | 32,219 | 6,920 | 82.32% | SEC Form N-CEN ADMIN table | run sync-sec-ncen-bulk |
| `net_assets` | 34,130 | 5,009 | 87.2% | SEC N-PORT quarterly bulk NET_ASSETS; N-CEN and N-CSR series net assets | run sync-sec-nport-bulk, sync-sec-ncen-bulk and sync-sec-ncsr-tsr |

## Completeness by field — reporting funds only

Dormant registrations cannot report new values, so this is the
population that a production completeness target applies to.

| Field | Present | Missing | Complete |
| --- | ---: | ---: | ---: |
| `ticker` | 28,659 | 3,968 | 87.84% |
| `isin` | 769 | 31,858 | 2.36% |
| `category` | 1,094 | 31,533 | 3.35% |
| `inception_date` | 16,661 | 15,966 | 51.07% |
| `manager` | 31,567 | 1,060 | 96.75% |
| `administrator` | 30,734 | 1,893 | 94.2% |
| `net_assets` | 32,588 | 39 | 99.88% |

## Records by number of missing fields

| Missing fields | Funds |
| ---: | ---: |
| 0 | 14 |
| 1 | 969 |
| 2 | 14,526 |
| 3 | 14,900 |
| 4 | 2,810 |
| 5 | 704 |
| 6 | 2,160 |
| 7 | 3,056 |

## Largest providers by missing fields

| Provider | Funds | Missing values | Fields |
| --- | ---: | ---: | --- |
| ETF Opportunities Trust | 569 | 3,557 | category=569, isin=568, inception_date=547, manager=501, administrator=501, net_assets=472, ticker=399 |
| GraniteShares ETF Trust | 527 | 3,199 | isin=527, category=527, inception_date=445, manager=444, administrator=444, net_assets=441, ticker=371 |
| Themes ETF Trust | 484 | 2,997 | category=484, isin=483, inception_date=466, manager=431, administrator=431, ticker=359, net_assets=343 |
| Tidal Trust II | 548 | 2,943 | category=548, isin=541, inception_date=455, manager=415, administrator=415, net_assets=362, ticker=207 |
| Corgi ETF Trust I | 328 | 2,157 | isin=328, category=328, inception_date=328, manager=327, administrator=327, ticker=326, net_assets=193 |
| Direxion Shares ETF Trust | 364 | 1,932 | category=364, isin=359, inception_date=315, manager=241, administrator=241, net_assets=216, ticker=196 |
| Investment Managers Series Trust II | 332 | 1,709 | category=332, isin=331, inception_date=263, manager=251, administrator=251, net_assets=208, ticker=73 |
| John Hancock Funds II | 387 | 1,388 | isin=387, category=387, inception_date=364, manager=66, administrator=66, net_assets=66, ticker=52 |
| PIMCO FUNDS | 378 | 1,170 | isin=374, category=372, inception_date=366, ticker=43, manager=5, administrator=5, net_assets=5 |
| PROSHARES TRUST | 264 | 1,157 | category=263, isin=251, inception_date=205, manager=113, administrator=113, net_assets=113, ticker=99 |
| GOLDMAN SACHS TRUST | 576 | 1,119 | isin=572, category=497, inception_date=50 |
| NATIONWIDE MUTUAL FUNDS | 299 | 1,087 | isin=299, category=296, inception_date=263, manager=61, administrator=61, net_assets=61, ticker=46 |
| LINCOLN VARIABLE INSURANCE PRODUCTS TRUST | 258 | 1,062 | ticker=258, isin=258, category=256, inception_date=214, manager=28, administrator=28, net_assets=20 |
| NATIONWIDE VARIABLE INSURANCE TRUST | 235 | 1,030 | ticker=235, isin=235, category=229, inception_date=193, manager=46, administrator=46, net_assets=46 |
| FIDELITY ABERDEEN STREET TRUST | 449 | 971 | isin=449, category=449, inception_date=73 |
| JNL SERIES TRUST | 260 | 945 | ticker=260, isin=260, category=258, inception_date=157, manager=4, administrator=4, net_assets=2 |
| ETF Series Solutions | 176 | 881 | category=176, isin=165, inception_date=130, manager=111, administrator=111, net_assets=101, ticker=87 |
| TIAA-CREF FUNDS | 336 | 878 | isin=335, category=330, inception_date=213 |
| PRINCIPAL FUNDS, INC. | 303 | 859 | isin=303, category=299, inception_date=250, manager=3, administrator=3, ticker=1 |
| MASSMUTUAL SELECT FUNDS | 282 | 857 | isin=282, category=282, inception_date=221, manager=24, administrator=24, net_assets=24 |
| HARTFORD MUTUAL FUNDS, INC | 297 | 820 | isin=297, category=297, inception_date=226 |
| RBB FUND, INC. | 183 | 790 | category=183, isin=167, inception_date=137, manager=88, administrator=88, net_assets=72, ticker=55 |
| EQ ADVISORS TRUST | 206 | 786 | ticker=206, isin=206, category=203, inception_date=171 |
| iSHARES TRUST | 390 | 767 | category=390, isin=270, inception_date=54, manager=24, administrator=24, net_assets=5 |
| JANUS INVESTMENT FUND | 256 | 766 | isin=256, category=250, inception_date=235, manager=8, administrator=8, net_assets=8, ticker=1 |
| JPMorgan Trust I | 365 | 754 | isin=359, category=326, inception_date=65, ticker=4 |
| Volatility Shares Trust | 110 | 705 | isin=110, category=110, inception_date=107, manager=99, administrator=99, net_assets=91, ticker=89 |
| SUNAMERICA SERIES TRUST | 143 | 661 | ticker=143, isin=143, category=143, administrator=143, inception_date=89 |
| Milliman Variable Insurance Trust | 95 | 657 | ticker=95, isin=95, category=95, inception_date=93, manager=93, administrator=93, net_assets=93 |
| EA Series Trust | 165 | 640 | category=165, isin=159, inception_date=106, manager=77, administrator=77, net_assets=52, ticker=4 |

The per-fund worklist is `reports/us_field_gaps.csv`. A value is never
inferred: the column names the official dataset that can supply it, and
funds whose publisher does not state a value stay null.
