# Official fund-data sources: Australia (AU) and United Arab Emirates (AE) - research as of 2026-11-18

Method: curl with a browser User-Agent from the project host on 2026-11-17/18 plus WebSearch. VERIFIED = fetched this session (real header/sample given). UNVERIFIED = search snippet or inference only. Official = regulator, exchange, central bank, tax/pension authority, or the product issuer's own file. UNOFFICIAL is labelled. Bot-blocked sites were not worked around. Repo code was not edited. Local state: connectors `app/connectors/gsfm.py`, `app/connectors/australian_managed_funds.py`; catalog rows `gsfm_unit_prices`, `au_user_managed_funds`, `uae_local_funds`; DB AU 97 funds / 5 with NAV, AE 0 (per 00_current_db_coverage.md).

---

## Q1. Australia: integrated sources and why they under-deliver

### Takeaway
Both integrated AU sources are thin. GSFM is one boutique manager's CSV and the user-supplied CSV is a 96-row master with empty ISIN and NAV columns, which is why only 5 of 97 funds have NAV. Neither is a regulator or exchange feed. The real official coverage sits in sources not yet used (Q2).

### Cited Findings
- `gsfm.py` downloads `https://www.gsfm.com.au/funds-data/combined-unit-prices/?export=csv`. It requires the header `fund,code,as_at_date,nav_price`, ingests only rows whose fund name explicitly says AUD, and has `license_status: Unknown`. It is a manager's current snapshot, not history. [repo: /media/asim/4_TB_1/MFAPI/MF ETL PIPELINE/app/connectors/gsfm.py]
- `australian_managed_funds.py` reads a user-provided CSV (manager, subcategory, structure, currency, URL). Its own manifest says: "All 96 rows have empty ISIN and nav_aud fields". [repo: app/connectors/australian_managed_funds.py; reports/au_user_managed_funds_dataset_manifest.json]
- The catalog describes `au_user_managed_funds` as "Fund master metadata only; no NAV or ISIN values supplied" and lists no official AU regulator, exchange or ETF issuer source. [repo: app/catalog.py]
- The ASIC managed investment scheme (MIS) register on data.gov.au does not exist as a dataset. The ASIC-authored data.gov.au datasets (VERIFIED via CKAN `package_search?q=asic`, 12 datasets) are: Company, Business Names, Financial Adviser, AFS Authorised Representative, AFS Licensee, Banned & Disqualified Organisations and Persons, Credit Representative, Credit Licensee, Registered Auditor, Liquidator, SMSF Auditor. All are cc-by. None is an MIS or fund dataset. — [data.gov.au CKAN](https://data.gov.au/data/api/3/action/package_search?q=asic&rows=200)
- ASIC's own register page lists no bulk MIS extract. Funds are registered through ASIC eLicensing and looked up through ASIC Connect per ARSN; only per-scheme extracts are documented. — [ASIC search registers](https://www.asic.gov.au/online-services/search-asics-registers/); [ASIC connectonline sample extract help](https://connectonline.asic.gov.au/OPH/HelpLandingPages/TH_PurchasingSearchItems/IMG_ACON_CUR_MANG_INVEST_SCH)
- Treasury consulted on 23 Sep 2026 on enhanced MIS data collection. This is a proposal, not a data release. — [Treasury media release](https://ministers.treasury.gov.au/ministers/daniel-mulino-2025/media-releases/improving-transparency-australias-managed-investment); [Allens](https://www.allens.com.au/insights-news/insights/2026/10/Treasury-proposes-enhanced-data-reporting-for-managed-investment-schemes/)

### Inferences
- With no official bulk MIS register, the AU fund universe must be built bottom-up from the ASX product universe (about 600 listed funds) and from issuer files. Unlisted retail funds (APIR-coded) have no single free official list.

### Gaps
- Whether ASIC Connect or ASIC's registers offer a paid bulk MIS extract or API: not found. The only API lead was a third-party scraper listing (parse.bot), which is UNOFFICIAL.

---

## Q2. Australia: every official source not yet used

### Takeaway
Best-value additions: (1) per-ETF issuer files (Vanguard JSON, BetaShares CSV, VanEck XLSX), which give NAV history, holdings, fees, distributions and inception for free; (2) ASX's monthly Investment Products Report plus ASX's own ETP key-stats endpoint, which give the full ETP/LIC universe with ASX code, MER, FUM and returns; (3) ATO USI list and APRA statistics for superannuation products. mFund is dead.

### Cited Findings

**ASX (exchange)**
- mFund was discontinued in May 2026. VERIFIED footnote in the ASX report: "Historical Total ASX Funds data includes the mFund product. The mFund product was discontinued in May 2026." — [ASX Investment Products Oct 2026 PDF](https://www.asx.com.au/content/dam/asx/issuers/asx-investment-products-reports/2026/pdf/asx-investment-products-oct-2026.pdf). The prior note's mFund lead should be dropped; older mFund update PDFs exist but are historical.
- ASX Investment Products Report, monthly PDF. VERIFIED: HTTP 200, `application/pdf`, 1,383,360 bytes. Header: "Investment Product Summary - October 2026 ... Period ending Friday, 30 October 2026". Counts: ETPs 477 listed ($377.93bn), LIVs (LICs/LITs) 90, AREITs 40, Infrastructure 3, total 610. Per-product rows give ASX code, type (ETF/Active/Complex), fund name, MER %, FUM, flows, price, 1M/1Y/3Y/5Y returns, e.g. `VGE ETF Vanguard FTSE Emerging Markets Shares ETF 0.48 ... 87.60 ...`. URL pattern `/content/dam/asx/issuers/asx-investment-products-reports/{YYYY}/pdf/asx-investment-products-{mon}-{YYYY}.pdf`. No ISIN or APIR in the PDF. Free, with no authentication. It is PDF only (parse with pdftotext -layout).
- ASX listed-company CSV is VERIFIED: `https://www.asx.com.au/asx/research/ASXListedCompanies.csv` returned 200 `text/csv`, 2,063 lines, header "ASX listed companies as at Wed Nov 18 05:19:28 AEDT 2026", columns `Company name,ASX code,GICS industry group`. It includes only some funds (38 lines match "ETF"); A200, VAS, IOZ and MOAT are absent, so it is not an ETP list. It is not usable as the fund universe.
- ASX's own site API (undocumented; it powers asx.com.au; the CSP header names markit as the data vendor), VERIFIED with plain GET and no auth:
  - `https://asx.api.markitdigital.com/asx-research/1.0/etfs/A200/key-statistics` returned 200 JSON: `{"data":{"shareInformation":{"ISIN":"AU00000A2000","priceClose":151.42,"nav":148.70021,"sharesOutstanding":76833604},"dividends":{"dateExDate":"2026-10-01","dividend":1.6733,"frankingPercent":84.46},"fundamentals":{"trackingError":0.2,"managementFeePercent":0.04}}}`.
  - `.../etfs/A200/header` returned 200: `dateAdmitted 2018-05-08, fundType "Equity Australia Large Blend", netAssets 11425173049, trackingIndex "Solactive Australia 200 TR AUD", premiumDiscountAverageOneMonthPercent 0.04, status, symbol`.
  - It gives ISIN, NAV, net assets, category, benchmark and admission date per ticker. It is not a documented public API and the terms are not reviewed, so keep it low-volume and label it "exchange-site endpoint, undocumented".
- Old ASX endpoints returned 404 this session: `/asx/v2/statistics/prevBusDayAllTradedFunds.do`, `/data/trt/ticker_list.csv`, `/markets/trade-our-cash-market/asx-investment-products-directory/etps` (the directory page moved). ASX also offers an "ETP Spotlight" Excel table, per its blog (UNVERIFIED download link). — [ASX blog](https://asx.com.au/blog/investor-update/2022/free-asx-information-to-help-your-investment-research)

**Issuer files, official because they are the product issuer's own disclosure (daily, machine-readable, free)**
- Vanguard Australia. VERIFIED JSON endpoint behind vanguard.com.au: `GET https://www.vanguard.com.au/personal/api/products/personal/fund/8205/price-history` returned 200 `application/json`, 1,001,167 bytes, with `access-control-allow-origin: www.vanguard.com.au`. Keys: `fundName "Vanguard Australian Shares Index ETF"`, `shortName VAS`, `fundCurrency AUD`, `productType etf`, `taxationStatus AMIT`, `inceptionDate 2009-05-04`, `assetClass equity`, `benchMarkNameFromECS "S&P/ASX 300 Index"`, `distFrequency Quarterly`, `recommendedHoldingPeriod 7 years`, `fundFees` (`ADJEXPRTPC` 0.07; buy/sell spread codes BUSS and others at 0), `navPrices` (185 rows, `{asOfDate 2026-11-17, price 110.0919, amountChange, percentChange}`, from 2026-02-27 to 2026-11-17), `buyPrices`, `sellPrices`, `periodicDistributions` (70 rows with ex-date, record date, pay date, reinvest price, tax components), `inavInfo`, `aumAmount`, `aumAsOfDate 2026-10-31`, `listings` (ASX code, exchange, FND_SHRCLS_GR_ID), `documentDetails` (factsheet/PDS/TMD PDF links), `monthlyReturns`. The suffix path `/holdings` returned a different payload, with `sectorDiversification`, `marketAllocation` and `regionExposure` (aggregate allocation, not security-level). The same endpoint family is advertised to the web app only; no documentation or terms found. `robots.txt` disallows only error pages and `/tools/*`. Portfolio IDs (e.g. 8205) must be enumerated from the site (sitemap-personal.xml); `tradingSymbols.APIR` came back null for VAS.
- BetaShares. VERIFIED two plain-file endpoints that are linked from each fund page (A200 shown):
  - Full holdings CSV: `https://www.betashares.com.au/files/csv/A200_Portfolio_Holdings.csv` returned 200 `text/csv`, 21,799 bytes, 213 lines. Preamble rows are `Betashares Portfolio Holdings,`, `Fund Name,Betashares Australia 200 ETF`, `Fund ASX Code,A200`, `Date,2026-11-16`, followed by the holdings table.
  - NAV history CSV: `https://www.betashares.com.au/wp-admin/admin-ajax.php?action=fund_nav_csv&ticker=A200` returned 200 `text/csv`, 90,876 bytes, 2,165 rows, header `Fund,Date,NAV,Distribution,Total Fund Return`, `A200,2018-05-07,100.35309,,100.0000000000` through `A200,2026-11-17,148.70611,,203.5862931596`. This is full history since inception, including distribution amounts.
  - Fund pages also link TMD (`/files/TMD/A200.pdf`), PDS, factsheet and financial statements. robots.txt disallows only `/learn/`, `/lp/` and `/super/insurance-sen/`. Page URL pattern `/fund/<category>/<ticker>/` (some redirect with 301). The ticker list can be taken from the sitemap (`https://www.betashares.com.au/sitemap_index.xml`).
- VanEck Australia. VERIFIED: `https://www.vaneck.com.au/etf/equity/moat/downloads/holdings/` returned 200 XLSX (6,368 bytes, "All MOAT holdings", labelled Daily) and `.../downloads/fundhistoprices/` returned 200 XLSX (163,862 bytes, "NAV & premium/discount history", Daily). The pages also carry a schema.org Dataset JSON link `https://www.vaneck.com.au/Main/FundDatasetBlock/Get/?blockId=...&ticker=MOATAU` (not tested) and an annual tax attribution XLSX. The VanEck AU path pattern is `/etf/<category>/<ticker>/downloads/...`.
- iShares Australia (BlackRock). UNVERIFIED. The product directory page loads (200) but it is a generic BlackRock directory, and the guessed `.ajax?fileType=csv` holdings URL returned an HTML page instead of CSV. The iShares holdings CSV needs the per-product product-ID URL taken from each product page.
- Others not tested (UNVERIFIED): Magellan, Perpetual, Platinum, Fidelity AU, Macquarie, Betashares active/unlisted funds, Global X, Janus Henderson, Pendal. The pattern is that each publishes unit prices on its site; some publish daily unit-price CSVs (GSFM does). They are the only source for unlisted retail funds.

**Superannuation (official, different product class)**
- ATO Super Fund Lookup USI list. VERIFIED: `https://superfundlookup.gov.au/Tools/DownloadUsiList?download=usi` returned 200 `application/octet-stream`, `Content-Disposition: attachment; filename=SflUsiExtract.txt`, 539,593 bytes, 1,121 data rows (CRLF, fixed-width 482 chars). Columns and start positions: ABN (1), Fund name (13), USI (214), Product name (235), Contribution restrictions (436), From date (461), To date (472). Example row: `11635839852 SUPER SA FLEXIBLE ROLLOVER PRODUCT 11635839852001 Super SA - Flexible Rollover Product Y 2013-12-16 9999-12-31`. The page says the URL can be used from scheduled jobs. No auth. USI is the superannuation product identifier.
- APRA Annual Superannuation Bulletin (released 16 Dec 2025). VERIFIED XLSX files (CC BY 3.0 AU) at `https://www.apra.gov.au/news-and-publications/annual-superannuation-bulletin`: `.../2026-05/Annual superannuation bulletin June 2015 to June 2025 - MySuper.xlsx` (429,823 bytes, tabs `Tab_MYS1_Data`, `Tab_MYS2_Data`; long format `TABLE_ID, FUNDTYPE_ALL, LINE_ITEM, LINE_ITEM_CODE, Tab_Row_No, Jun 2015 ... Jun 2025`), plus `... - Superannuation entities.xlsx`, `... - licensees (1).xlsx`, and CSVs for `Administration and other expenses` and `Investment management expenses`. The MySuper table is industry-segment aggregates, not product by product. Fund-level assets and fees are in the "Superannuation entities" file (not opened).
- APRA Quarterly superannuation statistics page VERIFIED to host `Quarterly superannuation performance statistics - December 2004 to June 2026 _0.xlsx` and `Quarterly MySuper statistics from September 2020 to June 2026_1.xlsx` (under `/system/files/2026-08/`). The Quarterly Superannuation Industry Publication page hosts `Quarterly Superannuation Industry Publication - June 2026.xlsx` and three Key Metrics CSVs (e.g. `Key Metrics Dataset - Industry Composition.csv`, 1,897,393 bytes, header `Publication_Name,Table_Name,Sub_Table_Name,Metric_Name,Period,Reporting_Level,...,Product_Type,Product_Phase,Fund_Type,Product_Category,Investment_Option_Type,... Value`). — [APRA quarterly stats](https://www.apra.gov.au/quarterly-superannuation-statistics); [APRA industry publication](https://www.apra.gov.au/quarterly-superannuation-industry-publication)
- APRA pages that exist for product-level data (page text seen, files not downloaded): "Superannuation product performance" (comprehensive product performance package, successor of the MySuper heatmap) and "Annual superannuation performance test" results (Your Future Your Super: 2023, 2024 and 2025 MySuper and trustee-directed products) under `https://www.apra.gov.au/superannuation/performance-and-transparency/...`. The old URL `/news-and-publications/superannuation-product-heatmap` returned 404. APRA's first heatmap was Dec 2019. — [APRA performance pages index](https://www.apra.gov.au/statistics); [MySuper Product Heatmap Data Insights PDF](https://www.apra.gov.au/sites/default/files/MySuper%20Product%20Heatmap%20-%20Data%20Insights.pdf)
- data.gov.au carries APRA datasets (`quarterly-superannuation-performance`, `quarterly-mysuper-statistics`, `annual-superannuation-bulletin`; cc-by) but the resource URLs are stale links to old apra.gov.au pages, so use apra.gov.au directly.
- APRA's Super register ("List of superannuation institutions") is linked from `/registers/list-superannuation-institutions` (not downloaded).

**Not available or not useful**
- FSC (Financial Services Council) fund statistics are member-only or paywalled (UNVERIFIED; not probed). RIAA is an industry certification body (UNVERIFIED). Morningstar AU is UNOFFICIAL.
- AFS licensee dataset on data.gov.au (cc-by, ASIC) gives responsible entities and licensees but not funds. — [data.gov.au asic-afs-licensee](https://data.gov.au/data/dataset/asic-afs-licensee)
- DDO target market determinations are published as per-fund PDFs by issuers (e.g. BetaShares `/files/TMD/A200.pdf`; VanEck TMD PDFs). No central register was found. They are unstructured.

### Inferences
- ASX codes from the monthly report (610 securities) provide the universe. The ASX key-stats and header endpoints then fill ISIN, NAV, net assets, category and benchmark per code. Issuer files fill history and holdings.
- Issuer file layouts are stable per issuer, so a per-issuer adapter (Vanguard, BetaShares, VanEck first) is cheap and covers a large share of ETF AUM, though not unlisted funds.

### Gaps
- Official APIR code list for unlisted funds: no free official source found (APIR is administered by APIR Systems Ltd, not tested). Vanguard's `tradingSymbols.APIR` was null for VAS.
- Terms of use and rate limits for the Vanguard JSON and ASX markit endpoints were not reviewed.
- Magellan, Perpetual, Platinum, Fidelity, Macquarie and iShares AU endpoints were not tested.
- APRA product-level performance and heatmap files were not located as direct file URLs.

---

## Q3. Australia: field-by-field matrix and connector design

### Takeaway
ETFs can reach near-complete coverage (NAV history, holdings, fees, distributions, inception, benchmark, net assets, category, status) from official issuer and exchange files. Unlisted funds and superannuation products stay thin. Risk indicator and share class are the weakest fields everywhere.

### Cited Findings (matrix; source evidence above)
| Field | Best official source | Status |
|---|---|---|
| Daily NAV + history | BetaShares NAV CSV (since 2018 inception), VanEck fundhistoprices XLSX, Vanguard `navPrices` JSON (roughly 185 rows per call) | VERIFIED |
| Current NAV, any ETP | ASX `etfs/{code}/key-statistics` field `nav` | VERIFIED (undocumented) |
| Holdings | BetaShares `_Portfolio_Holdings.csv`, VanEck holdings XLSX; Vanguard JSON gives sector/region/market allocation only | VERIFIED |
| Manager / RE | ASX header `displayName`, issuer pages; ASIC AFS licensee dataset (cc-by) to normalise RE names | partial |
| Administrator / custodian | financial statements and PDS PDFs only | not machine-readable |
| ISIN | ASX key-statistics `ISIN` | VERIFIED |
| Ticker / APIR | ticker from ASX and issuers; APIR not found (null for VAS) | partial |
| Category | ASX header `fundType` ("Equity Australia Large Blend"); ASX report grouping; Vanguard `assetClass/subAssetClass` | VERIFIED |
| Inception date | ASX `dateAdmitted`; Vanguard `inceptionDate` | VERIFIED |
| Net assets | ASX header `netAssets`; Vanguard `aumAmount` + `aumAsOfDate`; ASX report FUM | VERIFIED |
| Currency | Vanguard `fundCurrency`; BetaShares/ASX AUD | VERIFIED |
| Fees (MER/ICR) | ASX report MER column; ASX `managementFeePercent`; Vanguard `fundFees` | VERIFIED |
| Buy/sell spread | Vanguard buy/sell price series and BUSS codes | VERIFIED (Vanguard only) |
| Risk indicator | none official as structured data (PDS standard risk measure is in PDFs); ASX gives `standardDeviation`, `beta`, `trackingError` | partial |
| Benchmark | ASX `trackingIndex`; Vanguard `benchMarkNameFromECS` | VERIFIED |
| Distributions | BetaShares `Distribution` column; Vanguard `periodicDistributions`; ASX `dividends` (incl. franking) | VERIFIED |
| Status | ASX `status` field (empty for A200), report "Recent Admissions" | partial |
| Share class | Vanguard `fundShareClass` | VERIFIED (Vanguard) |
| Super products | USI list (fund name, USI, ABN, product name, dates); APRA assets/fees/returns aggregates | VERIFIED |

### Cited design (concrete, based on VERIFIED endpoints)
1. `au_asx_universe`: download the latest ASX Investment Products PDF, parse code, type, name, MER, FUM and returns (pdftotext -layout) into the `funds` stub (610 securities). Poll monthly.
2. `au_asx_etp_enrich`: per code, GET `asx.api.markitdigital.com/asx-research/1.0/etfs/{code}/header` and `/key-statistics` to set isin, inception_date, net_assets, category, benchmark, current NAV and fees. Throttle to about 1 request/sec and cache. Treat as undocumented.
3. Issuer adapters keyed by ASX code: `betashares` (holdings CSV + NAV CSV, skip the 6-line preamble, `Date` in the file gives the holdings date); `vaneck` (two XLSX downloads); `vanguard` (price-history JSON: NAV, fees, distributions, AUM, inception; allocation via `/holdings`). Load NAV into `nav_observations`, holdings into `portfolio_holdings`/`holding_metrics`, and snapshot of fees/benchmark/distributions into `fund_profile_snapshots` JSONB.
4. `au_super_usi`: download ATO USI list monthly, parse fixed widths, create `fund_type=superannuation_product` stubs keyed by USI; join APRA annual bulletin entity and MySuper XLSX for assets and fees (aggregates only).
5. Keep `gsfm_unit_prices` as the template for unlisted manager CSVs. Add further managers only where a machine-readable unit-price file is confirmed.
6. Dedup via ISIN (ASX) then ticker; labelling `source_tier = official_issuer | official_exchange | official_regulator`.

### Inferences
- Coverage estimate: about 480 ETPs plus about 90 LIVs from the ASX universe; full NAV/holdings only for issuers with adapters. Superannuation items (about 1,100 USI rows) are product records, not unit-priced funds.

### Gaps
- No official source found for category, administrator/custodian or risk indicator as structured data for unlisted funds; those require PDS PDF extraction.

---

## Q4. UAE: integrated sources and why they under-deliver

### Takeaway
AE has 0 funds. The catalog row `uae_local_funds` points to the regulator's open-data page, which is a JavaScript-rendered, search-only table. It exposes fund name and offering type only and has no visible bulk download, so nothing has been importable.

### Cited Findings
- Catalog row: `("AE","uae_local_funds","UAE Capital Market Authority","Local Investment Funds","https://www.uaecma.gov.ae/en/open-data/mutual-funds/local-funds.aspx", ...)`: "format, fund-level fields, and reuse terms need inspection", "NAV not confirmed". [repo: app/catalog.py]
- The regulator is now the Capital Market Authority (CMA). Federal Decree-Law No. 32 of 2025 (CMA Law) and No. 33 of 2025 took effect on 1 Jan 2026 and reconstitute the SCA as the CMA. Domain `www.uaecma.gov.ae` returns 200; `www.sca.gov.ae/...` 301-redirects to it. — [Cleary Gottlieb](https://www.clearygottlieb.com/news-and-insights/publication-listing/uae-capital-markets-overhaul-2026-new-regulatory-framework-for-the-capital-market-authority)
- VERIFIED page content: `https://www.uaecma.gov.ae/en/open-data/mutual-funds/local-funds.aspx` returned 200 `text/html`, 98,505 bytes. The visible table is `# | Fund Name | Offering Type` with Category and Search filters and pagination, and no download link. The site's menu has "Open Data > Authorized and Registered Investment Funds" (local and foreign pages) and a "Bayanat.ae" link.
- The table loads from `api/PublicApi/GetContentList` (page script; request includes `typeId:1036`, template `ajax-templates/pages/localfund.html`). A direct POST without an Origin header returned 403 `{"success":false,"message":"Origin header required for state-changing requests","code":"CSRF_PROTECTION"}`. I did not forge the header to get past the protection; the endpoint is therefore UNVERIFIED and should only be used after asking the CMA or checking the site terms.
- CMA fund counts (secondary): about 58 local funds expected in 2024 (Mondo Visione), 633 registered foreign funds at end-2016, 114 new foreign registrations in 2020. — [Mondo Visione](https://m.mondovisione.com/news/the-uae-securities-and-commodities-authority-reveals-a-surge-of-dh35-billion-in-2024828); [Mubasher](https://english.mubasher.info/news/3124778/UAE-foreign-investment-funds-rise-5-6-in-2016-SCA); [TrendsMENA](https://trendsmena.com/geostrategy/uaes-sca-registers-114-foreign-investment-funds-in-2020/)

### Inferences
- The regulator list is a register without NAV. Even if its table can be read, it provides names and offering type only.

### Gaps
- Whether the CMA open-data table has a documented export/API and permissive reuse terms.
- Whether Bayanat holds a fund dataset: `https://bayanat.ae/en/Search?query=investment%20fund` returned 200 HTML (a search page, no results extracted, so UNVERIFIED).

---

## Q5. UAE: every official source not yet used

### Takeaway
UAE has no central NAV platform. Official lists are registers (CMA, DFSA, ADGM FSRA) and exchange listings; NAV lives with managers and distributors. The only machine-friendly NAV table found is a distributor PDF (Dubai Islamic Bank), which is the bank's own publication and not a regulator source.

### Cited Findings
- ADGM FSRA Register of Passported Funds. VERIFIED: `https://assets.adgm.com/download/assets/20251120_ADGM_PassportedFunds_PublicRegister.pdf/94ed2082705611ef8b57fee44bda6edd` returned 200 `application/pdf`, 163,889 bytes, 211 text lines. Columns: Date passported, Fund name and registered address, Fund manager name and address, Agents, Public/Private, Passported to (DIFC/DFSA, UAE/SCA), Date withdrawn. It is a regulator register (no ISIN, NAV or currency), updated per edition (the 20 Nov 2025 and 11 Jun 2025 editions are indexed). Other ADGM registers sit behind `https://www.adgm.com/public-registers/fsra`, which returned 403 (Cloudflare challenge, not bypassed). — [ADGM passported funds PDF](https://assets.adgm.com/download/assets/20251120_ADGM_PassportedFunds_PublicRegister.pdf/94ed2082705611ef8b57fee44bda6edd)
- DFSA public register (domestic and foreign funds). Reachable only via `https://www.dfsa.ae/public-register/funds`, which returned 403 "Attention Required! | Cloudflare" to curl. UNVERIFIED and blocked. The old complinet host `dfsa.complinet.com` refused the connection. A search result says an HK SFC document cites the same URL; as of 22 Mar 2024 there were 41 public funds per an SFC source. — [HK SFC information sheet](https://sfc.hk/TC/faqs/Publicly-offered-investment-products/Information-Sheet-on-Offering-of-Hong-Kong-Domiciled-Funds-in-Dubai-International-Financial-Centre). DFSA fund types: Public, Exempt and Qualified Investor Funds (domestic); External/Foreign funds.
- Exchanges: ADX (`adx.ae`) returned 403 Cloudflare, so its ETF list is UNVERIFIED. Press says ADX listed its first ETF in Aug 2020 and had 21 ETFs in early 2026 (Lunate quantum computing, AI, luxury; KraneShares AGIX and KWIN cross-listings). — [Khaleej Times](https://www.khaleejtimes.com/business/markets/adx-marks-first-public-offering-of-2026-in-uae-capital-markets-with-listing-of-luxury-focused-etf); [WAM](https://www.wam.ae/en/article/bmw8u9b-adx-provides-investors-with-access-global). DFM (`dfm.ae`) loads (200) but `/the-exchange/market-data/etfs` was 404. Nasdaq Dubai home loads (200); its funds page `/products/funds` was 404; the "Listing criteria" page confirms funds (equity, bond, hedge, ETFs, REITs) can list under DFSA rules and is VERIFIED (200, 100,711 bytes). Press mentions Emirates REIT and The Bitcoin Fund listed there. Clearstream states Nasdaq Dubai is the ISIN issuing authority for its securities. — [Nasdaq Dubai listing criteria](https://www.nasdaqdubai.com/listing/listing-criteria); [Clearstream](https://clearstream.com/clearstream-en/res-library/market-coverage/securities-trading-united-arab-emirates-nasdaq-dubai--1281516)
- Distributor publication (NOT a regulator source; the bank's own document): Dubai Islamic Bank "Mutual Fund List", `https://www.dib.ae/docs/default-source/cpr/dib-funds-list.pdf`. VERIFIED: 200 `application/pdf`, 288,940 bytes, headed "as on 17-Nov-2026". Columns: ISIN, fund name, fund currency, NAV value, NAV date, AUM (USD mm), performance YTD/1Y/3Y/5Y, dividend yield and frequency, plus category sections (Sukuk, Equity, ETFs, Multi-asset). 19 rows matched the ISIN pattern in text extraction. Four have `AEDFX...` ISINs, which are UAE-domiciled funds (e.g. `AEDFXA57C014 FRANKLIN GLOBAL SUKUK A (M DIS) USD [UAE] USD 9.22 13-Nov-26 AUM 9`; `AEDFXA76C113 ASB STATE STREET GLOBAL EQUITY FUND A USD ACC USD 120.33 12-Nov-26`). The disclaimer says prices are "indication levels subject to change". It is weekly or daily, free and no-login, but a distributor shelf (a few dozen funds, many foreign UCITS). Classify as UNOFFICIAL-distributor (official to the bank, not to a regulator).
- Manager sites: Emirates NBD Asset Management / Emirates Islamic (e.g. `salama.ae` and `watania.ae` PDF fact sheets for Emirates Islamic Money Market Fund, Emirates Global Sukuk Fund, Emirates India Equity Fund). A search result shows NAV per share 12.7781 for the A USD Acc class as of 30.09.2025 and daily dealing frequency for a Jersey fund; Luxembourg SICAV classes appear on `finanzen.ch` (UNOFFICIAL aggregator). Daily NAV pages for UAE-domiciled funds on ADCB, FAB, Mashreq and Franklin Templeton Gulf were not confirmed. — [Emirates Islamic MMF PDF](https://salama.ae/wp-content/uploads/2025/12/Emirates-Islamic-Money-Market-Fund.pdf)
- Central Bank of the UAE: no fund-level data found (aggregate only; not probed).
- GCC cross-border lists: no official GCC-wide fund distribution list found.
- NAV disclosure rule: the SCA's 2023 Investment Funds regulation (Resolution 01/Chairman of 2023) has a "NAV assessment & frequency" section, but no search result confirmed a central NAV publication requirement or platform. — [Al Tamimi](https://tamimi.com/news/securities-commodities-authority-sca-introduces-new-fund-regime)

### Inferences
- UAE-domiciled retail funds are few (tens). The practical route is: CMA/DFSA/FSRA registers for the master list, exchange pages for listed ETFs/REITs (ISIN, ticker), and manager NAV pages/PDF fact sheets for NAV.
- Cloudflare blocks (DFSA, ADX, ADGM web register) mean those sources need browser-based access or a formal data request, not scripted GETs.

### Gaps
- CMA local and foreign fund tables: no confirmed export or API; the direct POST was refused (CSRF, Origin).
- DFSA register, ADX and DFM ETF lists, ADGM FSRA fund register web UI: blocked or not located.
- Bayanat fund dataset: not confirmed.
- Daily NAV pages for ADCB, FAB, Mashreq, Franklin Templeton Gulf: not confirmed.

---

## Q6. UAE: field-by-field matrix and connector design

### Takeaway
UAE can realistically deliver fund master (name, manager, offering type, passport status) from regulators and a handful of NAV/ISIN/AUM rows from distributor and manager publications; holdings, fees, risk, benchmark and history are essentially unavailable from official feeds.

### Cited Findings (matrix)
| Field | Best source | Status |
|---|---|---|
| Fund master list | CMA open-data page (name, offering type; web table); ADGM passported funds PDF | VERIFIED (page and PDF); CMA bulk access UNVERIFIED |
| Manager | ADGM passported PDF (manager name and address) | VERIFIED |
| NAV (current) | DIB mutual fund list PDF (NAV, NAV date, ISIN); manager fact sheets | VERIFIED (distributor) |
| NAV history | none found | gap |
| ISIN | DIB list (incl. `AEDFX...` UAE ISINs); Nasdaq Dubai is ISIN issuer for its listings | VERIFIED (DIB) |
| Currency | DIB list `Fund Currency` | VERIFIED |
| Net assets / AUM | DIB list (USD mm) | VERIFIED |
| Performance YTD/1/3/5Y, dividend yield/frequency | DIB list | VERIFIED |
| Category | DIB sections; CMA `Category` filter | partial |
| Fees, risk indicator, benchmark, holdings, administrator/custodian, inception, distributions history | fact sheet PDFs per fund | not machine-readable |
| Status | ADGM `Date Withdrawn`; CMA active register | partial |
| Share class | in fund names in DIB list | text only |

### Cited design
1. `ae_adgm_passported`: download the latest ADGM Register of Passported Funds PDF (URL carries an edition date; resolve via assets.adgm.com), parse into funds (name, manager, public/private, passport targets, withdrawn date).
2. `ae_cma_local_funds`: replace the placeholder only after the CMA confirms a supported export/API for `typeId 1036`; otherwise load manually from a browser-exported list. Capture `offering_type`.
3. `ae_dib_fund_list`: weekly parse of the DIB PDF with pdftotext -layout; fields ISIN, name, currency, NAV, NAV date, AUM, performance, yield. Label `source_tier=distributor_official`, not regulator. Rate: one file per run.
4. Optional manager adapters (Emirates NBD AM fact-sheet PDFs) once a stable URL pattern is verified.
5. ADX/DFM/Nasdaq Dubai ETF lists: add only after confirming non-blocked access or a data feed agreement.
6. Maintain tests that the AE-prefixed ISINs map to `country_code=AE` and foreign UCITS rows in the DIB list stay `domicile` by ISIN prefix (LU, IE, GB).

### Inferences
- Expect low double-digit to a few dozen AE-domiciled funds with NAV, against 0 now. The DIB list also adds foreign funds sold in the UAE, which belong to LU/IE/GB domiciles.

### Gaps
- No central UAE NAV platform found; coverage estimate depends on how many manager sites publish a parsable daily NAV.
- Reuse terms for all UAE sources were not reviewed.
