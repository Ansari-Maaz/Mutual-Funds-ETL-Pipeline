# Official fund-data sources: China, Hong Kong, Taiwan, Singapore

Method: all items marked VERIFIED were fetched with curl (Chrome UA) from this host on 2026-11-18 (host = project machine). UNVERIFIED = background knowledge or search snippet only. UNOFFICIAL is labelled. Host reachability matters: csrc.gov.cn, eid.csrc.gov.cn, sitca.org.tw (whole domain), fund.amac.org.cn all failed from this host (see per-item notes), so those need a different network/browser.

---

## 1. Hong Kong (HK)

### Takeaway
The HK loader bug is CONFIRMED and fixed by a different regex plus a trailing-marker allowance: 2,179 unique SFC funds (2,047 sub-funds + 132 standalone products; 393 umbrella/product codes) instead of 0 loaded. The SFC list is a pure public-offer register (name, CE ref, issuer, authorisation date, derivative flag, document links): no ISIN, currency, manager, NAV. Real NAV/ISIN data for HK must come from HKEX (ETPs, ISIN list) and MPFA (monthly MPF prices); non-ETF offshore UCITS get their NAV/ISIN/fees only from KFS PDFs per CE ref.

### Cited Findings
- Bug CONFIRMED: `app/connectors/hk_sfc_funds.py` `_load` uses `re.search(r"\(([A-Za-z0-9]+)\)", target)` (FIRST parenthetical) and a name-strip regex anchored at `$`. SFC cells look like `Name (USD) (BYK033)` / `Name (HK) (CE)`, so keys become `HK`, `LUX`, `USD`; `/media/asim/4_TB_1/MFAPI/MF ETL PIPELINE/reports/hong_kong_rejected_records.jsonl` has 154 lines, all `{"source_fund_id": "HK"|"LUX"|..., "reason": "duplicate CE number with conflicting names"}` (VERIFIED, local file).
- Second defect found this session (not in prior notes): some sub-funds end with a flag character after the CE ref, `(BYC779)#` (131 funds, ETF flag, SFC page footnote) and `(BOW810)+` (4 HSBC ICAV rows). A pure `\(([A-Z]{3}\d{3})\)\s*$` regex misses these (136 unmatched rows). Corrected regex tested on `data/raw/hong_kong/sfc_unit_trusts_mutual_funds.html` (sha256 03b851ce..., 1,063,819 bytes, 2,410 rows incl. header, every row has 6 cells; VERIFIED):
  `CE_RE = re.compile(r"\(([A-Z]{3}\d{3})\)\s*[#+^*]*\s*$")`; name = `CE_RE.sub("", cell).strip()`. Use `row[1]` (sub-fund) if non-empty else `row[0]` (product), and always `rx.search(...)` on the LAST group. Result: 2,047 unique sub-fund CE refs + 132 standalone products (rows whose sub-fund cell is empty and whose product has no sub-funds) = 2,179 unique funds; 261 umbrellas have sub-funds; 0 name conflicts per CE ref. 74 of the 2,179 are flagged derivative "Yes". Rows with empty sub-fund for umbrellas should NOT be emitted as funds (they are the umbrella header; use them as parent/umbrella name).
- SFC list columns (VERIFIED header): `Product (CE No.)`, `Sub-fund (CE No.)`, `Issuer`, `Authorisation date` (d/m/yyyy, e.g. 10/9/1997), `Documents` ("Offering Documents", "Waivers / Exemptions Granted"), `Derivative funds` (Yes/No/blank). NOT provided: ISIN, currency, manager (only issuer/management company), custodian, category, NAV, fees. Document links in the HTML: 2,291 `docType=OD` and 35 `docType=WV` per-CE links of form `searchProduct/getDocListNoDate.do?lang=EN&ceref=ADX434&docType=OD` — [SFC product list](https://apps.sfc.hk/productlistWeb/searchProduct/UTMF.do?lang=EN).
- HKEX List of Securities XLSX: https://www.hkex.com.hk/eng/services/trading/securities/securitieslists/ListOfSecurities.xlsx HTTP 200, 1.36 MB, "Updated as at 18/11/2026", 17,346 rows; header `Stock Code, Name of Securities, Category, Sub-Category, Board Lot, ISIN, Expiry Date, Subject to Stamp Duty, Shortsell Eligible, CAS/VCM Eligible, Admitted to CCASS, ..., Trading Currency, RMB Counter`; 423 rows "Exchange Traded Products / Exchange Traded Funds", 30 "Leveraged and Inverse", 21 "Investment Companies", 11 REITs. Sample: `02800 TRACKER FUND, HK2800008867, HKD, RMB counter 82800` (VERIFIED, openpyxl non-read-only needed; read_only mode mis-reports dimensions). Gives ISIN + stock code + currency for ~453 ETPs; no NAV/manager/fees.
- HKEX ETP page (https://www.hkex.com.hk/Market-Data/Securities-Prices/Exchange-Traded-Products?sc_lang=en) HTTP 200 (249 KB); front-end uses `/lhkexw/js/etps.js` and a client-side `xlsx.full.min.js` export (#etps_export) — data endpoint not found in the JS (UNVERIFIED which JSON feeds it); HKEX Data Marketplace is a paid channel — [HKEX](https://www.hkex.com.hk/Market-Data/Securities-Prices/Exchange-Traded-Products?sc_lang=en).
- MPFA monthly unit prices: page lists 13 month-end XLS links (Jul-25, Nov-25 ... Oct-26) under `https://www.mpfa.org.hk/en/-/media/files/information-centre/fund-information/monthly-fund-price/consolidated_list_for_{mon}_{yy}_read_only.xls`. Oct-26 file HTTP 200, 1,998,336 bytes, OLE2 .xls (needs xlrd), Sheet1 942 rows x 5 cols: header `Name of Approved Trustee | Name of Registered Scheme | Name of Constituent Fund | Unit Price (as at 30.10.2026, HK$) | Notes`, bilingual EN/zh headers; sample `AIA Company (Trustee) Limited | AIA MPF - Prime Value Choice | Age 65 Plus Fund | 1.2291 | 3a` (VERIFIED) — [MPFA page](https://www.mpfa.org.hk/en/info-centre/fund-information/monthly-fund-price/monthly-unit-prices-of-mpf-constituent-funds). Month-end only, no ISIN, no code. Note: MPF constituent funds are not in the SFC unit-trust list (MPF funds are approved by MPFA, not SFC-authorised UTs).
- MPFA other (UNVERIFIED): Fund Performance Platform, NAV of approved constituent funds data dictionary — [MPFA PDF](https://www.mpfa.org.hk/tc/-/media/files/information-centre/research-and-statistics/other-reports/dictionary/netassetvaluesofapprovedconstituentfunds-data-dictionary.pdf); eMPF platform daily prices (not tested; trustee-side yflife.com daily MPF history is UNOFFICIAL).
- SFC statistics page HTTP 200 (aggregate only) — [SFC](https://www.sfc.hk/en/Published-resources/Statistics?type=0); HKIFA site HTTP 200 (https://www.hkifa.org.hk/) — only industry statistics, no fund-level feed found (UNVERIFIED depth).

### Inferences
- Join key plan: SFC CE ref = primary key; link to ISIN via HKEX list only for ETPs (name fuzzy match + issuer; SFC "#"-flagged ETFs ~131 should map to the ~453 HKEX ETPs). Roughly 130 + some hundreds of the 2,179 will get ISIN; the other ~1,900 (offshore UCITS: Fidelity, AB, etc.) have no official bulk ISIN/NAV source in HK; their NAV/fee/risk lives only in KFS PDFs (per-fund, high effort) — LU/IE regulators (CSSF/CBI) or ISIN-registers would be the official source of NAV.
- Set `domicile_country` not HK for these (public-offer market); recommend a separate `market_country=HK` column or catalog-level market tagging, else they appear under "??".

### Gaps
- HKEX ETP NAV/daily and holdings endpoint; MPFA daily/eMPF feed; KFS field layout; SFC terms of use (no robots/ToS read); HKIFA fund statistics format.

---

## 2. China (mainland)

### Takeaway
Best verified official sources are the exchange (SSE/SZSE) JSON/XLSX endpoints, which are bulk, free and give fund lists with manager, custodian, tracked index, listing date, size and (SZSE) per-fund NAV history — covering ~1,455 listed funds (ETF/LOF). For the ~14,000 off-exchange public funds, NAV/holdings are only in CSRC e-disclosure (eid.csrc.gov.cn/fund), AMAC XBRL and manager sites; the CSRC host was unreachable here. UNOFFICIAL Tiantian remains the practical NAV fallback.

### Cited Findings
- Already integrated: CSRC public-fund product index XLSX (URL in `app/connectors/csrc.py`, "截至20260630"), read columns `序号, 基金代码, 基金简称, 设立日期` (header on row 2); connector loads only code and name (14,170 funds), drops 设立日期 (inception date) which IS in the file (VERIFIED from csrc.py header check). It under-delivers because it is only a product index: no manager, custodian, currency, ISIN, NAV. www.csrc.gov.cn itself timed out this session (connect timeout to 45.115.202.x; VERIFIED), so cached local XLSX is the only copy; reachability from the host is intermittent.
- SZSE fund list JSON: `https://www.szse.cn/api/report/ShowReport/data?SHOWTYPE=JSON&CATALOGID=1105&TABKEY=tab1&PAGENO=1` (Referer szse.cn) HTTP 200; 1,088 records, 20/page (55 pages); fields `基金代码, 基金简称, 基金类别(ETF/LOF..), 投资类别, 上市日期, 当前规模(万份), 基金管理人, 最新基金净值`. XLSX export: `https://www.szse.cn/api/report/ShowReport?SHOWTYPE=xlsx&CATALOGID=1105&TABKEY=tab1&random=0.5` HTTP 200, 65 KB (VERIFIED) — [SZSE fund list](http://fund.szse.cn/marketdata/fundslist/index.html).
- SZSE NAV history per fund: `.../ShowReport/data?SHOWTYPE=JSON&CATALOGID=1785_child&TABKEY=tab1&txtDm=158000` returns rows `{nav_date, fund_code, security_short_name, nav_per_share}` e.g. 2026-11-16 NAV 1.0482 (VERIFIED). Daily NAV with history, per fund; ~1,088 calls for all.
- SSE ETF list: `https://query.sse.com.cn/commonQuery.do?sqlId=COMMON_SSE_ZQPZ_ETFLB_L_NEW&isPagination=false` (Referer sse.com.cn) returns 367 ETFs: `FUND_ID, FUND_NAME, FUND_MANAGER, FUND_TYPE, ETF_CLASS, ETF_VERSION`. SSE fund master: `https://query.sse.com.cn/commonSoaQuery.do?sqlId=FUND_LIST&fundType=00&isPagination=true&pageHelp.pageSize=..&pageHelp.pageNo=..` returns `fundCode, fundAbbr, secNameFull, companyName (manager), fundManager (person), TRUSTEE_NAME (custodian), INDEX_NAME/INDEX_CODE (benchmark/tracked index), listingDate, subClass` — e.g. 510010 交银施罗德, custodian 中国农业银行 (VERIFIED). This answers manager + custodian + benchmark for SSE funds.
- AMAC: www.amac.org.cn HTTP 200 (378 KB); gs.amac.org.cn serves 私募基金公示 (PRIVATE funds; title "私募基金公示"), and its `/amac-infodisc/api/pof/fund` returns HTTP 500 for POST without browser session (VERIFIED). The public-fund registry (fund code, manager, custodian, establishment date, category) is NOT at gs.amac.org.cn (that is private funds); fund.amac.org.cn did not connect. AMAC now owns the XBRL templates for fund quarterly reports and NAV announcements (templates: quarterly report, NAV announcement, annual/semi-annual, contract-effective announcements, product summary; XBRL template tier moved to AMAC self-regulatory rules in the revised Disclosure Standard No. 2 effective 1 May 2026) — [CSRC/search summary](https://www.cs.com.cn/xwzx/hg/202603/t20260314_6541217.html).
- CSRC e-disclosure eid.csrc.gov.cn/fund: TLS handshake fails (`tlsv1 alert internal error`) with OpenSSL 3 even forced TLS1.2 (VERIFIED from this host; may be geo/WAF filter). Content (UNVERIFIED): per-fund periodic reports/NAV announcements, quarterly top-10 holdings, annual full holdings; XBRL presence consistent with AMAC templates above, bulk download not confirmed.
- ChinaClear https://www.chinaclear.cn/ HTTP 200 and CSI https://www.csindex.com.cn/ HTTP 200; neither has a verified fund-level NAV feed (ChinaClear publishes statistics; CSI publishes index data and index-fund lists) (UNVERIFIED depth).
- MRF (HK-China Mutual Recognition of Funds) lists are on SFC/CSRC sites; SFC list already includes the CN funds offered in HK (e.g. ABC-CA, Bosera standalone funds in the SFC file, VERIFIED in local HTML).

### Inferences
- Two-tier design: tier A (exchange funds, ~1.4k): SSE FUND_LIST + SZSE list/NAV give nearly all fields except ISIN, fees, holdings. Tier B (~12.7k OTC funds): CSRC index (code, name, inception) + per-manager/eid disclosures; manual or browser-session needed. UNOFFICIAL Tiantian (fund.eastmoney.com) / Sina / Howbuy for NAV history of Tier B, flagged "unofficial".
- Fund code 6-digit is the join key; share classes (A/C) have separate codes with same parent.

### Gaps
- eid.csrc.gov.cn, fund.amac.org.cn and www.csrc.gov.cn not reachable here: bulk format, XBRL download, rate limits and ToS unverified. SSE NAV/IOPV endpoint not identified. Currency (CNY mostly) not provided by CSRC xlsx.

---

## 3. Taiwan (TW)

### Takeaway
SITCA (whole sitca.org.tw) times out from this host, so the data.gov.tw daily NAV file is unreachable here, but exchange sources work: TWSE OpenAPI `t187ap47_L` (278 listed ETFs with manager, custodian, inception, index, fund ID) and TWSE `all_etf.txt` (ETF unit count, price, NAV estimate) and TPEx OpenAPI open-end-fund quotes. TDCC's Fundclear (offshore funds) has an API but queries require Google reCAPTCHA.

### Cited Findings
- data.gov.tw 11109: page HTTP 200 (525 KB) and references the file `https://www.sitca.org.tw/MemberK0000/F/03/nav.csv` (VERIFIED in HTML). The file URL and also `https://www.sitca.org.tw/` and `ROC/Industry/IN2105.aspx` all time out at 25-30 s with 0 bytes from this host (VERIFIED) — host unreachable (likely geo/IP filtering of non-TW IPs, UNVERIFIED reason; there is no alternate mirror host confirmed). Fields per catalog: Date, Member ID, company, tax ID, fund code, name, NAV, change, %, type, currency, certificate code; Open Government Data License 1.0 — [data.gov.tw](https://data.gov.tw/en/datasets/11109) (from prior notes + page reference).
- TWSE OpenAPI swagger: https://openapi.twse.com.tw/v1/swagger.json HTTP 200 (143 paths, free, no key). `GET /v1/opendata/t187ap47_L` "基金基本資料彙總表" returns 278 funds (出表日期 1151116) with keys: 基金代號, 基金簡稱, 基金類型, 基金中文名稱, 基金英文名稱, 標的指數/追蹤指數名稱, 是否設有績效指標, 績效指標名稱, 是否包含國外成分股, 基金統一編號, 成立日期, 上市日期, 基金經理人, 經理公司(電話/地址/董事長/總經理), 總代理人, 發行單位數, 保管機構 (custodian), 備註. Types: 101 foreign-component ETF, 66 domestic ETF, 51 leveraged/inverse, 26+9 active ETFs, 8 futures-trust ETFs (VERIFIED). No ISIN field, no NAV.
- TWSE `https://mis.twse.com.tw/stock/data/all_etf.txt` HTTP 200 JSON: 24 groups, 356 ETFs, fields a=code, b=name, c=units outstanding, d=change in units, e=price, f=estimated NAV (IOPV), g=premium, h=prior NAV, i=date, j=time (VERIFIED field semantics inferred; e.g. 00693U units 45,666,000, 20261117). Intraday/EOD snapshot only, no history.
- TPEx OpenAPI: https://www.tpex.org.tw/openapi/swagger.json HTTP 200 (225 paths). Fund-related: `/tpex_opfund_latest` (開放式基金當日行情表; fields SecurityCode like T1001Y, name, PreNAV, price, volume; only 3 rows now, VERIFIED), `/tpex_opfund_recommended_dealer`, `/tpex_opfund_market_highlight`.
- Fundclear (TDCC 基金資訊觀測站) https://www.fundclear.com.tw/ HTTP 200 Angular SPA; bundle `main.a3786120cd82ab33.js` reveals REST routes: `/api/marketing/offshore/query-fund`, `/api/marketing/offshore/query-fund-class`, `/api/marketing/onshore/query`, `/api/classStats/{offshore,onshore}/query`, `/api/detail-statistics/...`, `/api/marketing-statistics/offshore/fund-class/line-chart/net-asset-value`, `/api/performance/{lipper,ntu,star}/...`, `/api/file-download`, `/api/offshore/download-doc`. A POST to query-fund returns HTTP 403 "Google驗證失敗" (reCAPTCHA required) (VERIFIED). So bulk programmatic use is blocked; check the site's terms or ask TDCC for a data feed.
- SITCA ISIN/manager dataset and FSC 境內基金基本資料: from prior notes, last updated 2021 (UNVERIFIED this session) — [NCHC mirror](https://scidm.nchc.org.tw/en/dataset/b1e1f0ab-a78b-4609-aee7-9741cd319ea3/resource/5cfd2ca5-1cae-4d95-bb26-58c50ab27f8f).

### Inferences
- Coverage achievable now from this host: ~278 listed ETFs (master incl. manager/custodian/inception/benchmark) + 356 ETF intraday NAV estimates; mutual-fund (~1,000+ domestic, ~1,000+ offshore) NAV requires the SITCA nav.csv from a TW/other network (the connector should retry with long timeout and be run from a proxy/GH Actions TW runner) — otherwise a gap.
- ISIN: not in TWSE data; derive from the SITCA ISIN dataset or Fundclear (blocked by captcha).

### Gaps
- Actual nav.csv contents/size/history depth; any non-sitca mirror; FSC OAS API schema; MOPS; TDCC bulk terms.

---

## 4. Singapore (SG)

### Takeaway
Official sources are fragmented: MAS OPERA gives a register (scheme number, name, umbrella, status, manager) only through an interactive ASP.NET page; SGX publishes a free JSON for 108 listed ETFs with price/IOPV; CPF Board publishes CPFIS unit-trust lists as PDFs only (no NAV history). No official bulk NAV/holdings source for SG unit trusts.

### Cited Findings
- MAS OPERA CIS: https://eservices.mas.gov.sg/opera/Public/CIS/ViewSchemes.aspx HTTP 200 (80 KB); table header `Scheme Number | Scheme Name | Umbrella Fund | Scheme Status | Scheme Manager Name` (VERIFIED); no export/CSV control found; ASP.NET postback paging required (UNVERIFIED size).
- SGX ETF JSON: `https://api.sgx.com/securities/v1.1/etfs` HTTP 200, 108 ETFs, free, no key (VERIFIED); fields per item: `nc` (code e.g. Q50), `n` name, `cur` SGD, `lt` last, `pv` prior, `iopv`, `vl` volume, `m` board, `trading_time`, `issuer-name`. The generic `v1.1?params=...` endpoint returned SGX_4015 invalid params for the test; ISIN not returned in my call (UNVERIFIED how to request). Terms: SGX API is undocumented/public website back end (UNVERIFIED licensing).
- CPFIS: old `/member/investing-your-cpf/cpf-investment-scheme` 404 (VERIFIED). Current PDF documents (search): list of List A unit trusts (101 as at 8 Jun 2026, 102 as at 20 Jul 2026; 94 accept direct subscription) at https://www.cpf.gov.sg/service/sfc/servlet.shepherd/document/download/069IW00000R0RqLYAV and ...069IW00000VwNwrYAF; risk-classified list https://www.cpf.gov.sg/content/dam/web/member/business-partners/documents/RCSUT_ListA.pdf (expense ratio, Sharpe, 1y/3y performance, OA/SA eligibility; data as at Q4 2023, updated 28 Mar 2025) — [search results](https://www.cpf.gov.sg/content/dam/web/member/business-partners/documents/RCSUT_ListA.pdf). I did not open the PDFs (UNVERIFIED layout); CPF also hosts `CPFISInvestmentProducts.pdf`.
- IMAS https://www.imas.org.sg/ HTTP 200; publishes CPFIS FTC quarterly performance PDFs (e.g. Q1 2021 report) — aggregate/fund tables in PDF (UNVERIFIED fields) — [IMAS PDF](https://imas.org.sg/wp-content/uploads/2021/08/CPFIS-FTC-Quarterly-Report_Q121_Final4-3.pdf).
- UNOFFICIAL: FSMOne/Fundsingapore/Morningstar SG hold NAV; manager-official files (Nikko AM, Lion Global, Eastspring, Fullerton) not tested.

### Inferences
- SG achievable official coverage: ~108 SGX ETFs (price/IOPV) + ~100 CPFIS List A funds (name, risk class, expense ratio, performance from PDF) + OPERA register (scheme number/manager; hundreds of schemes). SG unit-trust NAV history and holdings have no official aggregator.

### Gaps
- OPERA record count/postback automation; CPFIS PDF parsing; SGX ISIN endpoint; any manager-site NAV downloads; MAS ToS.

---

## 5. Field-by-field matrix (best official source; "-" = none found)

| Field | CN | HK | TW | SG |
|---|---|---|---|---|
| Daily NAV / history | SZSE per-fund NAV history (listed funds); OTC: eid.csrc.gov.cn (unreached) | HKEX ETPs (endpoint unverified); MPF monthly XLS (month-end) | SITCA nav.csv (unreachable from host); TWSE all_etf.txt IOPV | SGX ETF `lt/iopv` snapshot |
| Holdings | eid.csrc.gov.cn periodic reports (unverified) | KFS/annual reports PDF | TWSE/SITCA monthly reports (unverified) | - (manager sites) |
| Manager | SSE FUND_LIST, SZSE list | SFC issuer (management company) | TWSE t187ap47_L | OPERA Scheme Manager |
| Custodian | SSE FUND_LIST `TRUSTEE_NAME` | - (OD PDFs) | TWSE `保管機構` | - |
| ISIN | - | HKEX List of Securities (ETPs only) | - (SITCA 2021 set stale) | SGX (unverified) |
| Ticker/code | 6-digit code | CE ref; HKEX stock code | TWSE code / SITCA code | SGX nc |
| Category | SZSE 基金类别/投资类别 | - (derivative flag only) | TWSE 基金類型 | - |
| Inception | CSRC xlsx 设立日期; SSE listingDate | SFC authorisation date | TWSE 成立日期 | OPERA (no) |
| Net assets | SZSE 当前规模 (shares x NAV) | - | TWSE units outstanding | - |
| Currency | (CNY assumed; not in source) | HKEX trading currency | SITCA `Currency` | SGX `cur` |
| Fees | eid reports / 产品资料概要 | KFS PDF | - | CPFIS expense ratio PDF |
| Risk level | 产品资料概要 | KFS PDF | SITCA (unverified) | CPFIS risk class PDF |
| Benchmark | SSE INDEX_NAME | KFS PDF | TWSE 標的指數 | - |
| Distributions | eid announcements | - | - | - |
| Status | AMAC/CSRC (unverified) | SFC list (authorised) | TWSE | OPERA Scheme Status |

## 6. Concrete connector designs

- hk_sfc_funds (fix): swap regex to `CE_RE`; emit only sub-funds and standalone products; store `authorisation_date`, `derivative_flag`, `umbrella_name` (row[0] stripped), `issuer`, `has_od_link`; dedupe by CE ref. New `hk_hkex_etp` connector: download ListOfSecurities.xlsx daily, filter Category "Exchange Traded Products", store ISIN/stock code/currency; map to SFC rows by normalised name + "#" flag. New `hk_mpfa_prices`: monthly xlrd parse (4 data cols, skip first 6 header rows), key = (trustee, scheme, constituent fund), store month-end NAV. Rate limits: none known; polite 1 req/s.
- cn_exchange: SSE FUND_LIST paging + SZSE list JSON (20/page, 55 pages) + SZSE `1785_child` NAV by code; require Referer header and Chrome UA; store ETF/LOF only; join csrc index by 6-digit code to add manager/custodian/benchmark. Add 设立日期 from the existing CSRC xlsx. OTC tier: queue eid.csrc.gov.cn from a browser session (Playwright) when reachable.
- tw_twse: `t187ap47_L` daily for ETF master; `all_etf.txt` for ETF NAV/IOPV snapshots (store daily snapshots to build history); `tpex_opfund_latest`. tw_sitca_nav: nav.csv daily with 120 s timeout, retry x3, run from TW-reachable network; fall back gracefully.
- sg_sgx_etf: poll `api.sgx.com/securities/v1.1/etfs` daily; sg_mas_opera: ASP.NET viewstate postback paging (UNVERIFIED feasibility; else Playwright); sg_cpfis: parse CPF List A and risk-classified PDFs quarterly (pdfplumber).
- Bulk vs per-fund: SSE/SZSE list/TWSE/TPEx/SGX/HKEX/MPFA are bulk; SZSE NAV and Fundclear are per-fund. Auth: none for any verified endpoint; Fundclear needs reCAPTCHA; SSE/SZSE need Referer. Languages: CN Chinese, TW Chinese (TWSE bilingual names), HK/SG English. ToS/robots: not reviewed for any source (UNVERIFIED); treat SSE/SZSE/SGX back-end JSON as unofficial-API usage to confirm.
