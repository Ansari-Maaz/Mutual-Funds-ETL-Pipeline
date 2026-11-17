# Official fund data sources: South Asia, Southeast Asia, Oceania, Middle East, Africa (as of 2026-11-17)

> SCOPE NOTE (user clarification, 2026-11-17): only the 20 Twelve Data reference countries plus LU/IE/AE/ZA matter. From this file only AUSTRALIA (section 5), SOUTH AFRICA (section 11) and UAE (section 12, thin) are in scope. India, Thailand, Pakistan, Malaysia, NZ, Israel, Saudi, Egypt, Nigeria, Indonesia etc. are out of scope: kept as optional later-expansion leads. SG, HK, JP, CN, KR, TW are covered by other researchers.

Method note: ~19 tool calls (searches + fetches). Items marked [VERIFIED] were seen in a fetched/search result this session; items marked [PRIOR] come from background knowledge and were NOT re-verified (treat as leads to HTTP-check). WebFetch to secopendata.sec.or.th returned 403 (likely bot block, not proof of key wall). Local repo state: connectors present = amf_geco, asisa, australian_managed_funds, bde_*, bmv_mexico, cvm, csrc, gsfm, hk_sfc_funds, japan_funds, korea_funds etc.; catalog.py registers for these regions only: AU (gsfm_unit_prices, au_user_managed_funds), AE (uae_local_funds, placeholder), ZA (asisa_cis_fund_list, asisa_cis_data), plus SG/HK/TW/KR/JP/CN (out of scope). EVERYTHING ELSE BELOW IS NEW. DB: ZA 1,945 funds (name/currency only), AU 97, AE 0, all others 0 (per 00_current_db_coverage.md).

## 5. Australia

### Takeaway
No official bulk NAV source. ASIC register is search-based; no MIS dataset on data.gov.au. Existing gsfm/au_user_managed_funds are tiny. Best incremental: ASX mFund (listed on ASX, ~ 100-200 funds) and ASX ETF files; APRA publishes super fund statistics (MySuper/ product heatmap, Excel) [PRIOR].

### Cited Findings
- ASIC datasets on data.gov.au are other registers (SMSF auditors, banned persons), CC-BY 3.0 AU, weekly snapshots; no MIS dataset found [VERIFIED] https://www.data.gov.au/data/dataset/asic-smsf ; ASIC MIS page https://www.asic.gov.au/regulatory-resources/managed-funds/managed-investment-schemes
- Treasury consultation (23 Sep 2026) proposing enhanced MIS data collection (future, not available) [VERIFIED] https://www.allens.com.au/insights-news/insights/2026/10/Treasury-proposes-enhanced-data-reporting-for-managed-investment-schemes/
- ASX mFund settlement list (ASX website, PDF/HTML), ASX ETF/ETP daily NAV files [PRIOR]. APRA: Quarterly superannuation performance statistics, MySuper product heatmaps (XLSX, free) [PRIOR]. Morningstar AU unofficial.
### Gaps
- Exact ASX URLs; ASIC register bulk (ASIC Connect is search-only; ASIC "company dataset" does not cover MIS).

## 11. South Africa

### Takeaway
ASISA: 1,945 local CIS portfolios end-June 2026 (matches DB count); 800 foreign-currency portfolios; detailed fund data (prices, TER, holdings) is commercial/proprietary (e.g. Profile Data, Morningstar, EconData) - no free official bulk NAV found. FSCA register URL not located.

### Cited Findings
- 1,945 local portfolios, R4.6tn Q2 2026 https://www.asisa.org.za/media-releases/local-cis-portfolios-attract-strong-net-inflows-in-second-quarter/
- FSCA requires scheme registration, annual and quarterly portfolio returns https://www.fscamymoney.co.za/Legislation%20Strategy%20and%20Policy/COLLECTIVE%20INVESTMENT%20SCHEMES%20CONTROL%20ACT%2045%20of%202002.pdf (statute). Profile's Unit Trusts (commercial ebook) https://www.fundsdata.co.za/ebook/2025-2U/files/basic-html/page79.html
- Manager websites publish daily prices; JSE lists ETFs/ETNs [PRIOR].
### Gaps
- FSCA public register URL; ASISA quarterly Excel fund-level stats licence.

## Overlap with Twelve Data mutual fund fields
Twelve Data fund fields (symbol, name, currency, exchange, country, type, ISIN/CUSIP, family, category, NAV, performance, risk, ratings, holdings, sector/country allocation, expense ratio, min investment) [PRIOR]. Official overlap: India (name, ISIN, family=AMC, category, NAV, plan), Thailand API (name, NAV, performance, fees, asset allocation, top-5 holdings), Saudi (name, manager, currency, NAV, expense ratio), NZ (fees, holdings, returns), Pakistan (NAV, returns, category). Ratings/risk scores generally NOT in official feeds (except SEBI riskometer in India documents, Thai risk level in factsheet [PRIOR]).
