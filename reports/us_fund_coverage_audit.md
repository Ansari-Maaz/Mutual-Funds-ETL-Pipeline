# FundFlow — Comprehensive US Mutual Fund Data Audit

**Audit Timestamp:** 2026-11-19T21:38:46.927788+00:00  
**Universe:** All US Domiciled Funds in PostgreSQL (`domicile_country = 'US'`)  
**Total US Funds:** **39,139**

---

## 1. Field-Level Completeness Report

| Field | Populated Records | Completeness (%) | Status / Note |
| :--- | ---: | ---: | :--- |
| Fund Name | 39,139 | 100.0% | Complete |
| Legal Name | 39,139 | 100.0% | Complete |
| Ticker / Symbol | 32,008 | 81.78% | Substantial |
| ISIN | 770 | 1.97% | High Gaps |
| SEC Series ID | 39,138 | 100.0% | Complete |
| SEC CIK | 39,138 | 100.0% | Complete |
| Category | 1,095 | 2.8% | High Gaps |
| Fund Type | 39,139 | 100.0% | Complete |
| Inception Date | 17,257 | 44.09% | High Gaps |
| Status | 39,139 | 100.0% | Complete |
| Provider / Registrant | 39,139 | 100.0% | Complete |
| Manager | 33,080 | 84.52% | Substantial |
| Administrator | 32,219 | 82.32% | Substantial |
| Net Assets | 34,130 | 87.2% | Substantial |
| Currency | 39,139 | 100.0% | Complete |
| Official URL | 39,139 | 100.0% | Complete |
| NAV Coverage | 25,675 | 65.6% | Substantial |
| Portfolio Holdings Coverage | 33,372 | 85.27% | Substantial |
| Both NAV and Holdings | 25,258 | 64.53% | Substantial |

---

## 2. Core Coverage Dimensions

| Dimension | Funds | Observations / Rows | Date Span | Sources |
| :--- | ---: | ---: | :--- | :--- |
| **NAV Observations** | 25,675 (65.6%) | 598,100 rows | 2012-05-15 to 2026-11-15 | us_nasdaq_mutual_fund_navs, us_yahoo_mutual_fund_navs, sec_nmfp_money_market, us_capital_group_fund_pages, us_vanguard_fund_products, us_ssga_spdr_navs, us_graniteshares_fund_pages, unattributed, us_nasdaq_etf_market_prices |
| **Portfolio Holdings** | 33,372 (85.3%) | 14,544,797 positions | 2024-12-31 to 2026-10-31 | sec_edgar_nport_bulk, sec_edgar_nport, sec_nmfp_bulk |
| **Both NAV & Holdings** | 25,258 (64.5%) | — | — | Full depth profile |
| **Holdings Only** | 8,114 (20.7%) | — | — | Missing daily NAV observations |
| **NAV Only** | 417 (1.1%) | — | — | Missing SEC N-PORT portfolio filings |
| **Missing Both** | 5,350 (13.7%) | — | — | Requires targeted research & filing recovery |

---

## 3. NAV Source Attribution Breakdown

| NAV Source | Covered Funds | Total Observations |
| :--- | ---: | ---: |
| `us_nasdaq_mutual_fund_navs` | 24,656 | 27,038 |
| `us_yahoo_mutual_fund_navs` | 24,407 | 115,797 |
| `sec_nmfp_money_market` | 986 | 21,341 |
| `us_capital_group_fund_pages` | 889 | 889 |
| `us_vanguard_fund_products` | 414 | 9,522 |
| `us_ssga_spdr_navs` | 143 | 403,703 |
| `us_graniteshares_fund_pages` | 34 | 19,790 |
| `unattributed` | 2 | 14 |
| `us_nasdaq_etf_market_prices` | 1 | 6 |

---

## 4. Portfolio Holdings by Data Source

| Data Source | Covered Funds | Position Rows |
| :--- | ---: | ---: |
| `sec_edgar_nport_bulk` | 31,359 | 11,438,944 |
| `sec_edgar_nport` | 4,387 | 2,939,824 |
| `sec_nmfp_bulk` | 1,093 | 166,029 |
