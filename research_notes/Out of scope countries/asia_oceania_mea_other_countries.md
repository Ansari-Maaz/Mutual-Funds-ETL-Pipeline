> Moved from 'asia_oceania_mea.md' on 2026-11-18: these countries are outside the 24-country scope (US CA MX GB DE FR IT CH NL DK SE JP CN KR AU SG HK TW RU BR + LU IE AE ZA). Kept verbatim for possible later expansion.

# Asia/Oceania/MEA outside scope: IN TH PK MY NZ IL SA EG NG ID and others

## 1. India (AMFI/SEBI/AMC) - the biggest win

### Takeaway
India is by far the best target: AMFI publishes a free, keyless, bulk daily NAV file with scheme code + ISINs for roughly all AMFI-registered schemes (NAVAll.txt, 1.5 MB), plus a date-range historical NAV endpoint, monthly AUM, scheme details and SEBI-mandated AMC portfolio files. NEW (not integrated).

### Cited Findings
- NAVAll.txt (302-redirects www.amfiindia.com/spages/NAVAll.txt to portal.amfiindia.com/spages/NAVAll.txt). Semicolon-delimited, header: `Scheme Code;ISIN Div Payout/ ISIN Growth;ISIN Div Reinvestment;Scheme Name;Plan;Option;Net Asset Value;Date`. Date format DD-Mon-YYYY (e.g. 17-Nov-2026, i.e. current). Sections: blank-line-separated category headings ("Open Ended Schemes(Debt Scheme - Liquid Fund)") then AMC name lines then scheme rows; missing ISIN = "-". Sample: `135762;INF846K01WO1;-;Axis Children's Fund;Direct Plan;Growth Option;31.2107;17-Nov-2026`. File is ~1.53M characters. No key. [VERIFIED] https://portal.amfiindia.com/spages/NAVAll.txt
  - Parsing: category heading and AMC lines give category (SEBI category, e.g. "Debt Scheme - Liquid Fund") and AMC/manager; Plan (Direct/Regular) and Option (Growth/IDCW) given. Join key: AMFI Scheme Code (stable integer) + ISIN (INF...). Approx 40-45k rows incl. all plan/option variants (estimate, PRIOR; not counted).
- NAVOpen.txt exists with same columns (open-ended schemes) [VERIFIED listed] https://portal.amfiindia.com/spages/NAVOpen.txt. Also closed-ended / interval equivalents (NAVClose.txt, NAVInterval.txt) [PRIOR].
- AMFI NAV history web page: views = NAV as on a date, all NAVs for a date, historical NAV for a period, high/low NAV, two-date comparison; "maximum 90 days per request" for historical download [VERIFIED] https://www.amfiindia.com/net-asset-value/nav-history ; https://www.amfiindia.com/net-asset-value/nav-download . AMFI says old-format download discontinued in favour of new format on the new site (new SIF section also exists: /sif/latest-nav/nav-download) [VERIFIED via search].
- Historical endpoint pattern used by third-party libs: `https://portal.amfiindia.com/DownloadNAVHistoryReport_Po.aspx?mf=<amcid>&tp=1&frmdt=01-Jan-2026&todt=31-Mar-2026` returning the same semicolon format with extra columns (Repurchase/Sale price). NOT confirmed as official docs and may have moved with the site redesign - must HTTP-test. History depth reported back to ~3 Apr 2006 [freefincal tool], https://freefincal.com/excel-mutual-fund-nav-history-downloader/ ; community archive of historical data: https://github.com/captn3m0/historical-mf-data (UNOFFICIAL). Unofficial JSON mirror api.mfapi.in (UNOFFICIAL; do not use as primary).
- AMFI average AUM by fund house/scheme category: AUMReport_Frm_Po.aspx?rpt=fwise [VERIFIED listed] https://portal.amfiindia.com/AUMReport_Frm_Po.aspx?rpt=fwise ; AMFI "other data" hub with scheme details, scheme-wise disclosure (SEBI circular 25 Aug 2022), AUM by category/city/folio [VERIFIED] https://www.amfiindia.com/otherdata , https://www.amfiindia.com/otherdata/scheme-details , https://www.amfiindia.com/otherdata/scheme-wise-disclosure . AMFI disclaims accuracy/timeliness (terms).
- Scheme-level average AUM (AAUM) per scheme: AMFI publishes quarterly/monthly "Average AUM scheme-wise" (Excel/HTML) [PRIOR - verify exact URL under /research-information or AUMReport pages].
- TER: SEBI-mandated per-scheme TER disclosure on AMFI "TER of Mutual Fund schemes" page and on each AMC site daily [PRIOR]; the only compiled file found is UNOFFICIAL Hugging Face dataset https://huggingface.co/datasets/Na-Rajan/IndianMutualFundsTER. Did not locate an official AMFI TER file URL.
- Portfolio holdings: SEBI requires each AMC to publish monthly portfolio (by 10th, per-scheme Excel/PDF on AMC site) and half-yearly; scheme-wise disclosure page at AMFI links to them [PRIOR + AMFI page VERIFIED to exist]. No single bulk file; ~45 AMCs x Excel layout varies (scraping-only). Riskometer: shown in AMC factsheets/SID, and AMFI/SEBI category list; no bulk feed found [PRIOR].
- SEBI: category/sub-category definitions and mutual fund registry at https://www.sebi.gov.in/curation/mutual_funds_and_rtas.html ; monthly MF statistics https://www.sebi.gov.in/statistics/mutual-fund/objective/apr-aug-2026.html [VERIFIED listed]. SEBI Master Circular for MFs March 2026 defines ISIN field as 12 chars [VERIFIED].
- NSE/BSE: NSE/BSE list ETFs (ISIN+iNAV/NAV) and BSE StAR MF/NSE NMF II publish scheme masters but require member login [PRIOR]; ETF NAVs also in AMFI NAVAll. Exchange ETF bhavcopy is free (equity bhavcopy).
- Terms: AMFI data is publicly viewable; no explicit open licence; commercial redistribution terms not found (Gap).

### Inferences
- NAVAll.txt alone gives id/ISIN/AMC/category/plan/option/NAV/date for the whole industry in one GET; daily snapshot builds history forward. Combine with the historical endpoint (90-day windows, per AMC) for back-fill 2006->.
- Missing from official bulk: manager, inception date, riskometer, benchmark, TER (partial), holdings -> need AMC scraping (e.g. SEBI scheme-wise disclosure) or accept gaps. Twelve Data overlap: name, ISIN, currency (INR constant), NAV, category, AMC/family, plan type.

### Gaps
- Exact current URL and params of historical NAV endpoint after AMFI site redesign; official TER and scheme-level AAUM file URLs; licence terms.

## 2. Thailand

### Takeaway
SEC Thailand has an official OpenAPI (V2, api.sec.or.th) with a free API key and a broad Fund factsheet API (fees, performance, statistics, asset allocation, top-5 holdings, daily NAV). Strong second target; NEW.

### Cited Findings
- SEC Open Data portal has a Mutual Fund section with "Open API: Fund Factsheet" [VERIFIED via search listing] https://secopendata.sec.or.th/Fund/MF_IPO (fetch returned 403 from this host).
- Community Go client documents V2 API at api.sec.or.th (legacy V1 api-portal.sec.or.th obsolete), 21 Fund endpoints incl. /v2/fund/factsheet/{fees,performance,statistics,asset-allocation,top5-holdings,urls} and /v2/fund/daily-info/nav; free developer account -> primary+secondary key; HTTP 204 = not found; 429 rate limits; inconsistent datetime formats. UNOFFICIAL client documenting official API: https://pkg.go.dev/github.com/jwitmann/sec-go
- Fund count ~ 1,500+ mutual funds, incl. ~ plus ~ many classes [PRIOR, estimate]. Data in Thai and English fields. AIMC (aimc.or.th) publishes industry stats and fund NAVs web pages; scraping-only [PRIOR].
- Join key: SEC proj_id (project id) + class abbreviation; ISIN not always present [PRIOR].

### Gaps
- Official endpoint docs (403), history depth of daily NAV, rate quota, licence.

## 3. Pakistan (MUFAP)

### Takeaway
MUFAP is the single official aggregator: NAV/returns tables for open-end, dedicated equity, pension, ETF funds (~250-300 funds/plans), Excel export, no documented API. Scrape/Excel only; NEW.

### Cited Findings
- NAV Returns Performance Summary pages with tabs (open-end, pension, etc.), NAV and validity date, returns; Excel 2003/2007 export offered [VERIFIED] https://www.mufap.com.pk/nav_returns_performance.php?tab=05& ; https://mufap.com.pk/nav_returns_performance.php?tab=04
- Third-party: Apify scrapers of MUFAP (UNOFFICIAL) https://apify.com/bakos_bence/mufap-mutual-fund-navs ; Capitalstake commercial API (UNOFFICIAL) https://capitalstake.com/docs/rest/api/mutual-funds/intro ; psxtactics.vercel.app (UNOFFICIAL).
### Gaps
- Historical depth, ToS, whether there's a JSON endpoint behind the page.

## 4. Malaysia

### Takeaway
FIMM publishes daily unit prices per fund online; SC publishes only aggregate stats and a data.gov.my list of launched unit trusts. HTML-scrape; NEW.

### Cited Findings
- FIMM daily prices (by management company; dated NAV per unit) https://www.fimm.com.my/report/dailyprice.php ; https://fimm.com.my/report/dailypricefms2.php [VERIFIED; no download option confirmed]
- SC industry NAV RM546.08bn at end 2024 (aggregate) https://www.bernama.com/en/news.php?id=2404272 ; SC "fund management products" analytics https://www.sc.com.my/analytics/fund-management-products ; data.gov.my "List of Launched Unit Trust Fund" (archive) https://archive.data.gov.my/data/dataset/list-of-launched-unit-trust-fund [VERIFIED listed]
- Bursa lists ETFs/closed-end (via bursamalaysia.com) [PRIOR].
### Gaps
- FIMM licence/bulk access; ~700-1,000 funds estimate unverified.

## 6. New Zealand

### Takeaway
Disclose Register (NZ Companies Office) is the official source for managed funds with fee, holdings and fund update data, but the API needs registration and approval; legacy Disclose Public API retired when the register was replaced on 23 Mar 2026. NEW.

### Cited Findings
- New Disclose REST API replaces SOAP; subscribe via business.govt.nz API portal after registering as Disclose user; subscription approved manually; sandbox not representative; some operations limited to 30-day date range [VERIFIED] https://portal.api.business.govt.nz/api/disclose-public ; https://disclose-register.companiesoffice.govt.nz/about-disclose/what-is-disclose/
- Managers must file quarterly fund updates and full portfolio holdings (XLSX/CSV or API) -> includes fees, returns, top holdings [VERIFIED] https://disclose-register.companiesoffice.govt.nz/help-centre/managed-fund-offers/filing-full-portfolio-holdings ; https://disclose-register.companiesoffice.govt.nz/help-centre/managed-fund-offers/filing-fund-updates
- No daily NAV (NZ unit prices are manager-published). ~ 600+ funds/ schemes estimate [PRIOR].
### Gaps
- Final REST schema, licence, bulk download.

## 7. Israel

### Takeaway
Rich data exists in Israel (ISA, TASE, Ministry of Finance gemelnet/pensyanet) but I could not verify official open-data endpoints this session. Funds are ISIN-identified (IL005...). NEW.

### Cited Findings
- ISA oversees mutual funds; funds must publish prices, prospectus, financials [VERIFIED] https://www.meitav.co.il/en/mutual_funds/features_to_know/
- TASE Data Hub: API-based access to TASE end-of-day and historical data (commercial) [VERIFIED, dated oddly] https://www.israelhayom.com/2020/09/25/tel-aviv-stock-exchange-offering-streamlined-access/ ; third-party claims api.tase.co.il public API is geofenced to Israel (UNOFFICIAL claim) https://apify.com/parseforge/tase-tel-aviv-listings-scraper
- Gemel Net / Pensya Net (Capital Market Authority, MoF): data.gov.il CKAN datasets with monthly yields/assets per provident/pension fund [PRIOR; search could not confirm] — this is the best lead for pension/provident (not mutual funds). Hebrew-only fields common.
- Third-party vendors (Twelve Data, EODHD) list TASE funds (UNOFFICIAL) https://twelvedata.com/markets/308802/etf/tase/mtf.f19
### Gaps
- Verify data.gov.il resource IDs, MAYA fund report endpoints, ISA fund directory, English availability.

## 8. Saudi Arabia

### Takeaway
Tadawul/Saudi Exchange fund screener and funds market watch give daily NAV per unit, manager, currency, Shari'ah flag, objective, expense ratio, total NAV, inception; web-only (dynamic pages), no official bulk API found. CMA gives aggregates. NEW.

### Cited Findings
- Fund screener columns: name, manager, currency, Shari'ah, objective, NAV/unit, YTD %, valuation date, NAV, expense ratio [VERIFIED] https://www.tadawulgroup.sa/wps/portal/saudiexchange/newsandreports/fund-screener?locale=en ; markets watch https://www.saudiexchange.sa/wps/portal/saudiexchange/ourmarkets/funds-market-watch/etfs?locale=en ; CMA fund info https://cma.gov.sa/en/Awareness/IFs/Pages/IFInformation.aspx ; CMA statistical bulletin (aggregate) https://cma.gov.sa/en/Market/Reports/Documents/Statistical_Bulletin_Q2_2026_en.pdf
- KAPSARC "Investment Funds (Open/Close)" dataset with API, CMA-sourced from 2006, update frequency unknown [VERIFIED] https://opennetzero.org/king-abdullah-petroleum-studies-and-research-center-kapsarc/investment-funds-open-close
- Cached screener pages seen with 2024-25 valuation dates (staleness risk). Count ~ 300-500 public funds (PRIOR estimate).
### Gaps
- Underlying JSON endpoint of screener, ToS for scraping.

## 9. Egypt

### Takeaway
FRA has fund counts/aggregates (224 funds, EGP 471bn NAV) and a 2025 resolution (no. 236) to publish unit prices via the "I Invest" platform; no verified public feed yet. Managers publish daily NAV. NEW.

### Cited Findings
- FRA: 224 funds, net assets EGP 471bn [VERIFIED] https://fra.gov.eg/en/?p=24457659 ; Q1 2026 first investment funds performance report https://fra.gov.eg/en/?p=22740505
- Resolution 236/2025 for real-time unit prices via I Invest [VERIFIED] https://fra.gov.eg/en/?p=19242024
- Prices compiled by Mubasher (UNOFFICIAL) https://english.mubasher.info/news/4530305/ ; manager example https://fabmisr.com.eg/en/personal-banking/investments-funds/money-market-fund
### Gaps
- Whether I Invest feed live/public; EGX fund NAVs.

## 10. Nigeria

### Takeaway
SEC Nigeria publishes weekly and monthly NAV/unit price files for registered CIS by year (document downloads); NEW, scrape files. Total CIS NAV N3.84tn Q4 2024.

### Cited Findings
- Weekly CIS NAV pages per year 2011-2025 https://sec.gov.ng/for-operators/keep-track-of-capital-market-data/net-asset-value-data/weekly-net-asset-value-for-cis/2025-weekly-nav-for-cis/ ; monthly https://sec.gov.ng/for-operators/keep-track-of-capital-market-data/net-asset-value-data/monthly-net-asset-value-for-collective-investment-schemes/2025-monthly-nav-for-cis/ ; aggregate https://ngxgroup.com/ngx-firms-declared-n1-1tn-dividends-raised-n3-68tn-in-2024-sec/
- File format (PDF vs Excel) not inspected. FMDQ link unconfirmed. ~ 100-150 funds (PRIOR estimate).

## 12. Indonesia, Philippines, Vietnam, Gulf, East/North Africa, others

- Indonesia: OJK monthly statistics PDFs (aggregate, incl. Syariah) [VERIFIED] https://www.ojk.go.id/id/kanal/syariah/data-dan-statistik/reksa-dana-syariah/ ; per-fund daily NAB/NAV from OJK is exposed via the e-reporting/"Pasar Modal" pages and KSEI/ Bareksa (Bareksa UNOFFICIAL) - no verified bulk. Indonesian only. Reported NAB Rp656.87tn Jun 2026 vs Rp652.9tn (sources conflict).
- Philippines (SEC, PIFA), Vietnam (SSC, VSD), Sri Lanka (SEC SL / Unit Trust Association), Bangladesh (BSEC; DSE mutual fund prices), Qatar, Kuwait (CMA), Bahrain (CBB), Oman (CMA), Jordan, Morocco (AMMC/ASFIM publishes weekly VL (valeur liquidative) per OPCVM, ~ 600+ OPCVM, French) , Tunisia (CMF/ Tunisie Clearing), Kenya (CMA quarterly CIS reports; managers publish daily), Ghana, Botswana, Mauritius (FSC), UAE (SCA/DFSA/ADGM public registers): NOT researched this session (tool budget); all PRIOR leads only. Morocco ASFIM weekly VL files and Bangladesh DSE are the most likely bulk-ish ones. UAE: SCA fund list is a register (no NAV); DFSA/ADGM public registers list funds without NAV.
- Dubai/Abu Dhabi: DFM/ADX list ETFs; ADX/DFM data is exchange-licensed.

## Ranking (funds x bulk official availability) - my assessment
1. India (~ thousands of schemes; full bulk NAV+ISIN+category free) - top win
2. Thailand (~1.5k+ funds; official keyed API incl. NAV, fees, holdings)
3. Pakistan (~250-300 funds; Excel export)
4. Nigeria (weekly/monthly files; ~100+)
5. Malaysia (daily web prices; ~700+?)
6. Saudi (daily web screener)
7. New Zealand (approved-key REST API; holdings+fees, no daily NAV)
8. Egypt, Israel, Indonesia, Morocco (leads; unverified bulk)
9. South Africa/Australia: already in DB; no free official bulk NAV (SA 1,945 stays name-only unless commercial source/ manager scraping).
Flags: scraping-only = MUFAP (Excel export), FIMM, Tadawul, FRA, AMC holdings; API key = Thailand SEC (free), NZ Disclose (approval); English OK = India, Thailand (partial), Malaysia, Saudi (EN), NZ, Nigeria, Egypt (EN reports); local-language only likely = Indonesia, Israel (Hebrew), Morocco (French), Vietnam.

## Tiny-industry countries
Not verified here (Gap). Likely regulator register only: Botswana, Ghana, Mauritius (FSC lists CIS/GBC funds), Bahrain (CBB register, many funds domiciled), Oman, Jordan, Tunisia, Qatar (QFMA), Kuwait (CMA register of funds).
