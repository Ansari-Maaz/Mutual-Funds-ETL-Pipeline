# FundFlow — Comprehensive US Mutual Fund Data Audit

**Audit Timestamp:** 2026-11-13T17:47:07.196744+00:00  
**Universe:** All US Domiciled Funds in PostgreSQL (`domicile_country = 'US'`)  
**Total US Funds:** **39,139**

---

## 1. Field-Level Completeness Report

| Field | Populated Records | Completeness (%) | Status / Note |
| :--- | ---: | ---: | :--- |
| Fund Name | 39,139 | 100.0% | Complete |
| Legal Name | 39,139 | 100.0% | Complete |
| Ticker / Symbol | 29,539 | 75.47% | Substantial |
| ISIN | 669 | 1.71% | High Gaps |
| SEC Series ID | 39,138 | 100.0% | Complete |
| SEC CIK | 39,138 | 100.0% | Complete |
| Category | 1 | 0.0% | High Gaps |
| Fund Type | 39,139 | 100.0% | Complete |
| Inception Date | 390 | 1.0% | High Gaps |
| Status | 39,139 | 100.0% | Complete |
| Provider / Registrant | 39,139 | 100.0% | Complete |
| Manager | 1 | 0.0% | High Gaps |
| Administrator | 0 | 0.0% | High Gaps |
| Net Assets | 30,740 | 78.54% | Substantial |
| Currency | 39,139 | 100.0% | Complete |
| Official URL | 39,139 | 100.0% | Complete |
| NAV Coverage | 25,263 | 64.55% | Substantial |
| Portfolio Holdings Coverage | 32,273 | 82.46% | Substantial |
| Both NAV and Holdings | 24,164 | 61.74% | Substantial |

---

## 2. Core Coverage Dimensions

| Dimension | Funds | Observations / Rows | Date Span | Sources |
| :--- | ---: | ---: | :--- | :--- |
| **NAV Observations** | 25,263 (64.5%) | 101,855 rows | 2025-11-10 to 2026-11-09 | us_nasdaq_mutual_fund_navs, us_yahoo_mutual_fund_navs, unattributed, us_nasdaq_etf_market_prices |
| **Portfolio Holdings** | 32,273 (82.5%) | 12,128,486 positions | 2024-12-31 to 2026-08-31 | sec_edgar_nport, sec_edgar_nport_bulk |
| **Both NAV & Holdings** | 24,164 (61.7%) | — | — | Full depth profile |
| **Holdings Only** | 8,109 (20.7%) | — | — | Missing daily NAV observations |
| **NAV Only** | 1,099 (2.8%) | — | — | Missing SEC N-PORT portfolio filings |
| **Missing Both** | 5,767 (14.7%) | — | — | Requires targeted research & filing recovery |

---

## 3. NAV Source Attribution Breakdown

| NAV Source | Covered Funds | Total Observations |
| :--- | ---: | ---: |
| `us_nasdaq_mutual_fund_navs` | 25,259 | 27,719 |
| `us_yahoo_mutual_fund_navs` | 24,753 | 74,108 |
| `unattributed` | 3 | 22 |
| `us_nasdaq_etf_market_prices` | 1 | 6 |

---

## 4. Portfolio Holdings by Data Source

| Data Source | Covered Funds | Position Rows |
| :--- | ---: | ---: |
| `sec_edgar_nport` | 18,724 | 5,916,818 |
| `sec_edgar_nport_bulk` | 13,549 | 6,211,668 |
