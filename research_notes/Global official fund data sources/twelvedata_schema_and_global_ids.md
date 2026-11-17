# Twelve Data mutual-fund schema vs official sources, and global identifier sources (as of 2026-11-17)

Method note: Twelve Data facts come only from twelvedata.com public docs pages (no API calls, no key). Project facts come from the repo files named below. Classification (official / derivable / proprietary) and the proposed columns are my analysis, so they sit under Inferences.

## Q1. What exact data model does Twelve Data expose for mutual funds, and what gates each part?

### Takeaway
Twelve Data has 11 mutual-fund routes: a cheap directory (1 credit) and families/types lists, plus 8 "world" routes (1000 credits full, 200 credits per section) restricted to Ultra/Enterprise and above. The docs do not document `/etf/world`, `/funds` or NAV history via `/time_series` on the mutual-funds pages I could fetch.

### Cited Findings
Plans and credits ([MF directory page](https://twelvedata.com/docs/mutual-funds/mutual-funds-list), [MF full data page](https://twelvedata.com/docs/mutual-funds/mf-all-data), [MF overview](https://twelvedata.com/docs/mutual-funds)):
- Individual plans are Basic, Grow, Pro, Ultra; business plans are Venture, Enterprise, Custom.
- `/mutual_funds/list`: 1 credit. Basic/Grow/Pro/Venture return up to 50 records; Ultra/Enterprise/Custom return the full set (over 140,000 funds).
- `/mutual_funds/world` (full): 1000 credits, Ultra and above. `/world/summary|performance|risk|ratings|composition|purchase_info|sustainability`: 200 credits each, Ultra and above.
- `/mutual_funds/family` and `/mutual_funds/type`: 1 credit each, plan not stated.
- `figi` request filter requires Ultra/Enterprise and above; ISIN and CUSIP values in responses require the ISIN and CUSIP Data add-ons.
- Identifier params: `symbol`, `figi`, `isin`, `cusip` (one required on world routes); optional `country`, `dp` (0-11, default 5). Directory also takes `cik`, `fund_family`, `fund_type`, `performance_rating` (0-5), `risk_rating` (0-5), `format` (JSON/CSV), `delimiter`, `page`, `outputsize` (default 100).
- The overview page does not document an `/etf/world` route; the ETF section lists directory, full data, summary, performance, risk, composition, families, types. It shows NAV only as current values (`nav`, `12_month_low/high`, `last_month`) in summary/purchase_info, not as time-series history. ([MF overview](https://twelvedata.com/docs/mutual-funds))
- The docs fetched for `/funds` (reference-data/funds-list) returned HTTP 404, so `/funds`, `/quote`, `/profile`, `/time_series` fund behavior is undocumented in these notes beyond the section labels: Time series and Quote are "High demand" under Market data, Profile is "Useful" under Fundamentals. ([Docs index](https://twelvedata.com/docs))
- The project's own 2026-11-13 comparison shows `/time_series` for a mutual fund returns `instrument_type: "Mutual Fund"`, `exchange`, `mic_code`, `currency`, `exchange_timezone`, `interval` and OHLC where open=high=low=close (a single daily NAV) — [repo report](reports/twelvedata_us_fund_comparison_2026-11-13.md). That report also records that ISIN/CUSIP returned `request_access_via_add_ons`.

Field schema (all from [MF full data page](https://twelvedata.com/docs/mutual-funds/mf-all-data) and [directory page](https://twelvedata.com/docs/mutual-funds/mutual-funds-list)); `symbol` example `0P0001LCQ3` (docs do not say what the id scheme is):

`/mutual_funds/list` -> `result.count` (int, 1000); `result.list[]`: `symbol` (str), `name` (str, "JNL Small Cap Index Fund (I)"), `country` (str, "United States"), `fund_family` (str, "Jackson National"), `fund_type` (str, "Small Blend"), `performance_rating` (int 0-5), `risk_rating` (int 0-5), `currency` ("USD"), `exchange` ("OTC"), `mic_code` ("OTCM"); top-level `status`.

`summary`: `symbol`, `name`, `fund_family`, `fund_type`, `currency` (str); `share_class_inception_date` (date, 2021-04-26); `ytd_return` (double, -0.02986); `expense_ratio_net` (double, 0.001); `yield` (double, 0); `nav` (double, 10.09); `min_investment` (int, 0); `turnover_rate` (double, 0.32); `net_assets` (int, 2400762112); `overview` (str, prospectus-style text); `people[]`: `name`, `tenure_since` (date).

`performance`: `trailing_returns[]` {`period` (e.g. "ytd"), `share_class_return`, `category_return`, `rank_in_category` (int)}; `annual_total_returns[]` {`year`, `share_class_return`, `category_return`}; `quarterly_total_returns[]` {`year`, `q1..q4`}; `load_adjusted_return[]` {`period` ("1_year"), `return`}.

`risk`: `volatility_measures[]` per `period` ("3_year"): `alpha`, `beta`, `mean_annual_return`, `r_squared`, `std`, `sharpe_ratio`, `treynor_ratio`, each with a `_category` twin (all double). `valuation_metrics`: `price_to_earnings`, `price_to_book`, `price_to_sales`, `price_to_cashflow`, `median_market_capitalization` (int), `3_year_earnings_growth`, each with `_category` twin (the growth twin is spelled `3_year_earnings_growths_category`).

`ratings`: `performance_rating`, `risk_rating`, `return_rating` (int 0-5).

`composition`: `major_market_sectors[]` {`sector`, `weight`}; `asset_allocation` {`cash`, `stocks`, `preferred_stocks`, `convertables`, `bonds`, `others`}; `top_holdings[]` {`symbol`, `name`, `exchange`, `mic_code`, `weight`}; `bond_breakdown` {`average_maturity` {`fund`,`category`}, `average_duration` {`fund`,`category`}, `credit_quality[]` {`grade` (AAA..below B, "U.S. Government"), `weight`}}.

`purchase_info`: `expenses` {`expense_ratio_gross`, `expense_ratio_net`}; `minimums` {`initial_investment`, `additional_investment`, `initial_ira_investment`, `additional_ira_investment` (ints)}; `pricing` {`nav`, `12_month_low`, `12_month_high`, `last_month`}; `brokerages` (array of string).

`sustainability`: `score` (int 0-100); `corporate_esg_pillars` {`environmental`, `social`, `governance`}; `sustainable_investment` (bool); `corporate_aum` (double).

`/family`, `/type`: `result` map country -> array of strings (e.g. India -> "Aditya Birla Sun Life AMC Ltd"; Singapore -> "Singapore Equity", "SGD Bond").

Doc inconsistencies noted by the page review: scale mixing in `/risk` samples (alpha -9.12 vs category -0.0939; r_squared 69 vs 0.8309), several empty sample blocks, `/type` example copy error, `/world/summary` description mentions asset class/region that the schema lacks. ([MF full data page](https://twelvedata.com/docs/mutual-funds/mf-all-data))

Already covered in the repo (not repeated here): endpoint inventory vs FundFlow routes, Twelve Data terms (no redistribution / no competing product), US source cadence, and the finding that a `basic` key gets 403 on all world sections — [docs/TWELVE_DATA_MUTUAL_FUNDS_GAP_ASSESSMENT.md](docs/TWELVE_DATA_MUTUAL_FUNDS_GAP_ASSESSMENT.md).

### Inferences
- Tier gating summary: everything useful beyond a 50-row sample, plus every "world" section, needs Ultra+; identifiers (ISIN/CUSIP/FIGI) are separately paywalled. So ISIN/CUSIP are exactly the fields FundFlow can add value on from official sources.
- `ytd_return` is a decimal fraction (-0.02986 = -2.99%); percentages in `risk` appear on mixed scales, so a FundFlow-compatible layer should pick one scale and document it.

### Gaps
- `/funds`, `/etf/world`, `/quote`, `/profile`, `/time_series` fund-specific field lists could not be fetched (404 / not on the mutual-funds page). Unverified whether `/etf/world` exists; the overview page lists ETF sections but not that path.
- Plan prices and exact tier credit allowances were not retrieved.

## Q2. Which Twelve Data fields can be reproduced from official data, and which cannot?

### Takeaway
Roughly: identity, NAV, fees, minimums, net assets, objectives, managers and holdings are directly official where a regulator/issuer publishes them; returns, volatility, Sharpe, drawdown, asset allocation, sector/country weights, top holdings and turnover are derivable; ratings, category ranks/peer metrics, Morningstar-style types and ESG scores are proprietary.

### Cited Findings
- Official-source anchors already verified in the repo: SEC series/class report (identity, optional ticker), N-PORT quarterly bulk (holdings, series-level, delayed), N-MFP monthly (money-market holdings and daily class NAV), N-CEN (service providers), prospectus filings (fees, objectives); N-PORT is not a daily NAV source — [repo gap doc](docs/TWELVE_DATA_MUTUAL_FUNDS_GAP_ASSESSMENT.md).
- The repo doc states raw filings give no comparable 0-5 fund ratings, and no single public official ESG dataset covers US fund-level ESG scores — [repo gap doc](docs/TWELVE_DATA_MUTUAL_FUNDS_GAP_ASSESSMENT.md).
- EU standard data templates exist for distributors: EMT (MiFID template, latest in results V4.2, April 2024) and EPT (PRIIPs template, V2.0 Feb 2022, V2.1 Sept 2022) — [EFAMA/FinDatEx via search results: Kneip EPT 2.1](https://www.kneip.com/?p=17120), [EFAMA EPT v2](https://www.efama.org/newsroom/news/findatex-publishes-ept-v2). A Clearstream piece (Jan 2026) says FinDatEx regularly publishes new EMT/EPT versions, so newer versions may exist — [Clearstream](https://www.clearstream.com/clearstream-en/newsroom/260116-5077768).

### Inferences
Classification table (D = directly official, C = computable from official NAV/holdings, P = proprietary). "US/EU/other" gives the best official route; availability is per-source, not universal.

| Twelve Data field | Class | Best official route / note |
|---|---|---|
| symbol (vendor id e.g. 0P...) | P | Vendor id; replace with ISIN/ticker/regulator id |
| name, country, currency | D | Registers, SEC series/class, KID |
| fund_family | D | Manager/sponsor (SEC N-CEN/adviser; EMT manufacturer name; AMFI AMC; CVM administrador) |
| fund_type (Morningstar-like "Small Blend") | P | Official equivalents are coarse: SEC N-CEN flags, CFI code, CVM classe, AMFI scheme category, UCITS/AIF. Store source category; don't relabel |
| exchange / mic_code | D (where listed) | ISO 10383 from exchange lists / ESMA FIRDS; most mutual funds have none |
| performance_rating, risk_rating, return_rating | P | EU SRI/SRRI (1-7) in KID is official risk class, but a different scale; keep as separate field |
| share_class_inception_date | D | SEC class/series, KID, registers |
| nav, 12m low/high, last_month | D (nav) / C (range) | Issuer/regulator NAV; range from stored history |
| ytd_return, trailing_returns (share class) | C | From NAV + distributions (total return) or NAV only (price return); label method. Issuer/KID past performance is D |
| annual_total_returns, quarterly_total_returns | C (or D from KID past performance / N-1A bar chart) | calendar-year/quarter from NAV+dists |
| load_adjusted_return | C | Needs official load schedule (prospectus) |
| category_return, rank_in_category, all `*_category` | P | Needs peer set from proprietary taxonomy; could be computed vs FundFlow-defined peer groups, labeled as such |
| alpha, beta, r_squared, std, mean_annual_return, sharpe, treynor | C | Need NAV series + benchmark index series + risk-free rate; benchmark index data may be licensed |
| max drawdown (not in TD) | C | NAV |
| valuation_metrics (P/E, P/B, median mkt cap, earnings growth) | C but needs fundamentals of holdings (commercial) | Not realistically official |
| expense_ratio_net/gross | D | Prospectus fee table / KID ongoing charges / N-CSR financial highlights |
| min_investment, initial/additional/IRA mins | D | Prospectus/KIID/issuer; IRA is US-specific |
| yield | C/D | SEC yield from N-1A/497K standardized or distributions/NAV |
| turnover_rate | D | N-1A/prospectus, N-CSR financial highlights; or C from N-PORT (low quality) |
| net_assets | D | N-PORT, N-MFP, registers, AMFI AUM |
| overview | D | Prospectus objective text |
| people (managers, tenure) | D | Prospectus/497K/issuer, some KIID |
| brokerages | P | Distribution-platform data |
| top_holdings (symbol, name, weight) | C from D holdings | N-PORT/EU SFDR/national holdings disclosures; needs ISIN->ticker mapping (OpenFIGI) |
| asset_allocation | C | From holdings with asset category (N-PORT asset cat) |
| major_market_sectors | C (needs sector classification; GICS/ICB are licensed) | Use CFI/NACE/issuer SIC from registers as free approximations |
| bond_breakdown (maturity, duration, credit quality) | C partial | N-PORT gives maturity, coupon, some ratings/duration fields; credit grade often absent |
| sustainability score/pillars | P | Official: SFDR Art 6/8/9 and EET fields (EU) are D-ish; no numeric score |
| sustainable_investment (bool) | D (EU SFDR article / EET) | Not US |
| corporate_aum | P | Morningstar-style |

### Gaps
- Not verified: exact EMT/EPT field lists (they are FinDatEx files shared B2B; I did not fetch field specs). Not verified which jurisdictions publish KID/past-performance in bulk.

## Q3. What minimal new DB structure lets FundFlow serve Twelve-Data-like responses?

### Takeaway
Existing schema already has funds (ISIN, ticker, manager, category, net_assets, SEC ids), nav_observations, portfolio_holdings (isin/cusip/ticker/weight), a generic JSONB `fund_profile_snapshots` keyed by dataset, and `holding_metrics`. Missing are first-class share-class/identifier tables, typed fees, distributions, benchmark, risk indicator and a calculated-metrics cache.

### Cited Findings
- `/media/asim/4_TB_1/MFAPI/MF ETL PIPELINE/app/models/schema.py` defines: `Source`, `Fund` (isin, legal_name, provider, category, fund_type, inception_date, status, ticker, manager, administrator, net_assets/_date, sec_series_id, sec_cik, holdings_status, holdings_report_date; no lei, figi, cusip, share-class or parent link), `FundProfileSnapshot` (fund_id, source_id, dataset, source_report_date, snapshot_key, JSONB payload), `PortfolioHolding` (isin, cusip, ticker, market_value, weight, report date; no FIGI, LEI, asset category, sector, country), `HoldingMetric`, `NavObservation` (nav, open/high/low/close, ohlc_basis, currency), `EtlRun`.
- Repo gap doc says compatibility routes already read performance/risk/ratings/composition/fees/yields from `fund_profile_snapshots` where present, and FIGI is not stored — [repo gap doc](docs/TWELVE_DATA_MUTUAL_FUNDS_GAP_ASSESSMENT.md).

### Inferences
Proposed minimal additions (keep JSONB snapshots for long-tail, add typed tables only for fields that are queried/filtered or computed):
1. `fund_identifiers` (fund_id, scheme [ISIN|LEI|CUSIP|FIGI|SHARE_CLASS_FIGI|CIK|SEC_CLASS_ID|SEDOL|WKN|VALOR|TICKER|MIC_TICKER|NATIONAL_ID], value, mic nullable, source_id, valid_from/to, retrieved_at; unique on scheme+value+mic). Replaces more columns on `funds`; keep `funds.isin/ticker` as primary denormalized convenience. LEI belongs here (fund-level LEI) not on holdings only.
2. `fund_share_classes` (class_id, fund_id parent umbrella/series, class_name, currency, distribution_policy [acc/inc], hedged flag, inception_date, min_initial/min_additional/min_ira, status). Twelve Data is share-class-level (`share_class_inception_date`); FundFlow `funds` mixes class and series (SEC series vs class).
3. `fund_fees` (class_id, as_of, ongoing_charge/expense_ratio_gross/net, mgmt_fee, entry/exit load, performance_fee, transaction_costs, source/doc type). Typed because filterable.
4. `fund_distributions` (class_id, ex_date, pay_date, amount, currency, type) — required to compute total return and yield.
5. `fund_benchmarks` (fund_id, benchmark_name, index_id/ISIN, source) and a `benchmark_series` (or reuse nav_observations for index) — required for alpha/beta/R2.
6. `fund_risk_indicator` (class_id, as_of, scheme [SRI|SRRI|national], value, source) — EU KID SRI 1-7 and equivalents; do not mix with a 0-5 rating.
7. `fund_metrics_cache` (class_id, as_of, method_version, window, metric, value, currency) — trailing/annual/quarterly returns, std, Sharpe, max drawdown, beta/alpha; label `basis` (price vs total return) and `inputs_complete` flag.
8. `fund_allocation` (fund_id, report_date, dimension [asset_class|sector|country|currency|credit_quality], bucket, weight, method [reported|computed], source) — materialized from holdings or issuer-reported.
9. Extend `portfolio_holdings` with figi, lei (issuer LEI), asset_category, issuer_country, maturity_date, and add `security_master` (identifier -> canonical security) so ISIN/CUSIP/FIGI/ticker/MIC resolve once.
10. `fund_people` (fund_id, name, role, tenure_since) and `fund_documents` (class_id, type [prospectus|KID|KIID|annual], url, date, language) for `overview`/KID links.
11. Provenance columns (`source_id`, `source_url`, `as_of`, `retrieved_at`, `license_status`) on every new table — mirrors the existing pattern.
Fields deliberately NOT given columns: vendor ratings, category ranks, ESG scores, brokerages, valuation metrics (proprietary or commercial inputs) — return `unavailable`.

### Gaps
- Not checked: whether existing Alembic migrations or `app/catalog.py` already hold some of these elsewhere; only schema.py was read as asked.

## Q4. What is the minimal "FundFlow canonical" field set (similar, not same, as Twelve Data)?

### Takeaway
Use Twelve Data's section names and shapes as an interface, but define values as source-attributed with a `basis`/`method` tag, and drop proprietary sections.

### Cited Findings
- Repo constraints: Twelve Data terms restrict redistribution and competing use, so FundFlow must not ingest their values; keep source-reported and FundFlow-calculated metrics distinct — [repo gap doc](docs/TWELVE_DATA_MUTUAL_FUNDS_GAP_ASSESSMENT.md).

### Inferences
Canonical set (all fields carry `source`, `as_of`, `basis`):
- identity: fund_id, share_class_id, name, legal_name, domicile, currency, ISIN, ticker+MIC, LEI, FIGI/shareClassFIGI, CUSIP/CIK/series (US), national id, manager/family, administrator, fund_type (source-reported) + CFI + normalized `asset_class` (FundFlow taxonomy: equity/bond/mixed/MM/alt/other), distribution policy, inception, status.
- price: nav, nav_date, currency, ohlc only where an exchange-traded close exists (ETFs).
- cost: ongoing_charge/expense gross+net, loads, minimums.
- size: net_assets, as_of.
- returns (computed + issuer-reported flagged): 1m/3m/6m/YTD/1y/3y/5y/10y/since inception, calendar-year; distributions.
- risk (computed): std, Sharpe, max drawdown, beta/alpha vs declared benchmark; plus official risk indicator (SRI/SRRI) as its own field.
- composition: top-N holdings (with ISIN), asset/sector/country weights, computed with `method=computed` and coverage %, bond maturity/duration where filed.
- documents: prospectus, KID links.
Dropped / unavailable: performance/risk/return ratings, category rank and `*_category` metrics, brokerages, ESG score/pillars, valuation metrics.

### Gaps
- None beyond Q2/Q3 gaps.

## Q5. GLEIF LEI-ISIN mapping: how it works and how to use it for funds

### Takeaway
GLEIF publishes free daily ISIN-LEI relationship zip files (data under CC0), but coverage is limited to new ISINs from early-mover national numbering agencies, so it fills only part of the fund-ISIN-to-LEI gap.

### Cited Findings
- Daily files, zip named `isin-lei-YYYYMMDDThhmmss.zip`, latest listed 2026-11-17; CSV import guide v1.1 linked; built on an ANNA mapping process certified by GLEIF. Currently includes only new ISINs from "early mover" NNAs; legacy ISINs not covered yet but planned; 116 NNAs issue ISINs in total. The page does not mention funds. — [GLEIF ISIN-LEI files](https://www.gleif.org/en/lei-data/lei-mapping/download-isin-to-lei-relationship-files)
- GLEIF LEI Data Terms of Use: Access Service is free and the data are provided under the CC0 licence; GLEIF logo/trademark is protected — [GLEIF terms of use](https://www.gleif.org/en/meta/lei-data-terms-of-use) (via search summary; the dedicated ISIN-LEI terms URL I tried returned 404), [GLEIF open data](https://gleif.org/en/about/open-data).
- A Finextra explainer notes LEIs cannot carry licence fees for use/redistribution whereas ISINs are not necessarily free — [Finextra](https://finextra.com/blogposting/11977/mifir-how-isins-work-4).

### Inferences
- Use: join fund ISIN -> LEI of the issuer (for UCITS/AIF, the legal entity can be the umbrella/SICAV sub-fund or management company; GLEIF Level 1 data also has "fund" entities with fund-family relationship records, not verified here) and join holdings ISIN -> issuer LEI to enrich N-PORT/EU holdings. Download the full Level-1 LEI golden copy (CC0) separately to name-match funds that lack ISIN-LEI rows.
- Because of the early-mover limitation, do not assume absence = no LEI.

### Gaps
- Which NNAs are early movers and whether ISIN-LEI covers fund-type ISINs: not stated on the page. GLEIF Level 1/2 file format and fund-entity category (`FUND`) not verified.

## Q6. ANNA / national numbering agencies, ISIN access, and licensing

### Takeaway
ISIN assignment is decentralised across NNAs; a free ANNA ISIN lookup exists but with limited fields and download caps, and redistribution rights are NNA-/ASB-specific and unclear. CUSIP has commercial licensing.

### Cited Findings
- ANNA's free ISIN Lookup Service offers basic ISIN information, requires registration, allows only a limited number of record downloads; paid subscriptions give licensed exports, daily feeds, APIs — [ANNA FAQ](https://anna-web.org/faq-page/), [Waters: ANNA ISIN lookup](https://waterstechnology.com/reference-data-data-management/3463696/anna-unveils-isin-lookup-service), [ANNA ASB](https://anna-web.org/about-the-anna-service-bureau/).
- The DSB (ANNA DSB) states OTC-derivative ISINs and their data have no licensing restrictions on use and distribution; this covers OTC derivatives, not funds — [ANNA DSB](https://www.anna-dsb.com/ISIN).
- Trade press reports ANNA objected to S&P's practice of seeking licence fees for CUSIP-based ISIN databasing; outcome not found — [Waters](https://www.waterstechnology.com/inside-market-data/feature/1619129/anna-suffers-setback-against-s-p).
- Finextra: ISINs are not necessarily free; licence fees may govern use/redistribution — [Finextra](https://finextra.com/blogposting/11977/mifir-how-isins-work-4).

### Inferences
- Practical free routes for fund ISINs are regulator/exchange/issuer publications (KID, register, FIRDS, exchange lists) rather than bulk NNA feeds. Treat WM Datenservice, SIX, CUSIP Global Services as paid unless a specific free list is verified.

### Gaps
- Not verified: WM Datenservice, SIX Financial, CUSIP Global Services (CGS) licence terms; I found nothing on CGS fees in this pass. Redistribution terms of ASB free lookup not found (suggested contact: ASB support).

## Q7. ESMA FIRDS/FITRS reference data for EU-traded funds and ETFs

### Takeaway
FIRDS is public and bulk (full files weekly, delta files daily) and carries ISIN, MIC and CFI for MiFID-traded instruments, so it covers ETFs and listed funds on EU venues but not unlisted mutual funds.

### Cited Findings
- ESMA publishes FIRDS reference data: full files weekly, delta files daily; full files are split by first letter of the CFI code and when they exceed 500,000 records; each record carries ISIN, MIC and CFI among other fields — [ESMA FIRDS download instructions (ESMA65-8-5240)](https://www.esma.europa.eu/sites/default/files/2023-12/ESMA65-8-5240_FIRDS_Transparency_Download_Instructions.pdf), [FI.se notice](https://fi.se/en/published/news/2017/esma-publishes-reference-data-and-instructions-for-downloading-files/).
- The FCA operates its own FIRDS for UK, sourcing EEA data from ESMA — [FCA instrument reference data](https://FCA.org.uk/markets/transaction-reporting/instrument-reference-data).
- OpenSanctions lists FIRDS as an ESMA dataset; its note says free for non-commercial users while businesses need its own licence (this describes OpenSanctions' repackaging, not ESMA's terms) — [OpenSanctions](https://www.opensanctions.org/datasets/eu_esma_firds).

### Inferences
- Filter CFI category "C" (collective investment vehicles; CFI ISO 10962) to get funds/ETFs; FITRS is the transparency-results side (liquidity/volume results), not an ID source. ESMA's reuse terms not retrieved: assume EU institutional reuse policy but confirm.

### Gaps
- ESMA FIRDS landing page URL attempted returned 404; ESMA's own reuse licence and the CFI "C" filter were not confirmed. FITRS not researched beyond scope note.

## Q8. Exchange-official ticker/ISIN lists (LSE, Xetra, Euronext, SIX, SGX, HKEX, JPX, KRX, TWSE, NSE/BSE, ASX, TSX, B3, BMV)

### Takeaway
Only Xetra (instrument list/new ETF page), Euronext (free live-markets ETF directory) and Cboe Europe were evidenced; Euronext's machine-readable ETF Master File is a paid subscription. The remaining exchanges were not verified in this pass.

### Cited Findings
- Deutsche Börse "All tradable instruments" lists ETFs/ETNs with ISIN and Xetra symbol (about 3,949 results on one page); a "new ETFs/ETPs" page lists recent launches with ISIN, Xetra symbol, currency — [Deutsche Börse instruments](https://deutsche-boerse-cash-market.com/dbcm-en/instruments-statistics/all-tradable-instruments/xetra/3972!search?query=etp), [New ETFs](https://www.eurexchange.com/cash-en/trading/etfs-etps/new-etfs-etps).
- Euronext: ETF Master File is a detailed reference-data product available by subscription; reference data files are XML zip via FTP daily; a free ETF directory exists on Euronext Live — [Euronext reference data](https://euronext.com/nb/data/reference-data), [Euronext ETF Masterfile spec](https://connect.euronext.com/sites/default/files/documentation/clearing/euronext-and-borsa-italiana-etf-masterfile-client-specification-v19512052026.pdf), [Euronext ETF](https://www.euronext.com/etf).
- Cboe Europe publishes a listed-securities page including ETF/ETPs with ISINs — [Cboe Europe](https://cboe.com/europe/equities/listings/symbols/). SIX has an ETP market-data page — [SIX ETPs](https://www.six-group.com/en/market-data/etp.html); no downloadable list confirmed.

### Inferences
- Exchange lists are good for ETF ticker+MIC+ISIN; typically restrict commercial redistribution of full master files (Euronext explicitly sells it). Use FIRDS for EU breadth and per-exchange lists for non-EU.

### Gaps
- LSE, SGX, HKEX, JPX, KRX, TWSE, NSE/BSE, ASX, TSX, B3, BMV: no verified source found; searches returned nothing relevant. Redistribution terms of every exchange list not verified.

## Q9. OpenFIGI: ticker/FIGI mapping and terms

### Takeaway
OpenFIGI offers a free mapping API (25 req/min unkeyed, 250/min keyed) that maps ISIN/ticker/etc. to FIGI, shareClassFIGI and ticker; FIGI itself is presented as open with no licensing fees, but mapping from third-party IDs may carry their own licence considerations.

### Cited Findings
- Limits: mapping 25 req/min and 10 jobs/request without key; 250 req/min and 100 jobs/request with key; search/filter 5 vs 20 req/min; results cap 15,000; 429 with `retry-after`; limits per key or per IP — [OpenFIGI API docs](https://www.openfigi.com/api/documentation).
- Mapping request: `idType`, `idValue` required; `exchCode` or `micCode` (not both); `securityType2` required for BASE_TICKER/ID_EXCH_SYMBOL; optional currency, marketSecDes, etc. Response per instrument: figi, securityType, marketSector, exchCode, securityType2, ticker, name, shareClassFIGI, compositeFIGI, securityDescription — [OpenFIGI API docs](https://www.openfigi.com/api/documentation).
- Terms (last updated Nov 27, 2018) reportedly grant a non-exclusive right to use, reproduce, distribute and create derivative works from FIGI identifiers; OpenFIGI states no cost recovery, licensing or re-use restrictions on FIGI symbology — [OpenFIGI terms](https://openfigi.com/docs/terms-of-service), [OpenFIGI benefits](https://openfigi.com/about/benefits). I could not confirm CC0 specifically (search found no CC0 statement); the OMG standard MIT-licence claim is secondhand.
- Third-party identifier mapping may need a separate licence from that provider — search-summary advice, original source not identified.

### Inferences
- Good fit for ISIN->ticker/FIGI for holdings and ETFs; rate limits imply batching 100 per request with a key ≈ 25,000 IDs/min; mutual-fund (non-listed) coverage is likely thinner (unverified).

### Gaps
- Full terms text not read (truncated); no verification of mutual-fund FIGI coverage.

## Q10. EU PRIIPs KID, EMT/EPT: who publishes in bulk

### Takeaway
EMT/EPT are FinDatEx industry-standard Excel/XML templates exchanged B2B between manufacturers and distributors, not public bulk downloads. Public KIDs are published per product on manager sites and some fund-platform/national sites; no verified free bulk regulator feed.

### Cited Findings
- EPT V2.0 (Feb 2022, EEA products from Jan 2023) and V2.1 (Sept 2022, adds UK regime) coexist; EMT latest seen V4.2 (April 2024) — [Kneip EPT 2.1](https://www.kneip.com/?p=17120), [EFAMA EPT v2](https://www.efama.org/newsroom/news/findatex-publishes-ept-v2), [BVI EPT](https://bvi.de/en/services/samples-and-working-aids/european-priips-template-ept-comfort-european-priips-template-cept), [BVI EMT](https://bvi.de/en/services/samples-and-working-aids/european-mifid-template-emt).
- Commercial feeds redistribute EMT/EPT (e.g. fefundinfo) — [FE fundinfo EPT FAQ](https://www.fefundinfo.com/insights/the-evolution-of-ept-faq), [ICE EET](https://www.ice.com/publicdocs/ICE_European_ESG_Template_EET_solution.pdf).

### Inferences
- Treat KID/EMT/EPT as manufacturer-published data: fetch per-issuer KID PDFs (ongoing charges, SRI, RHP, performance scenarios, past performance) rather than expecting a bulk register. FinDatEx data sharing is membership/platform-based (not verified as open).

### Gaps
- FinDatEx platform access terms and whether any national regulator hosts bulk KIDs not verified; current EMT/EPT versions in Nov 2026 not confirmed.

## Q11. Aggregated multi-country NAV/fund sources (ECB, OECD, IOSCO, EFAMA, exchange platforms, FundsLibrary)

### Takeaway
Official multi-country sources are aggregates only (ECB euro-area investment fund statistics); no verified official multi-country per-fund NAV source.

### Cited Findings
- ECB investment fund statistics (IVF): euro-area funds' assets/liabilities, outstanding amounts and transactions, money market funds and pension funds excluded, ETF data available; funds report to national central banks which send aggregates to the ECB; monthly with some quarterly breakdowns; data from Dec 2008; published ~7 weeks after reference period; series catalogue CSV and SDMX download on the ECB Data Portal — [ECB IVF](https://www.ecb.europa.eu/stats/financial_corporations/investment_funds/html/index.en.html), [ECB Data Portal IVF](https://data.ecb.europa.eu/data/datasets/IVF/data-information). ECB reuse terms not found.

### Inferences
- ECB IVF can validate national-source totals (reasonableness checks) but not fill per-fund fields. FE fundinfo and similar are commercial.

### Gaps
- OECD, IOSCO, EFAMA (statistics are aggregate member data), Euronext/Deutsche Börse/SIX fund platforms, FundsLibrary: not researched in this pass; no sources found/fetched; official vs commercial status unverified.

## Summary answers to key questions
1. Reproducible officially: identity, NAV, fees, minimums, net assets, objectives, managers, holdings (direct); returns, risk stats, allocations, top holdings (computed, needs distributions/benchmark/security master). Not reproducible: ratings, category ranks/peer metrics, Morningstar-style categories, ESG scores, valuation metrics, brokerages.
2. Canonical set: see Q4.
3. Free bulk ID sources with clear terms: GLEIF ISIN-LEI (CC0, limited coverage), GLEIF LEI golden copy (CC0), ESMA FIRDS (public weekly/daily; reuse terms unconfirmed), OpenFIGI (free API, rate-limited, open FIGI). Restricted/paid: ANNA full feeds, CUSIP, Euronext ETF Master File. Unverified: most non-EU exchange lists.
