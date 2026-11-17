# US mutual fund / ETF profile-field gap sources (category, inception, expense ratio, objective, benchmark, share class, managers, minimum investment, net assets)

Research date: 2026-11-17. Tool budget was limited; several sub-questions are unresolved and listed under Gaps. Quoted/sourced facts are separated from inference. Items marked [UNSOURCED-BACKGROUND] come from general knowledge, not verified this session.

## 1. SEC DERA Mutual Fund Prospectus Risk/Return (RR) Summary Data Sets

### Takeaway
The RR data sets are the best official bulk source for class-level fees, objective/strategy text, benchmark-index performance, and inception dates, keyed by series (S...) and class (C...) IDs. They cover only funds that file XBRL risk/return exhibits (open-end funds' prospectuses), have no fund manager or net-assets fields in the prospectus tags, and the published file set has holes (no 2024, no 2017).

### Cited Findings
- Page lists files: monthly `2026-10_rr1.zip`, quarterly 2025 Q1 to 2026 Q3 (`YYYYqN_rr1.zip`), annual `2011`-`2023` (`YYYY_rr1.zip`) plus `2010q4_rr1.zip`. Listed gaps in my fetch: no 2024 file and no 2017 file. Sizes e.g. 2026q1 55.2 MB, 2022 annual 78 MB. — [SEC RR data sets page](https://www.sec.gov/data-research/sec-markets-data/mutual-fund-prospectus-riskreturn-summary-data-sets)
- Full URL pattern: `https://www.sec.gov/files/dera/data/mutual-fund-prospectus-risk/return-summary-data-sets/<filename>` — same page. (Direct fetch of `2023_rr1.zip` exceeded my fetch tool's 10 MB cap, which indicates the file exists; not downloaded.)
- Update note (page reviewed 2026-10-31): datasets "will now be produced monthly and periodically consolidated into quarterly and annual files", superseding the earlier "updated quarterly" statement; a new SCN (Series Class Name) file adds series/class identifiers, names and ticker symbols; earlier submissions used the Risk/Return (RR) taxonomy, current ones use the Open-End Fund (OEF) taxonomy; NUM/TXT `otherdims` now keep the full XBRL context segment. — same page.
- Scope: data extracted from XBRL-tagged exhibits (EX-101) to mutual fund prospectuses, filings from 12/20/2010; "as filed", may contain errors/inconsistencies; not a substitute for filings. — [rr1.pdf readme](https://SEC.gov/dera/data/rr1.pdf) and the page above.
- File layout (readme): SUB (submissions), TAG, LAB, CAL, NUM (numeric facts), TXT (text facts; plain text of non-numeric tagged items, HTML stripped). NUM and TXT rows carry `adsh, tag, version, ddate/qtrs, series (S########), class (10-char class ID C#########), otherdims`. TAG joins on (tag, version) where version is taxonomy of origin or the accession number for custom tags. — [rr1.pdf](https://SEC.gov/dera/data/rr1.pdf) (text extracted locally with pdftotext after decrypting).
- RR taxonomy element names (from SEC RR Preparers Guide 2022-11-04 element listings): fees `ManagementFeesOverAssets`, `DistributionAndService12b1FeesOverAssets`, `OtherExpensesOverAssets`, `AcquiredFundFeesAndExpensesOverAssets`, `FeeWaiverOrReimbursementOverAssets`, `ExpensesOverAssets` (gross total), `NetExpensesOverAssets`; sales loads (`Maximum...ImposedOnPurchases...`, deferred loads); text blocks `ObjectivePrimaryTextBlock`, `ObjectiveSecondaryTextBlock`, `StrategyNarrativeTextBlock`, `RiskTextBlock`, `PortfolioTurnoverTextBlock`; performance `AverageAnnualReturnYear01/05/10/SinceInception`, `AverageAnnualReturnInceptionDate`, `AnnualReturn1990..2025`, bar chart highest/lowest quarterly return; `ExpenseBreakpointMinimumInvestmentRequiredAmount` (breakpoint-related, not a clean "minimum initial investment"); benchmark via `MarketIndexPerformanceTableTextBlock` and a broad-based index member (`...BroadBasedIndexMember` in examples). — [RR Preparers Guide](https://xbrl.sec.gov/rr/2023/rr-preparers-guide-2022-11-04.pdf)
- OEF taxonomy guide (2025-03-17) elements seen: `oef:AvgAnnlRtrPct` (dimensioned by `BroadBasedIndexAxis`, class member, and after-tax members), `oef:ClassName`, `oef:ExpenseRatioPct`, `oef:ExpensesPaidAmt`, `oef:AdvisoryFeesPaidAmt`, `oef:HoldingsCount`, `oef:InvestmentCompanyPortfolioTurnover`, `oef:PerfInceptionDate`, `oef:SecurityExchangeName`, `oef:AddlFundStatisticsTextBlock`, `oef:MaterialChngDate`, `ObjectivePrimaryTextBlock`, `StrategyNarrativeTextBlock`. — [OEF taxonomy guide](https://xbrl.sec.gov/oef/2025/oeftaxonomyguide-2025-03-17.pdf)
- My grep of both guides found no tag for minimum initial investment and no tag for portfolio manager name (only `PreviousInvestmentAdviserTextBlock`, `ExpenseBreakpointMinimumInvestmentRequiredAmount`). Manager/min-investment info is typically in prose text blocks, if at all. — guides above (absence of match, not proof of absence).

### Inferences
- Objective, strategy, class fees, since-inception/10y returns and inception dates are extractable per class; benchmark name must be parsed from the index dimension member label (LAB table) or the market-index table text block.
- Coverage is of open-end mutual funds and ETFs that file prospectus summary exhibits (ETFs on Form N-1A included; ETFs are open-end funds); unit investment trusts and commodity/grantor-trust ETPs (e.g., SPDR Gold) are not N-1A filers, so are outside. Not verified with counts.
- Missing 2024 and 2017 files mean the prospectus-year-2024 data must come from direct EDGAR filing XBRL (R files / Financial Report API) or from the 2025 monthly/quarterly sets, which may hold 2024-filed facts only if later re-filed (not verified). Funds update annually so a 2025 dataset still holds each fund's latest filing in most cases (inference).
- Because facts are as-filed and dated, take the latest `ddate`/filing per (series, class).

### Gaps
- Exact fraction of US funds covered: not found; no SEC statement. Suggested computation: distinct class IDs in latest 12 months of RR+SCN versus SEC's list of class IDs (company_tickers_mf.json) or N-CEN.
- Whether 2024 absence is an SEC omission or a page-listing issue was not determined.
- Complete oef/rr tag catalog was not read in full (PDF tool limitations).

## 2. N-CEN, N-PORT, N-CSR/N-CSRS and Tailored Shareholder Report (TSR) structured data

### Takeaway
N-CEN (annual census) gives fund-type flags (ETF, index, target date, fund of funds, money market) and ETF details; N-PORT gives holdings-level asset/issuer categories and fund net assets; TSR (Inline XBRL, OEF taxonomy) gives class-level expense ratio, net assets, holdings count, turnover, and 1/5/10-year returns vs index for the filings since the July 2024 compliance date.

### Cited Findings
- N-CEN data sets: 33 quarterly ZIPs `YYYYqN_ncen.zip` from 2018 Q3 to 2026 Q3, flat TSV extracted from N-CEN XML; includes `ETF.tsv` with `REDEEMED_SHARES_PER_CREATION_UNIT` from 2024 Q1; filings in N-CEN schema 3.1 (EDGAR 25.2) not yet included; as-filed, accuracy not guaranteed. — [SEC N-CEN data sets](https://www.sec.gov/dera/data/form-ncen-data-sets) (readme `ncen_readme.pdf` linked there; not read)
- SEC staff fund statistics use N-CEN Item C.3 for index-fund indication; categories (ETF, index, fund of funds, target date) are not mutually exclusive. Funds are grouped by prevalent asset class. — [SEC registered fund statistics (2025-08-14)](https://www.sec.gov/files/investment/im-investment-registered-fund-statistics-20250814.pdf), via search summary (PDF not machine-readable to my tool)
- N-PORT per-holding `assetCat` (e.g., equity-common, debt, ABS-MBS), `issuerCat`, `invCountry` (via third-party API doc). — [sec-api.io N-PORT](https://sec-api.io/api-reference/form-nport)
- N-PORT bulk sets exist at SEC (page URL I tried returned 404; not verified). ICE sells N-PORT asset/issuer classification data. — [ICE](https://developer.ice.com/fixed-income-data-services/catalog/ice-regulatory-n-port)
- TSR rule: Release 33-11125 (final rule 2022, S7-09-20); compliance date July 24, 2024; TSRs must show net assets, number of holdings, portfolio turnover, and 1/5/10-year average annual returns (NAV based); Inline XBRL tagging. — [SEC final rule](https://www.sec.gov/rules-regulations/2022/10/s7-09-20), [Filepoint summary](https://filepoint.com/news-resources/tailored-shareholder-report-final-rule/), [SEC ADI 2024-14](https://www.sec.gov/about/divisions-offices/division-investment-management/accounting-disclosure-information/adi-2024-14-tailored-shareholder-report-common-issues)
- EdgarTools (third party) parses N-CSR/N-CSRS TSRs: per class `class_name`, `class_ticker`, `expense_ratio_pct` (decimal, 0.0094=0.94%), `holdings_count`, `annual_returns`; via DataFrames `expenses_paid`, `advisory_fees_paid`, `inception_date` ("if reported"); report-level `net_assets` (full dollars), `portfolio_turnover`, `fund_name`; classes from `oef:ClassAxis`. — [EdgarTools guide](https://edgartools.readthedocs.io/en/latest/guides/fundshareholderreport-data-object-guide/)
- TSR example with ClassAxis net assets: [Sequoia N-CSRS](https://www.sec.gov/Archives/edgar/data/89043/000119312525188618/d948069dncsrs.htm).

### Inferences
- TSR is the freshest source for class expense ratio (actual, realized) and net assets, but net assets in TSR may be fund/series level, repeated per class (EdgarTools shows report-level only); class-level assets would need N-PORT/other.
- I did not find an SEC-published bulk data set for TSR; extraction means per-filing Inline XBRL (or the SEC Financial Statement-style APIs) — unverified. Per-filing fetch from EDGAR via data.sec.gov submissions + filing index is the likely route.
- N-CEN index flag + target-date flag + fund-of-funds + ETF flag + N-PORT asset mix (equity/debt/money market share of NAV, country split) could support a coarse derived taxonomy (asset class / index vs active / target date / international vs domestic). Style box (growth/value, size) and sector categories cannot be obtained from these without holdings-to-fundamentals joins.

### Gaps
- Fields list in N-CEN readme (flags names, series/class IDs mapping) not read.
- No verified SEC TSR bulk dataset; no confirmation of coverage fraction.
- N-PORT data set page and net-assets field names not verified (SEC URL 404 on my attempt).
- Manager names: N-CEN does carry adviser/sub-adviser names (fund level) [UNSOURCED-BACKGROUND]; individual portfolio managers appear only in prospectus/SAI text (Item 5 of N-1A) — not tagged as a field.

## 3. Open or official category equivalents to Morningstar/Lipper

### Takeaway
I found no official or openly licensed classification equivalent to Morningstar/Lipper categories. SEC offers only coarse prevalent-asset-class and flag-based groupings in statistics. Derivation from N-CEN + N-PORT is feasible for coarse buckets only.

### Cited Findings
- SEC registered fund statistics group funds by prevalent asset class and flag fund of funds and index funds (index from N-CEN C.3); categories overlap. — [SEC statistics PDF](https://www.sec.gov/files/investment/im-investment-registered-fund-statistics-20250814.pdf); [SEC visualization](https://www.sec.gov/data-research/data-visualizations/registered-fund-statistics/registered-funds-fund-portfolio-investments-category)
- N-PORT asset categories describe security types, not style. — [sec-api.io](https://sec-api.io/api-reference/form-nport)

### Inferences
- Legit derived category: build own taxonomy (e.g., Equity/Bond/Allocation/Money Market/Alternative, US vs international, index vs active, target date year, fund of funds) from N-CEN flags + N-PORT asset mix, labelled as "derived" and not named after Morningstar/Lipper categories.
- Style/size and fixed income duration/credit buckets would need holdings-level market cap/maturity/ratings joins; N-PORT has debt maturity/coupon and ratings fields [UNSOURCED-BACKGROUND].
- Another proxy: benchmark index name from RR/TSR (e.g., "S&P 500", "Bloomberg US Aggregate") mapped to a category with a hand-built lookup; also fund name text / objective text classification (own-derived).

### Gaps
- Not researched: Nasdaq/NYSE/Cboe ETF type lists, FINRA, Treasury/IRS classifications, issuer-site categories (Vanguard/iShares), and open-source projects that derive categories. A search for open-source methodology returned nothing relevant.

## 4. Vendors and redistribution restrictions

### Takeaway
Morningstar and Lipper categories are proprietary and licensed by contract; public redistribution in a commercial product needs a license. No public rate card was found.

### Cited Findings
- Morningstar's Essentials toolkit includes a broad distribution license covering Morningstar Rating, Categories, Style Box and Factor Profiles; marketing use is reviewed and requires prescribed disclosure language; contact licensedproducts@morningstar.com. — [Morningstar Essentials Guidelines US](https://advisor.morningstar.com/Enterprise/VTC/Essentials_Guidelines_US_2023_0323.pdf)
- Morningstar Direct subscription grants "limited, nonexclusive, nontransferable" license, with extra restrictions on internal distribution and territory in separate agreements. — [Morningstar Direct agreement](https://gladmainnew.morningstar.com/directhelp/General/Subscription_Agreement.htm)
- Brand guidance: redistribution of Morningstar data to clients always involves a contract; attribution required. — [Morningstar third-party branding](https://design.morningstar.com/foundations/third-party)
- A university library's Morningstar Direct access is for research/teaching, commercial use prohibited (institution-specific). — [HBS library](https://www.library.hbs.edu/Find/Databases/Morningstar-Direct)
- LSEG Lipper: 500+ classifications; Fund Marketing License needed to publish Leaders Ratings, benchmarks, rankings; data via Lipper feeds (Global Data Feed, Snowflake). — [LSEG Lipper](https://www.lseg.com/en/data-analytics/asset-management-solutions/lipper-fund-performance), [Lipper Global Data Feed factsheet](https://www.lseg.com/content/dam/data-analytics/en_us/documents/fact-sheets/lseg-lipper-global-data-feed-factsheet.pdf)

### Inferences
- Licensing routes: Morningstar (Direct/Data feeds/Essentials, enterprise quote), LSEG Lipper (data feed/Snowflake, quote), plus FactSet/ICE/Bloomberg/CRSP fund databases [UNSOURCED-BACKGROUND]. Pricing is negotiated; budget estimates not found.
- Do not scrape Morningstar/Yahoo/Lipper categories into a commercial dataset; terms of those sites generally prohibit it (not verified for each site).

### Gaps
- ICE and FactSet category redistribution terms: not found. Lipper redistribution clauses and Morningstar category-specific display rights: not found. Pricing: not found.

## 5. SEC/EDGAR terms for commercial reuse

### Takeaway
EDGAR filing content is free to reuse commercially; automated access must follow fair access (10 req/s, declared User-Agent).

### Cited Findings
- Fair access: "Current max request rate: 10 requests/second"; declare User-Agent with company name and admin contact email; download only needed data; no botnets; no technical support for scripts; bulk sources (daily/full index, Feed, Oldloads, company ticker/CIK files) free. — [SEC accessing EDGAR data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data)
- SEC FAQ: government-created content and EDGAR public filing content "free to access and reuse" with very few exceptions. — [SEC webmaster FAQ](https://www.sec.gov/about/webmaster-frequently-asked-questions)
- 15 U.S.C. 78ll: EDGAR information may be used, resold, redisseminated by any person lawfully obtaining it without restriction or additional fees/royalties (as summarized in search result). — [15 USC 78ll](https://m.openjurist.org/book/export/html/13385567)
- SEC data sets disclaim accuracy and completeness. — SEC pages above.

### Inferences
- Commercial use fine; retain provenance, disclaim as-filed data, honor rate limit. The fee-based Public Dissemination Service is separate and not needed for public EDGAR.

### Gaps
- Fair-access page states no specific licence terms (the above statutes are secondary summaries); I did not read the SEC Privacy & Security policy directly.

## Field-to-source map (synthesis, inference)
| Field | Best source | Notes |
|---|---|---|
| Category/style | None official; derive from N-CEN flags + N-PORT mix + benchmark name | label as derived; vendors need licence |
| Inception date | RR `AverageAnnualReturnInceptionDate`, `AnnualReturnInceptionDate`; OEF `PerfInceptionDate` | class-level, if filed |
| Expense ratio | TSR `oef:ExpenseRatioPct` (actual); RR `ExpensesOverAssets`/`NetExpensesOverAssets` (prospectus) | decimal fractions |
| Objective | RR `ObjectivePrimaryTextBlock` (TXT table) | text |
| Benchmark | RR/OEF index dimension + market index table; TSR `BroadBasedIndexAxis` | name in LAB / member label |
| Share-class attributes | RR SCN file, class IDs, loads/12b-1 tags, ticker | |
| Managers | No tag; N-CEN adviser names (fund level); prospectus text | gap |
| Minimum investment | No clean tag; prospectus text (Item 6 N-1A) | gap |
| Net assets | TSR `NetAssets` (report-level), N-PORT | class-level gap |
