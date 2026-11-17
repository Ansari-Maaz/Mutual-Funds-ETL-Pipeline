# Official fund-data sources: United States, Canada, Mexico (as of 2026-11-18)

Legend: VERIFIED = fetched this session (sample shown). UNVERIFIED = from search/background; not fetched. UNOFFICIAL = labelled explicitly.
Method note: tests ran from the research host with curl. Many research tool calls were limited; the CNBV portal and several Canadian sites could not be opened (reasons below).

## United States

### Takeaway
The US pipeline already uses nearly every free SEC bulk set. The remaining ISIN/CUSIP, category, inception and no-ticker-NAV gaps are structural: no free official source exists for fund-class CUSIP/ISIN or Morningstar-style category. New official gains are small: N-CEN series LEI and exchange/ticker tables, N-PORT class monthly returns, RR benchmark/index text, ETF CUSIPs from the SEC 13(f) list, and a DERIVED taxonomy. ISIN via GLEIF was tested and returns nothing.

### Cited Findings
- Integrated sources (from docs/US_OFFICIAL_SOURCES.md and the connector registry): N-PORT bulk, N-MFP bulk, N-CEN bulk, RR (N-1A XBRL) profiles, N-CSR TSR, Vanguard/SSGA/Capital Group/GraniteShares issuer pages, Nasdaq fund-info quote. Why they under-deliver: N-PORT/N-CEN identifiers describe portfolio securities, not the fund's own class; N-CEN has no inception and annual NAV only; RR/TSR cover filers with tagged exhibits only; issuers block bots (Fidelity, Hancock, MassMutual, Invesco, Schwab, Direxion; per docs).
- SEC `company_tickers_mf.json` VERIFIED: rows are `[cik, "S000009184", "C000024954", "LACAX"]`, no CUSIP/ISIN. Reachable only with a declared identifying User-Agent (`Name email`): a Chrome browser UA got HTTP 403 (1,924-byte "Request Rate Threshold Exceeded" page) and tripped the rate limit for the whole host for several minutes. Rate limit is 10 requests/second; use a descriptive UA. — [SEC](https://www.sec.gov/files/company_tickers_mf.json)
- `data.sec.gov/submissions/CIK##########.json` VERIFIED (returned name, sic, tickers[], lei, fiscalYearEnd) and `data.sec.gov/api/xbrl/frames/...` VERIFIED (819 KB JSON). `company_tickers_exchange.json` VERIFIED (`[cik,name,ticker,exchange]`, operating companies/ETFs). — [data.sec.gov](https://data.sec.gov/submissions/CIK0000102909.json)
- N-CEN bulk 2026q3 VERIFIED: URL `https://www.sec.gov/files/dera/data/form-n-cen-data-sets/2026q3_ncen.zip` (5.9 MB; 2018q3..2026q3 listed). Tables present include FUND_REPORTED_INFO (2,330 rows this quarter), SHARES_OUTSTANDING (`FUND_ID, CLASS_NAME, CLASS_ID, TICKER`, 4,707 rows), SECURITY_EXCHANGE (`FUND_EXCHANGE, FUND_TICKER_SYMBOL`), ETF, REGISTRANT_REPORTING_SERIES, CUSTODIAN, TRANSFER_AGENT, PRICING_SERVICE, SHAREHOLDER_SERVICING_AGENT, AUTHORIZED_PARTICIPANT, SECURITY_LENDING, DIRECTOR, REGISTRANT_WEBSITE. FUND_REPORTED_INFO has `LEI`, `IS_ETF/IS_INDEX/IS_FUND_OF_FUND/IS_TARGET_DATE/IS_MONEY_MARKET`, `MONTHLY_AVG_NET_ASSETS`, `MANAGEMENT_FEE`, `NET_OPERATING_EXPENSES`, `NAV_PER_SHARE`, `MARKET_PRICE_PER_SHARE`, tracking-difference columns. Series LEI is therefore available for ~2,270 series in one quarter (VERIFIED count of non-empty LEI). — [SEC N-CEN data sets](https://www.sec.gov/data-research/sec-markets-data/form-n-cen-data-sets)
- GLEIF ISIN-to-LEI file VERIFIED: latest `isin-lei-20261117T081511.zip` (33 MB zip, 322 MB CSV `LEI,ISIN`, free, daily) via `https://mapping.gleif.org/api/v2/isin-lei/latest`. I joined the 2,270 N-CEN series LEIs against it: 0 matches. So GLEIF cannot supply US fund-class ISINs. GLEIF LEI API (`api.gleif.org/api/v1/lei-records?filter[lei]=...`) VERIFIED reachable (JSON, no key). — [GLEIF](https://mapping.gleif.org/api/v2/isin-lei/latest)
- Nasdaq public quote API VERIFIED: `https://api.nasdaq.com/api/quote/VFIAX/info?assetclass=mutualfunds` returned `lastSalePrice $685.18`, `lastTradeTimestamp Nov 17, 2026`, `exchange Nasdaq Fund Network`, currency USD (browser UA, no key). `https://api.nasdaq.com/api/screener/etf?download=true` VERIFIED: 5,520 rows (symbol, name, price, 1y %); no CUSIP/NAV/category. This is Nasdaq's unofficial-for-redistribution web API (NFN data is licensed by Nasdaq; UNOFFICIAL for reuse purposes, terms prohibit redistribution per prior notes). Prior audit: 0 of 60 no-NAV tickers returned a quote.
- Nasdaq Trader `mfundslist.txt` symbol directory: both HTTPS and FTP paths returned "Page Not Available" / FTP 550 (VERIFIED not found).
- SEC 13(f) securities list page: blocked by the SEC rate limit at test time (403); UNVERIFIED this session. Prior note says it carries CUSIPs for exchange-traded securities (includes ETFs); ETF CUSIP is therefore fillable for ETFs only. — [prior note isin_cusip_sources.md]
- Prior notes (not re-tested): DTCC Fund/SERV and Nasdaq NFN are licensed; CGS licenses CUSIP/ISIN (redistribution needs CGS licence); RR monthly sets now exist (page 2026-10-31) with new SCN file.
- Rule 6c-11 requires ETF daily holdings (with CUSIP or other identifier) on the issuer site; official but per-issuer. iShares Canada holdings URL returned an HTML page (271 KB) rather than CSV with a browser UA, so scripted CSV access is unconfirmed.

### Field matrix (US)
| Field | Best official source | Expected fill |
|---|---|---|
| Daily NAV ~14k gap | None free for classes without ticker; ticker classes: issuer pages; N-MFP (MMFs); N-CEN/TSR snapshot NAV | funds with NAV stays ~65-70%; +few % from issuer adapters |
| Holdings | N-PORT bulk (quarterly) + 6c-11 issuer files for ETFs | ~85% (new series lag) |
| Manager / administrator / custodian | N-CEN ADVISER/ADMIN/CUSTODIAN | 85% (already) |
| ISIN / CUSIP | ETFs: SEC 13(f) list CUSIP (UNVERIFIED); mutual funds: none free | ETFs ~90% of ETFs; mutual funds <5% |
| Ticker | company_tickers_mf.json + N-CEN SHARES_OUTSTANDING/SECURITY_EXCHANGE | ~76% (VIT/529/institutional have none) |
| Category | None official; DERIVED from N-CEN flags + N-PORT asset mix + name (target-date year, index) labelled derived | derived coverage ~90%, not Morningstar-equivalent |
| Inception | RR/TSR PerfInceptionDate (class), already; Vanguard directory | ~45% (RR-filers only) |
| Net assets | N-PORT NET_ASSETS, TSR AssetsNet | ~87% |
| Currency | USD | 100% |
| Fees/TER | RR NetExpensesOverAssets, TSR ExpenseRatioPct | ~70% |
| Risk indicator | none (SEC has no SRRI); N-CEN return stdev only for index funds | ~0 |
| Benchmark | RR broad-based index member labels / average annual returns table; N-CEN ETF tracking tables | ~60% of RR filers |
| Distributions | Not in bulk data; N-CSR financial statements (untagged); issuer sites | low |
| Status | N-CEN terminated, absence from latest N-PORT/N-CEN | derived |
| Share class | SCN / SHARES_OUTSTANDING CLASS_NAME | ~95% |
| Monthly total return per class | N-PORT bulk MONTHLY_TOTAL_RETURN table (class-keyed; from background, UNVERIFIED this session) | for chain-linked return index, not NAV |

### Connector design (US additions)
1. `sync-sec-ncen-bulk` extension: load SHARES_OUTSTANDING (class ticker), SECURITY_EXCHANGE, FUND_REPORTED_INFO.LEI into `funds.source_fund_id` mapping via SERIES_ID; store LEI in fund_profile_snapshots (kind `identifiers`).
2. 13(f) list parser (quarterly text/PDF): match ETF ticker/name to CUSIP; ISIN = `US` + CUSIP + check digit (compute; label derived from CUSIP, subject to CGS terms).
3. RR benchmark: from `txt.tsv`/`lab.tsv` for IndexAxis members, write `benchmark` snapshot.
4. Derived category: `fund_profile_snapshots` kind `classification`, label DERIVED; never write to `funds.category`.
5. HTTP: send `User-Agent: <Org> <contact email>`, at most 5 req/s.

### Inferences
- A free official US fund ISIN feed does not exist; the 0% GLEIF join confirms the identifier path is closed except ETF CUSIPs and fund-of-fund holdings.
- Gains for NAV are bounded: the 9.4k tickerless classes have no daily public NAV anywhere.

### Gaps
- 13(f) list, FINRA Fund Analyzer, N-PORT class return table not fetched this session (SEC rate-limited the host after browser-UA probes).
- Nasdaq NFN licence text not read.

## Canada

### Takeaway
No free official bulk fund-level NAV/holdings feed exists for Canada. SEDAR+ (CSA) blocks scripted access (403) and bulk data is a paid CSA data service. The workable route is manager-published files plus the IFIC/Fundata daily NAV view, and CIFSC categories via licensed vendors only.

### Cited Findings
- Integrated: `scotia_canada_daily_nav` (data/raw/canada Scotia XLSX, URL on transmissionmedia.ca; columns name, series, currency, date, NAV, ..., fund code). DB VERIFIED: 373 rows, `ticker` = Scotia fund code (e.g. BNS341), `isin` empty, category derived from name keywords, no holdings. Under-delivers because the workbook has only NAV and code (read connector code).
- SEDAR+ home page returned 403 Forbidden to curl with a browser UA (VERIFIED, with Transaction ID page). Manual check: open in a browser. CSA paid Data Delivery Service for SEDAR+ filings: [CSA](https://www.securities-administrators.ca/2025-02-sedar-updates) (not re-fetched).
- CIFSC site cifsc.org reachable (200, 85 KB) VERIFIED; no public category-by-fund download found; a search shows the committee was formed in 1998 by data providers and that category data access is via request forms; licence terms not found. — [CIFSC](https://www.cifsc.org/)
- IFIC site: TLS handshake failure from this host (VERIFIED failure). A search result states IFIC publishes daily NAVs for all Canadian funds on its site, data supplied by Fundata, by fund family (web view). — [Investment Executive](https://www.investmentexecutive.com/news/products/ific-offering-daily-navs-on-its-website) (UNVERIFIED; undated, may be outdated).
- BMO GAM site: connection failed (000) from this host. RBC GAM mutual funds list page fetched (200, 6.7 KB, "Mutual funds list"); contents are a shell; no CSV link verified. TMX ETF page URL 404 (path guessed wrong).
- iShares Canada holdings `.ajax?fileType=csv` URL returned an HTML page (271 KB), not CSV, so ETF CSV not confirmed.
- QuoteMedia sells CSV bulk fund data for US/Canada (UNOFFICIAL vendor). — [QuoteMedia](https://quotemedia.com/coverage/mutual_funds)

### Official sources not yet used (all UNVERIFIED unless noted)
SEDAR+ Fund Facts/Simplified Prospectus/MRFP per fund (manual, bot-blocked); provincial open data (OSC, AMF, BCSC) have no fund-level feeds I could confirm; IFIC statistics; CIFSC classification; Bank of Canada (no fund data; FX only); TMX and NEO/Cboe Canada ETF lists (exchange symbol lists); manager sites: RBC, TD, BMO, CIBC, Mackenzie, Fidelity, Manulife, Dynamic (daily prices pages; machine-readable format not confirmed).

### Field matrix (Canada)
| Field | Best source | Fill expectation |
|---|---|---|
| NAV | Manager daily files / IFIC-Fundata view | high for managers added; Scotia only today |
| Holdings | Fund Facts top 10 (SEDAR+/manager PDF); ETF CSV | top-10 only |
| Manager | Manager name from file/Fund Facts | ~100% |
| ISIN | Not in Scotia file; ETFs via exchange (TMX) | ETFs only |
| Ticker/code | Manager fund code (existing) | 100% for loaded |
| Category | CIFSC (licensed); Fund Facts category | low officially |
| Inception, fees (MER), risk rating (1-5 low to high), benchmark, status | Fund Facts PDF (SEDAR+ or manager) | high if PDF parsed |
| Distributions | manager pages | unconfirmed |

### Connector design (Canada)
Generic `manager_xlsx_csv` connector per manager (same pattern as Scotia: load file, key by manager fund code + series, currency from file). Add a Fund Facts PDF parser (MER, risk rating, inception, category) fed from manager URLs; SEDAR+ stays manual.

### Inferences
Growing past 373 funds requires per-manager endpoint discovery in a normal browser (devtools), not bulk APIs.

### Gaps
Real endpoints for RBC/TD/BMO/CIBC/Mackenzie/Fidelity/Manulife not confirmed; IFIC download format, CIFSC licence, CSA data pricing unknown.

## Mexico

### Takeaway
The "5,151 ISIN" count is false: DB VERIFIED shows `count(distinct isin)` = 1 across 5,151 MX rows (blank value), while `ticker` is the BMV pizarra+series (e.g. `IBUPLUS.BO-2`) and is real and unique. The official richer source is the CNBV "portafolioinfo" portal, which could not be opened from this host (TLS chain error), so it needs manual verification.

### Cited Findings
- Integrated: `bmv_mexico_funds` reads CSVs in data/raw/mexico (only `bmv_mexico_navs.csv` exists locally: columns `source_fund_id, valuation_date (dd/mm/yyyy), nav, currency, series, id_emision`; funds CSV missing in this checkout). Connector maps only name, manager (operator), category (from name), MXN currency; no holdings, administrator, inception. Catalog states ISIN is not present.
- BMV `https://www.bmv.com.mx/es/Grupo_BMV/BmvJsonOperadora` VERIFIED reachable (HTTP 200) but a bare GET returns an empty template; it needs POST/query parameters used by the page (not captured). BMV fondos page (200, 74 KB) loads `fondos.js`; endpoint parameters not extracted. — [BMV](https://www.bmv.com.mx/es/Grupo_BMV/fondos)
- CNBV statistics page (gob.mx) VERIFIED (200): links to `https://portafolioinfo.cnbv.gob.mx/Paginas/Reporte.aspx?s=52&t=2&st=0&ti=0&sti=0&n=0&tp=0` ("Consultar información de fondos de inversión"). Both curl and WebFetch failed to verify its TLS certificate (incomplete chain); I did not disable verification. Manual step: open it in a browser, inspect the report tabs and export buttons (likely per-report XLS/CSV; UNVERIFIED). — [CNBV](https://www.gob.mx/cnbv/acciones-y-programas/informacion-estadistica-fondos-de-inversion)
- `www.cnbv.gob.mx` also fails TLS verification; Condusef timed out (000) from this host; AMIB site (200, SPA shell), Valmer (200, public marketing page), PiP Latam (200, SPA shell) reachable but no free price dataset found. Prior note: Valmer/PiP are CNBV-authorised price vendors, public prices not confirmed; CUFI regulatory report specs (B-1422 prices, C-1331 valuation) are filings, not public bulk.
- Operator DICI/prospectus PDFs (Actinver, BBVA, Monex) contain benchmark, risk rating, fees, custodian (prior note, UNVERIFIED).

### Official sources not yet used
CNBV portafolioinfo (fund characteristics, portfolio composition, fees, returns, VaR); BMV per-fund composition downloads; operator sites; Banxico (no fund data); INDEVAL (ISIN assigner for Mexican securities, issuer ISINs; fund-series ISIN lookup not confirmed); Condusef (no confirmed fund data); AMIB (association; no free data confirmed).

### Field matrix (Mexico)
| Field | Best source | Fill |
|---|---|---|
| NAV | BMV JSON (existing) | ~67% of series (3,486 NAV funds) |
| Holdings | CNBV portafolioinfo / BMV composition file | unknown |
| Manager | BMV operator (existing) | 100% |
| Administrator/custodian/distributor | DICI/prospectus PDFs | high if parsed |
| ISIN | INDEVAL/BMV (not found); currently none | ~0 |
| Ticker | BMV pizarra.serie | 100% |
| Category | CNBV classification (RV/RD), currently from name | partial |
| Inception, fees, benchmark, risk | CNBV portal / DICI | unknown |

### Connector design (Mexico)
1. Fix catalog/DB: clear fake ISIN claim; store pizarra.serie as ticker (already) and `id_emision` as a secondary id.
2. Capture BMV `fondos.js` POST payloads in a browser; replace CSV with direct JSON pull.
3. After manual verification of portafolioinfo, add a connector paging reports by fund (administrator, inception, fees, composition) keyed on pizarra/serie.

### Inferences
MX gap-filling depends entirely on CNBV portafolioinfo; if it exposes per-fund exports, it covers holdings, fees, and operator in one place.

### Gaps
CNBV portal contents, BMV endpoint parameters, Valmer/PiP access terms, INDEVAL fund ISINs, Condusef: unverified.
