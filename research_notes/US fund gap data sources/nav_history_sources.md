# US open-end mutual fund (and ETF) daily NAV history: official and licensed sources

Research date: 2026-11-17. Not legal advice. Many vendor pages could not be fully fetched (403/404/compressed PDF); items resting on search snippets or secondary sources are marked. Uncited items are in Inferences or Gaps only.

## 1. Official / regulator / NSCC / Nasdaq sources

### Takeaway
No regulator publishes a daily NAV series. The institutional origin of US mutual fund daily NAVs is the Nasdaq Fund Network (NFN, formerly MFQS), a licensed feed that requires a Nasdaq distributor agreement. Its fee schedule and redistribution terms were not retrievable.

### Cited Findings
- SEC website content is "public information and may be copied or further distributed by users of the web site without the SEC's permission"; the SEC asks for attribution and bars use of its seal/logos and of "SEC"/EDGAR names in business names or domains. This governs reuse of EDGAR filings (N-CSR, N-PORT etc.), not NAV feeds. — [SEC privacy/website information](https://www.sec.gov/about/privacy-information)
- SEC adopted amendments to Forms N-PORT and N-CEN on 2024-08-28 (IC-35308, published 2024-09-11), requiring more frequent monthly portfolio holdings reporting. A 2026 proposal on N-PORT reporting (IC-35962, File S7-2026-05) also exists; contents not reviewed. — [Federal Register 2024-19819](https://www.govinfo.gov/content/pkg/FR-2024-09-11/html/2024-19819.htm); [2026 proposal](https://public-inspection.federalregister.gov/2026-03460.pdf)
- N-CSR/N-CSRS annual and semi-annual shareholder reports include a "Financial Highlights" section (example: Invesco N-CSRS). I could not retrieve the form instructions, so what is exactly required (per-share NAV at period end, per-class) is unverified here. — [Invesco N-CSRS listing](https://insurancenewsnet.com/oarticle/semi-annual-report-by-investment-company-form-n-csrs-5)
- Nasdaq Fund Network (NFN), formerly Mutual Fund Quotation Service (MFQS), is Nasdaq's mutual fund pricing service. Nasdaq's page directs users to a Fund Data Price List for pricing and to Nasdaq Global Data Products for distributor agreements. Billing line +1 800 955 3898. — [Nasdaq Trader NFN](https://nasdaqtrader.com/Trader.aspx?id=MFQS) (via search snippet; direct fetch returned 404)
- NFN Data Policy (modified 2024-05-09) has sections: Pricing & Data Clarifications; Terminology & Unit of Count; "Delayed, End of Day and Historical Data"; NFN Identifier Requirements & Restrictions; License Restrictions; Use of Third-Party Data. Body text was not readable (compressed PDF saved at /home/asim/.claude/projects/-media-asim-4-TB-1-MFAPI-MF-ETL-PIPELINE/ba8d66db-0ce2-4266-a70d-81ac8b026ce8/tool-results/webfetch-1794857711836-ljy26q.pdf). Snippet: External Distributor Fee includes the Internal Distributor Fee; each feed recipient must be separately approved. — [NFN Data Policy](https://www.nasdaqtrader.com/content/AdministrationSupport/Policy/nasdaqfundnetworkpolicy.pdf)
- NFN Data Service is delivered via Nasdaq Data Link Streaming API per a 2024 spec; dxFeed resells NFN data (pricing not found). — [dxFeed NFN](https://www.dxfeed.com/consolidated-data-feed/nasdaq-mfds); [NFNDS spec](https://m.nasdaqtrader.com/content/technicalsupport/specifications/dataproducts/NFNDS_NCDS.pdf)
- Fund-side: funds/families list on NFN under a Fund List Agreement; Nasdaq publishes listing standards. — [MFQS fund list agreement](https://www.nasdaqtrader.com/content/administrationsupport/agreementsdata/mfqs_fundlist_agreement_redlined_v18.pdf); [listing standards](https://m.nasdaqtrader.com/content/AdministrationSupport/AgreementsData/mfqslistingstandards.pdf)
- Xignite's NAVs API states US NAV data is sourced from NASDAQ NFN, with history back to 1994, identifiers incl. ticker/CIK/CUSIP/ISIN. — [Xignite blog](https://www.xignite.com/blog/access-any-fund-nav-from-a-single-xignite-api) (snippet)

### Inferences
- EDGAR gives only periodic snapshots (N-CSR financial highlights: period-end NAV per share; N-PORT: fund-level net assets monthly; N-MFP is money-market funds only). Therefore EDGAR can validate or anchor NAVs but cannot supply a complete daily series. (Inference from form purposes; not verified from form text in this research.)
- NSCC Fund/SERV is a transaction-processing network; I found no evidence it offers a public NAV subscription. NFN is the practical licensed price source. Direct NFN licensing probably carries per-user/per-distributor fees and redistribution restrictions; since Xignite resells it, a reseller route likely exists.

### Gaps
- NFN fee schedule, distributor-agreement text, and the historical-data rules (section 4 of policy) were unreadable. Contact Nasdaq Global Data Products or extract the saved PDF locally (pdftotext) to read them.
- NSCC Fund/SERV subscription eligibility and cost: not found.
- Exact N-CSR/N-PORT field requirements: not retrieved.

## 2. Fund issuer sites

### Takeaway
Issuer sites publish NAV history in the web UI (some with CSV/XLSX export), but terms typically restrict automated access and commercial reuse. Only partial evidence gathered; per-family exports were not tested.

### Cited Findings
- Vanguard US terms (2018 PDF version) bar devices/software providing repeated automated access unless Vanguard authorizes it in writing; current page not retrieved in full. Vanguard UK terms bar repeated automated access other than what Vanguard makes generally available. Vanguard Ireland grants a limited, revocable, non-commercial personal-use licence. — [Vanguard US T&C (PDF)](https://investor.vanguard.com/ts/pdf/terms_and_conditions.pdf); [Vanguard UK](https://www.vanguard.co.uk/professional/terms-and-conditions); [Vanguard IE/NL](https://nl.vanguard/professional/terms-and-conditions) (search snippets)

### Inferences
- Other large families (Fidelity, Schwab, T. Rowe Price, Capital Group, BlackRock/iShares, SSGA, Invesco, PIMCO, JPMorgan, Dodge & Cox) very likely have similar personal/non-commercial terms. This is unverified; I did not fetch their terms.
- A commercial API sourcing from issuer sites would need written permission or per-issuer agreements. Issuers do routinely supply NAVs to NFN, which is why NFN is the aggregated route.

### Gaps
- No per-issuer terms, endpoints, or CSV/JSON/XLSX availability verified for the listed families. This question is largely unanswered.

## 3. Free/low-cost quote sources: terms and fund coverage

### Takeaway
None of the free sources grants commercial redistribution by default. Yahoo is unofficial and personal-use only; Tiingo, EODHD, FMP, Twelve Data have paid redistribution routes requiring separate agreements.

### Cited Findings
- Yahoo Finance: yfinance README says the tool is for personal/research/educational use; Apache licence covers only the code, not the data; users are pointed to Yahoo's terms. Yahoo's developer terms (as quoted secondhand) bar deriving income from its APIs without prior written permission. One vendor claims Yahoo discontinued its official finance API (vendor claim, unconfirmed). — [yfinance README](https://cdn.jsdelivr.net/gh/ranaroussi/yfinance@main/README.md); [Yahoo API T&C](https://legal.yahoo.com/us/en/yahoo/terms/product-atos/apitnc/index.html); [Intrinio blog](https://intrinio.com/blog/yahoo-finance-api-replacement)
- Tiingo: Starter $0, Power $30/mo, Internal Commercial $50/mo ($499/yr), Enterprise bespoke. Internal use means you may not "display or share the data with another person or organization"; redistribution handled by Tiingo Sales. Coverage listed: 60,848 ETFs and mutual funds; 30+ years price history. — [Tiingo pricing](https://tiingo.com/about/pricing)
- EODHD: mutual funds are treated like other symbols (volume zero); free plan personal use (20 calls/day, 1 year history); paid from $19.99/mo personal with full history; commercial/B2B pricing on a separate page not seen; no mutual-fund coverage count or history start given. — [EODHD docs](https://eodhd.com/financial-apis/api-for-historical-data-and-volumes)
- Twelve Data: claims over 10,000 US and 300,000 global mutual funds; sources are unnamed "trusted market providers"; NAV published once per business day after close; mutual fund data plans from $329/mo; lists "Redistribution and commercial usage" without detail. — [Twelve Data mutual funds](https://twelvedata.com/mutual-funds)
- FMP: terms require a specific agreement before displaying data in public apps/websites; Enterprise plan is the display/redistribution option; an older ToS version (2023-08-01) says customer may not use data for any Commercial Use (snippet truncated); mutual fund historical price endpoint exists (page for it marked legacy in one language version). — [FMP pricing](https://site.financialmodelingprep.com/pricing-plans?planType=commercial); [FMP ToS](https://site.financialmodelingprep.com/terms-of-service); [FMP public-use article](https://site.financialmodelingprep.com/insights/platform/can-you-use-fmp-data-in-a-public-app-website-or-client-dashboard)
- Xignite NAVs API: sold as an API with a trial; see section 1 for NFN sourcing. Intrinio markets mutual fund NAVs and historical prices (no source/pricing found). — [Xignite](https://xignite.com/mutual-funds-data/); [Intrinio blog](https://intrinio.com/blog/mutual-fund-data-enhancing-portfolio-optimization)

### Inferences
- Tiingo's and EODHD's mutual fund NAVs likely derive from NFN-type licensed feeds (not stated). Their personal/internal tiers explicitly exclude resale, so a commercial data API would need their enterprise/redistribution licences.
- Twelve Data's and FMP's redistribution rights for mutual fund data in particular are unconfirmed; vendors often exclude certain exchange/third-party data from redistribution grants.

### Gaps
- Not verified: Nasdaq.com API/Google Finance terms, Stooq terms and fund coverage, Alpha Vantage (terms PDF unreadable; premium/commercial licensing not confirmed), Polygon/Massive (rebranded; mutual fund KB article 404; the Massive-vs-yfinance page returned in search was not read), Tiingo/EODHD/Twelve Data enterprise price points.

## 4. Licensed institutional routes

### Takeaway
ICE, FactSet, LSEG, Morningstar, Bloomberg cover US mutual funds but pricing is by quote only; Xignite and Intrinio are the API-first options. Display vs. redistribution licence tiers exist, but specifics were not found.

### Cited Findings
- ICE Reference Data (Funds) lists mutual funds and ETFs across the USA, Europe, UK, Asia, with fund pricing data and NAV monitoring, delivered via ICE Connect, ICE Data API, ICE Data Files. — [ICE developer catalog](https://developer.ice.com/fixed-income-data-services/catalog/ice-reference-data-funds)
- ICE says it licenses data to quote vendors/redistributors via customizable packages; its exchange policy has a vendor-redistribution section with annual fees (not NAV-specific). — [ICE pricing and analytics](https://www.theice.com/market-data/pricing-and-analytics)
- ICE Global Index Feed lists daily ETP valuation data including NAV and shares outstanding (via dxFeed). — [dxFeed](https://dxfeed.com/market-data/indices/ice-global-index-feed)
- Xignite: US NAVs from NFN, history from 1994, global expansion to 300,000 NAVs in 74 countries; legacy XigniteFunds v1 exists. — [Xignite blog](https://www.xignite.com/blog/access-any-fund-nav-from-a-single-xignite-api)

### Inferences
- Standard market-data licence tiers (display, non-display/internal, redistribution) apply; commercial API resale generally needs the highest tier and often flow-through of the upstream (NFN/ICE) distributor fees.

### Gaps
- No public pricing found for ICE, FactSet, LSEG, Morningstar, Bloomberg, Intrinio, Xignite, Nasdaq Data Link. No documented US mutual fund coverage counts for FactSet/LSEG/Morningstar/Bloomberg. Not researched in this pass.

## 5. Competitor positioning (summary)
- Twelve Data: 10,000+ US funds, unnamed sources, $329/mo tier. EODHD: generic, no count. Tiingo: ~60.8k ETFs+MFs, 30+ yrs, no source disclosure. FMP: mutual fund historical endpoint, source undisclosed. Citations in section 3.

### Gaps
- Sourcing is undisclosed by all four; only Xignite names NFN.

## Practical options (inference)
1. Direct NFN licence from Nasdaq (full history terms unknown; read policy section 4/6 locally).
2. Licensed reseller (Xignite, dxFeed, Intrinio, ICE) with explicit API-redistribution rights.
3. Enterprise redistribution plan from Tiingo/EODHD/Twelve Data/FMP, confirmed in writing for mutual funds.
4. Use EDGAR N-CSR/N-PORT only for validation/anchoring, not as the series.
