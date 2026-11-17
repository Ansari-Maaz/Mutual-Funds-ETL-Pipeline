# Japan (JP) and South Korea (KR): official fund-data sources, matrix and connector design (research run 2026-11-18, probes from this host)

Legend: VERIFIED = fetched this session from this host (real response seen). UNVERIFIED = from search snippets/background, not fetched. OFFICIAL = regulator/exchange/association/government. MANAGER-OFFICIAL = published by the fund manager itself (primary data, but not a regulator). UNOFFICIAL = anything else. Language: JA = Japanese only, KO = Korean only, EN = English page/file exists.

## 1. Japan: integrated sources and why they under-deliver

### Takeaway
The three integrated JP connectors are pure fund-list files (name, manager, category) with no NAV, ISIN, currency or holdings, because the NISA lists carry only those columns. The only complete free NAV/ISIN source (the IMAJ Toushin Library) forbids scraping in writing, but a keyless manager-level JSON API (MUFG AM) and the JPX ETF files fill part of the gap today.

### Cited Findings
- Integrated JP connectors (read in repo): `jp_imaj_nisa_growth_funds` (IMAJ xlsx `unlisted_fund_for_investor.xlsx`, NISA growth-quota non-listed trusts), `jp_fsa_tsumitate_funds` (FSA `.../products/YYYYMMDD/23.xlsx`, tsumitate NISA funds, id is a hash of manager+name, no code), `jp_imaj_new_funds` (IMAJ newfunds page xlsx, 11 rows), plus aggregate-only statistics. Source: `/media/asim/4_TB_1/MFAPI/MF ETL PIPELINE/app/connectors/japan_funds.py` (lines 15-330) and `reports/jp_*_manifest.json`. These files list only fund name/manager/category/launch info; the code never sets `currency`, `isin`, NAV or holdings (consistent with the DB state stated in the brief).
- IMAJ library terms, VERIFIED text on the fund-detail page: "自動的な手段による情報の取得（Webスクレイピング、ロボットによるデータ収集、等）を禁止します" (automated acquisition incl. scraping/robots is prohibited), copyright reserved, no use beyond private copying without rights-holder permission, weekly maintenance Sunday ~04:00 for ~30 min — [fund detail page](https://toushin-lib.fwg.ne.jp/FdsWeb/FDST030000?isinCd=JP90C000C7Z0) (HTTP 200, text/html, fetched).
- Library hosts: `toushin-lib.fwg.ne.jp` answers (HTTP 200) while `toushin-lib.fwr.jp` (150.95.255.38) TIMED OUT at 20 s from this host (both curl probes). Pages are keyed by `FdsWeb/FDST030000?isinCd=<ISIN>`; an unknown ISIN returns "該当ファンドは存在しない". The page links to the IMAJ "library-guide" video page; no CSV-download link was found in the page HTML (grep of hrefs: only FDST000000/999900-999905 menu pages) — UNVERIFIED that no CSV feature exists behind the JS UI (search/ranking pages not tested).
- Organization change: a Daiwa glossary entry states the Investment Trusts Association merged with the Japan Investment Advisers Association on 2026-04-01 and became 一般社団法人資産運用業協会 (Japan Asset Management Association) — [Daiwa glossary](https://www.daiwa.jp/glossary/YST1345.html) (search snippet); MUFG AM's page footer also reads 「加入協会：一般社団法人資産運用業協会」 (VERIFIED). `toushin.or.jp` 301-redirects to `imaj.or.jp` (VERIFIED); `imaj.or.jp/robots.txt` is 404 (VERIFIED), so the written library terms are the only restriction found.
- IMAJ site: `/statistics/` returns 200 and links `/statistics/factbook/`, `/statistics/jiaa/`, `/statistics/report/`, `/statistics/research/`, `/statistics/world/` (VERIFIED); `/toukei/` is 404. No fund-by-fund (ファンド別) download link was found on the statistics index (it exposes aggregates; fund-by-fund data lives only in the library).

### Inferences
- The "no NAV/ISIN/currency" gap is a source-scope problem, not a parser bug: NISA lists have no price columns. Currency for JP domestic trusts can be defaulted to JPY only where the fund is domestic-registered (JPX ETF master and MUFG API are explicit), otherwise it needs a prospectus/EDINET source.
- Because the library is the only free exhaustive daily-NAV source, bulk use needs written permission from the association (contact via IMAJ); do not scrape.

### Gaps
- Whether the library has an authenticated/permitted CSV export (search and ranking pages not inspected; JS UI). Whether the merged association now publishes a licensed data feed (not found).

## 2. Japan: every official source not yet used

### Takeaway
New usable-today sources: MUFG AM public JSON API (NAV, ISIN, association code, net assets, returns, risk; 542 funds; keyless), JPX ETF database + monthly ETF quotation Excel + NISA ETF list + ETN list (VERIFIED), EDINET API v2 (key-gated; best for holdings/fees/trustee, per-fund per-period), iDeCo/FSA lists, manager NAV downloads. JSDA (Securities Dealers) and BoJ/e-Stat are aggregate only.

### Cited Findings
- MUFG AM "投信情報API" (MANAGER-OFFICIAL, free, no key): host `developer.am.mufg.jp`; endpoints `GET /fund_information_all_latest/` (trailing slash needed; VERIFIED: HTTP 200, 894,746 bytes, `retcount 542`), `/fund_information_latest/{association_fund_cd|isin_cd|fund_cd}/{v}`, `/fund_information_all_date/base_date/{YYYYMMDD}`, `/fund_information_date/{association_fund_cd|isin_cd|fund_cd}/{v}/base_date/{d}`, `/code_list/` (542 rows: fund_cd, isin_cd, association_fund_cd, fund_name). VERIFIED sample (eMAXIS 日経225): `{"fund_cd":"250874","isin_cd":"JP90C0006LC1","association_fund_cd":"0331109A","base_date":"20261117","fund_name":"ｅＭＡＸＩＳ 日経２２５インデックス","nav":73611,"cancellation_price":73611,"netassets":134571705113,"percentage_change_1y":"18.4","risk_1y":"29.81",...}`; a historical date (20260105) also returns 200, so NAV history is retrievable by base_date. Covers funds from inception to 6 months after redemption. Spec PDF v1.4.0 (2026-06-09): fields nav, cmp_prev_day, percentage_change(_1m/3m/6m/1y/3y/full + max/min), nav_max/min with dates, risk_1y/3y/full, risk_return, cancellation_price, netassets — [spec PDF](https://www.am.mufg.jp/assets/pdf/tool/webapi/fund_api.pdf), [API page](https://www.am.mufg.jp/tool/webapi/index.html). Terms VERIFIED ([agreement](https://www.am.mufg.jp/tool/webapi/agreement.html)): free; prohibits unfair secondary redistribution/copying/processing; provider may cut access; data not a statutory disclosure. Contains no holdings, fees, manager field (manager is MUFG AM by definition), category, or inception date.
- JPX ETF database (OFFICIAL, EN, xlsx, VERIFIED download 225,107 B, Last-Modified 2026-11-12, "As of December 30, 2025", 468 rows x 51 cols): columns Code, Fund Name, Underlying Index, category, Fund Administrator, Listing Date, Trading Unit, trading values, Net Assets (JPY m), Total Expense Ratio, Management Expense Ratio, Record Date for Dividend Payment, Market Price (closing), Gross Dividend Paid, 12-month Dividend Yield, iNAV, PCF URLs (e.g. `https://inav.ice.com/pcf-download/1306.csv`). Sample row: 1305 iFreeETF TOPIX, Daiwa AM, listed 2001-07-13, net assets 13,100,431.8 m JPY, TER 0.0009 — [JPX investors page](https://www.jpx.co.jp/english/equities/products/etfs/investors/index.html), file `.../investors/tvdivq0000005cdd-att/b5b4pj000000ihxg.xlsx`.
- JPX monthly ETF quotations (OFFICIAL, JA/EN headers, xlsx, VERIFIED): `https://www.jpx.co.jp/equities/products/etfs/data/nlsgeu0000011b0q-att/etf-soba2026.xlsx` (1,062,115 B, Last-Modified 2026-11-11), one sheet per month ("2026.10" ...), columns Code, name (JA+EN), margin/loan flag, trading unit, open/high/low/close with dates, average close, volume, ToSTNeT volume, value; yearly files back to 2016 listed on [data page](https://www.jpx.co.jp/equities/products/etfs/data/01.html). This gives price history (market price, not NAV) per ETF code monthly OHLC only.
- JPX NISA growth-quota product list for commodity/foreign ETFs, ETN, JDR (OFFICIAL, VERIFIED, xlsx 3.36 MB, "as of 2026-09-02"): sheets 成長投資枠対象銘柄一覧, 更新履歴, ETN (cols Indicator, Name, Code, Trading Unit, Bloomberg, Reuters, Management Fee, Issuer, Listing date) — `https://www.jpx.co.jp/equities/products/etfs/issues/tvdivq000001j45s-att/aocfb40000001i2o.xlsx` from [ETF issues page](https://www.jpx.co.jp/english/equities/products/etfs/issues/01-01.html). The JA issues page also exposes per-code PDFs `./files/{code}-j.pdf` (~300+ ETFs; summary sheets).
- JPX robots.txt: `User-Agent:* Disallow:` (empty = allow all), VERIFIED. No explicit bulk-use licence read.
- EDINET API v2 (OFFICIAL FSA, JA only): `https://api.edinet-fsa.go.jp/api/v2/documents.json?date=YYYY-MM-DD&type=2` returns `{"StatusCode": 401,"message": "Access denied due to invalid subscription key..."}` (VERIFIED) so a free Subscription-Key is required (registration via email on the EDINET site per third-party [edinetdb.jp](https://edinetdb.jp/blog/edinet-system-overview); not confirmed on an FSA page). Spec: [ESE140206.pdf](https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/download/ESE140206.pdf). Per API briefing, XBRL is type=1 (ZIP), PDF type=2, CSV type=5 ([FSA briefing](https://disclosure2dl.edinet-fsa.go.jp/guide/EFT013/230501K0001/2/説明会資料.pdf), snippet). The documents list carries `fundCode`, `ordinanceCode`, `formCode`, `docTypeCode` (UNVERIFIED details). Maintenance window 2026-11-21 08:00-11:00 JST ([EDINET notice](https://disclosure2.edinet-fsa.go.jp/WEEK0020.aspx)).
- iDeCo official site `ideco-koushiki.jp` responds 200 (VERIFIED, JA); robots.txt 404. Fund-level NAV/fee lists are published by each recordkeeper (運営管理機関), not centrally (UNVERIFIED).
- FSA tsumitate list page responds 200 (VERIFIED); already integrated.
- Manager sites reachable (HTTP code): Daiwa 200, Amova/AM-One 200, Rakuten 200, SMDAM 200, SBI AM 200, Nomura 302, Nikko 301 (VERIFIED reachability only; their NAV-CSV download links and terms not inspected). The MUFG fund page `am.mufg.jp/fund/253425.html` exposes CSV/xlsx icons (an eMAXIS Slim NAV download exists on the page per the brief; the CSV URL was not extracted, UNVERIFIED).

### Inferences
- JPX ETF DB + MUFG API give high-quality joins: ETF 4-char code to ISIN is not in the JPX file, so ISIN for ETFs must come from MUFG-style APIs, EDINET, or the JSDA/JPX listed-issues list (UNVERIFIED).
- EDINET is the only official bulk source that could cover trustee/custodian, fees, holdings for most domestic public trusts, but only per filing (semiannual/annual), JA only.
- The MUFG API is a template: other managers (Nomura, Daiwa, Amova, Nikko, Rakuten, SBI) likely offer NAV CSV/XLS per fund; each has own terms; treat each as MANAGER-OFFICIAL and check terms.

### Gaps
- EDINET fund docTypeCode/formCode values and XBRL element names for NAV/holdings (spec PDF not parsed; a search for code tables returned nothing citable). Official key sign-up steps. JSDA lists (not fetched beyond homepage 200). BoJ/e-Stat/NPA aggregates not pursued (aggregate only, no fund-level data). Manager NAV-CSV URLs and terms for Nomura/Daiwa/Amova/Nikko/Rakuten.

## 3. Japan: field-by-field matrix

### Takeaway
No single JP source delivers all fields; combine MUFG API (NAV/ISIN/net assets/risk), JPX (ETF master + fees), EDINET (holdings/trustee/fees/inception, per filing) and the NISA lists (manager/category).

### Cited Findings
Cell = source (status). "-" = not available there.
| Field | Best official source | Status |
|---|---|---|
| Daily NAV (基準価額) and history | MUFG API by base_date (MANAGER-OFFICIAL, MUFG funds only); IMAJ library (forbidden to scrape); ETF market price: JPX monthly xlsx | VERIFIED |
| Holdings (組入銘柄) | EDINET XBRL/PDF per report (key needed); monthly reports on manager sites | UNVERIFIED |
| Manager | NISA lists (integrated), JPX ETF DB "Fund Administrator" (name of management company), MUFG API (implicit) | VERIFIED |
| Administrator/trustee/custodian (受託会社) | EDINET filings, prospectus | UNVERIFIED |
| ISIN | MUFG API `isin_cd`; IMAJ library URL key `isinCd` | VERIFIED |
| Ticker / fund code | JPX Code (e.g. 1305, 133A); association code (協会コード) `association_fund_cd` e.g. 0331109A; MUFG `fund_cd` 250874 | VERIFIED |
| Category | NISA lists (integrated); JPX "category" | VERIFIED |
| Inception date | JPX Listing Date (ETF); IMAJ new-funds list; EDINET | VERIFIED (ETF) |
| Net assets | JPX ETF DB (annual), MUFG `netassets` (daily) | VERIFIED |
| Currency | not given by any JP list; JPY for domestic trusts by inference; JPX ETF in JPY | - |
| Fees | JPX TER/MER (ETF); EDINET/prospectus for the rest | VERIFIED (ETF) |
| Risk indicator | MUFG `risk_1y/3y/full` (annualised std dev), `risk_return_*` | VERIFIED |
| Benchmark | JPX "Underlying Index" (ETF); prospectus for trusts | VERIFIED (ETF) |
| Distributions | JPX gross dividend + record date; MUFG site 分配金一覧 page (not API) | VERIFIED (ETF) |
| Status | MUFG API covers to 6 months after redemption; IMAJ library | VERIFIED |

### Inferences
- Matrix coverage in practice: ETF/ETN ~470 funds near-complete; MUFG ~542 funds good on NAV; the remaining ~2,000 domestic trusts need EDINET (holdings/fees/trustee) plus permission-based NAV.

### Gaps
- Holdings/fees structure per EDINET form unverified.

## 4. Japan: concrete connector design

### Takeaway
Build four small connectors with a shared `source_fund_id` key = ISIN where known else association code, and merge by ISIN then association code then fund name.

### Cited Findings
- (design, builds on verified endpoints above) No cited facts beyond Section 2.

### Inferences
1. `jp_mufg_am_api`: GET `/code_list/` for the roster, then `/fund_information_all_latest/` daily; backfill by looping `/fund_information_all_date/base_date/YYYYMMDD` over business days (542 funds x 3 s/call; 1 request per date). Mapping: funds(source_fund_id=association_fund_cd, isin=isin_cd, name=fund_name, manager="三菱UFJ アセットマネジメント", currency=JPY (assumption, domestic trusts), domicile=JP); nav_observations(date=base_date, nav=nav, net_assets=netassets); fund_profile_snapshots(risk_1y/3y/full, returns, cancellation_price). Respect terms (no redistribution). Use `retcount` for completeness check, treat "-"/null as NULL.
2. `jp_jpx_etf`: download ETF DB xlsx (listed on investors page; filename hash changes, so parse href from the page like `_fsa_excel_url`), map Code -> funds.ticker, "Fund Administrator" -> manager, category, listing_date -> inception, TER/MER -> fees snapshot, Net Assets -> net_assets, Underlying Index -> benchmark, dividend fields -> distributions. Monthly `etf-soba2026.xlsx` -> optional market prices (not NAV). ETN sheet from the NISA list. Mark NAV unavailable; iNAV/PCF is an external vendor CSV (ICE/IHS) - not official-open.
3. `jp_edinet`: needs EDINET_API_KEY. Daily `documents.json?date=D&type=2` -> filter on `fundCode` non-null (investment trusts) -> download `documents/{docID}?type=1` (XBRL ZIP) or `type=5` (CSV) -> parse cover (fund name, ISIN/associations code), trustee, fees, holdings table -> portfolio_holdings/holding_metrics, filing dates -> snapshots. Needs element names from the XBRL taxonomy (not verified).
4. Optional permission-based `jp_imaj_library` only after written consent from IMAJ/JAAM; otherwise skip (terms prohibit robots).
- Do a scheduled refresh: MUFG daily after Japanese close; JPX ETF DB yearly, quotes monthly; EDINET daily.

### Gaps
- No sample EDINET fetch (no key). Rate limits for developer.am.mufg.jp not stated in spec.

## 5. South Korea: integrated source and the '??' bucket fix

### Takeaway
The IBK dataset is a 1,132-row product/returns/fee snapshot (as of 2025-12-31) whose "펀드코드" is a 6-digit KOFIA short code (단축코드); domicile/currency are null only because the connector sets them to None. Fix by setting domicile KR and then joining the FSC fund-standard-code API on that short code.

### Cited Findings
- IBK CSV header (VERIFIED, local file `data/raw/south_korea/ibk_fund_information_20251231.csv`, CP949): 운용사명 (manager), 펀드코드, 상품명 (product name), 1/3/6/12개월누적수익률, 20251231기준 위험등급 (risk grade), 펀드유형 (type), 선취수수료 (front-end fee), 총보수 (total expense). All 1,132 펀드코드 values are 6 characters; sample row `슈로더투신운용,001004,키움슈로더유로증권(주식-재간접형)A,2.42,...,2,재간접투자,1,2.01`. 73 rows mention USD/dollar/yen/EUR/JPY in the name.
- Connector sets `domicile_country: None, currency: None` explicitly (`app/connectors/korea_funds.py`, `_load`), which causes the '??' bucket; source manifest states scope "funds handled by IBK; no domicile/currency/NAV" (`reports/kr_ibk_fund_information_dataset_manifest.json`).
- 6-char short code equals the FSC/KOFIA `srtnCd` format (see Section 6), so the join key is available (inference, join untested without key).

### Inferences
- Fix: `domicile_country="KR"` (KOFIA-coded funds are Korean-registered; the connector already has `country_code="KR"`), `currency="KRW"` as default (Korean public funds are KRW-denominated even when investing overseas; share-class names with "(USD)"/"(H)" hints are only investment currency, not unit currency, so do not infer a different currency from the name). Better: overwrite from FSC standard-code join when available. Populate `isin` = asoStdCd, `inception_date` = setpDt, `category` = fndTp.

### Gaps
- 73 name hits for foreign-currency keywords not reviewed to confirm all are KRW-unit funds.

## 6. South Korea: official sources not yet used

### Takeaway
Best new official source: FSC `GetFundProductInfoService/getStandardCodeInfo` (data.go.kr 15094792, free key, no restriction): all KOFIA-coded funds with short code, 협회표준코드 (ISIN), inception date, type. NAV/holdings are only on KOFIA DIS/FreeSIS (reachable today; JSON/XML endpoints via browser-captured requests) and KRX ETF data (KOGL type 4, non-commercial).

### Cited Findings
- FSC Fund Product Basic Information (OFFICIAL, KO, JSON+XML REST, free): endpoint `https://apis.data.go.kr/1160100/service/GetFundProductInfoService/getStandardCodeInfo` — VERIFIED exists (call with a fake key returns `SERVICE_KEY_IS_NOT_REGISTERED_ERROR`, code 30; wrong operation names return `NO_OPENAPI_SERVICE_ERROR`). Parameters: serviceKey, resultType (xml default/json), pageNo, numOfRows, basDt, beginBasDt, endBasDt, likeBasDt, srtnCd, fndNm, likeFndNm, ctg, fndTp. Response item fields (from the page's embedded Swagger, VERIFIED): basDt (base date), srtnCd (short code), fndNm (fund name), ctg (business sector 업권), setpDt (inception date 설정일), fndTp (fund type), prdClsfCd (product classification code), asoStdCd (KOFIA standard code = ISIN-style). Licence "이용허락범위 제한 없음" (no restriction; no KOGL type named). Dev account 10,000 calls/day, production raisable on request (stated for sibling FSC services; not stated on this page). Data updated after 13:00 on the next business day. Registered 2021-11-16, modified 2026-01-02 — [dataset page](https://www.data.go.kr/data/15094792/openapi.do), [catalog JSON](https://www.data.go.kr/catalog/15094792/openapi.json).
- Key sign-up: free member registration on data.go.kr then "활용신청" (apply) on the dataset page; FSC datasets are auto-approved (dev and prod) per the page of sibling dataset 15094799 ([page](https://www.data.go.kr/en/data/15094799/openapi.do)). Error codes: 22/23 daily/per-second limit, 29 blocked IP, 30/31 unregistered/expired key. data.go.kr serves `<meta robots noindex,nofollow>` (VERIFIED) but the API is official.
- Other FSC datasets under `apis.data.go.kr/1160100/` (VERIFIED names/endpoints/licence from catalog JSON): 금융투자협회종합통계정보 15094809 `service/GetKofiaStatisticsInfoService` ops getFundTotalNetEssetInfo (net assets by public/private; aggregate), getTrustScaleInfo, getCMAStatus, ELS/DLS stats — no restriction licence; 금융투자회사공시정보 15094795 `service/GetOfficialNoticeInfoService` (stock trading fees, retirement pension returns; not funds); 금융투자협회기타공시정보 15094799; 자산운용사 영업활동통계정보 15139266 and 투자자문사 15139267 (company-level stats); 펀드상품 판매현황정보 15151230 `GetFdSaleInfoService_V2` (aggregate sales balances by fund type/institution/customer; KOGL type 4 non-commercial no-derivatives; VERIFIED fields) — [page](https://www.data.go.kr/data/15151230/openapi.do).
- FSC 증권상품시세정보 15094806 `GetSecuritiesProductInfoService_V2` ops getETFPriceInfo_V2 / getETNPriceInfo_V2 / getELWPriceInfo_V2 (OFFICIAL via KRX, KOGL type 4: attribution, non-commercial, no modification; page says redistribution to third parties is prohibited and commercial use requires purchasing from KRX data marketplace, krxdata@krx.co.kr). Filters include isinCd, likeSrtnCd, itmsNm, beginNav/endNav, bssIdxIdxNm, beginMrktTotAmt — so ETF NAV, ISIN and base index exist; exact response field names not shown on page (UNVERIFIED). Same KOGL-4 for KRX상장종목정보 15094775 (`GetKrxListedInfoService_V2`) and 지수시세정보. Dev quota 10,000 calls. — [page](https://www.data.go.kr/en/data/15094806/openapi.do).
- KOFIA (금융투자협회) sites, reachability this session: `dis.kofia.or.kr` HTTP 200 (EUC-KR, WebSquare app loading `/websquare/index.jsp?w2xPath=/wq/main/main.xml`) and `freesis.kofia.or.kr` HTTP 200 — both reachable now, unlike the prior timeout note. `robots.txt` on both returns 307 to an error page (no robots rules found). KOFIA's own page says DIS offers 펀드기준가격조회 (NAV lookup), fund comparison search, company disclosures, return disclosures and overseas funds; FreeSIS offers fund size, sales, fees, flows and base prices daily — [KOFIA page](https://www.kofia.or.kr/brd/m_114/view.do?seq=26).
- FreeSIS JSON endpoint VERIFIED working: `POST https://freesis.kofia.or.kr/meta/getMetaDataList.do` with `Content-Type: application/json` and body `{"dmSearch":{"tmpV40":"1000000","tmpV41":"1","tmpV1":"D","tmpV45":"20261101","tmpV46":"20261116","OBJ_NM":"STATSCU0100000060BO"}}` returned `{"unit":"","ds1":[{"TMPV1":"20261116","TMPV2":86924733,...}]}` (daily aggregate series). Each statistic is a different OBJ_NM and tmpV* mapping, discoverable only via browser DevTools; fund-level NAV object not identified.
- DIS XML service pattern VERIFIED: `POST https://dis.kofia.or.kr/proframeWeb/XMLSERVICES/` with XML `<message><proframeHeader><pfmAppName>FS-DIS2</pfmAppName><pfmSvcName>…</pfmSvcName><pfmFnName>…</pfmFnName></proframeHeader>…`; unknown service names return `COMS9009 … is not found`. A 2017 gist uses pfmSvcName `DISDlsOfferSO`/`selectSubscribing` ([gist](https://gist.github.com/mr-yoo/81574873dc8cdecfd380ad3765d04c51)) — that operation name `select` is missing, so the pattern is real but the fund NAV service names were not found by guessing (10 guesses failed).
- KRX data portal `data.krx.co.kr` HTTP 200 (VERIFIED, KO; has EN UI); a guessed POST to `/comm/bldAttendant/getJsonData.cmd` returned HTTP 400 (bad bld ID, not an access block). ETF list/NAV/PDF screens exist in the UI (UNVERIFIED), free viewing, data redistribution restricted.
- DART: `opendart.fss.or.kr` HTTP 200 (VERIFIED); free key, but it covers company filings; fund-level data not confirmed. SEIBro (KSD) `seibro.or.kr` HTTP 302 to a WebSquare page (VERIFIED reachable); SEIBro Open API requires application; fund/ETF ISIN, issuance data (UNVERIFIED).
- Language: all data.go.kr FSC pages have a partial EN translation (`/en/data/...`), but field values (fund names, types) are Korean. KOFIA/KRX UIs have limited EN.

### Inferences
- FSC 15094792 gives the roster the IBK file lacks: total KOFIA-coded fund universe (public and private, all share classes) with ISIN-style asoStdCd and setpDt. It is the right master list; no manager or NAV. Manager must come from KOFIA DIS or fund-company disclosures.
- KRX/FSC ETF NAV is the only official daily NAV open feed, but KOGL type 4 blocks commercial use and redistribution; treat as research-only unless a KRX data licence is bought.
- For public fund NAV, KOFIA DIS is the system of record; capturing its XML requests in a browser is required; check KOFIA terms of use before automated access.

### Gaps
- Exact getETFPriceInfo_V2 response field names; real call outputs (no key). KOFIA terms of use on automation; DIS fund-NAV pfmSvcName; SEIBro open API specifics and KRX PDF (constituents) download endpoints; DART fund coverage; Korea Post fund data (15156910 sales ranking only).

## 7. South Korea: field-by-field matrix

### Takeaway
Roster, ISIN, inception, type, fees and risk grade are solved by FSC + IBK; NAV, holdings, manager, benchmark need KOFIA DIS or KRX.

### Cited Findings
| Field | Source | Status |
|---|---|---|
| Daily NAV (기준가) / history | KOFIA DIS 펀드기준가격조회; FreeSIS; KRX/FSC ETF `nav` | UNVERIFIED (endpoint names missing); ETF filter VERIFIED |
| Holdings | KOFIA DIS fund pages (자산보유현황), KRX ETF PDF, fund reports | UNVERIFIED |
| Manager | IBK `운용사명`; KOFIA DIS | VERIFIED (IBK) |
| Administrator/trustee/custodian | KOFIA DIS / fund prospectus | UNVERIFIED |
| ISIN | FSC `asoStdCd` (KOFIA standard code); ETF `isinCd` | VERIFIED (schema) |
| Ticker / fund code | FSC `srtnCd` = IBK 펀드코드 (6 chars); ETF short code | VERIFIED |
| Category | IBK `펀드유형`; FSC `fndTp`, `ctg`, `prdClsfCd` | VERIFIED |
| Inception | FSC `setpDt` | VERIFIED (schema) |
| Net assets | FSC KOFIA stats (aggregate only); ETF `nPptTotAmt`-type field (UNVERIFIED name) | partial |
| Currency | none in files; KRW default for KOFIA-registered funds (inference) | - |
| Fees | IBK `선취수수료`, `총보수` | VERIFIED |
| Risk indicator | IBK `위험등급` (1-6 grade) | VERIFIED |
| Benchmark | ETF `bssIdxIdxNm`; DIS fund page | partial |
| Distributions | KOFIA DIS / KRX | UNVERIFIED |
| Status | FSC roster (presence); DIS | partial |

### Inferences
- Realistic Korea target: ~all funds with ISIN/inception/type/fee (via FSC+IBK) and ETFs with NAV (KRX); public-fund NAV needs KOFIA.

### Gaps
- Counts of funds in FSC roster (needs key call).

## 8. South Korea: concrete connector design

### Takeaway
Add `kr_fsc_fund_standard_code` (master), patch IBK to join it, and defer KOFIA/KRX NAV until terms and request formats are confirmed.

### Cited Findings
- Design builds on verified endpoint/fields in Section 6.

### Inferences
1. `kr_fsc_fund_standard_code`: env `DATA_GO_KR_KEY`; paginate `getStandardCodeInfo?serviceKey=…&resultType=json&numOfRows=1000&pageNo=n` until `totalCount`; incremental via `beginBasDt`. Map srtnCd -> funds.ticker/source code, asoStdCd -> funds.isin, fndNm -> name, setpDt -> inception, fndTp -> category/type, ctg -> sector, domicile=KR, currency=KRW (default, flagged as assumed). Respect 10,000 calls/day dev limit: at 1000 rows/page it is ample; request production quota.
2. IBK fix: in `korea_funds.py` set domicile_country="KR", currency="KRW", and carry IBK fees/risk/returns into `fund_profile_snapshots` (already), merge by srtnCd.
3. `kr_krx_etf` (research-only flag): FSC `getETFPriceInfo_V2` daily by `basDt` -> nav_observations(nav), net assets, isin, benchmark; keep KOGL-4 attribution and do not redistribute.
4. `kr_kofia_dis_nav`: after capturing the DIS NAV request in a browser, replay the XML POST per standard code or date; confirm terms with KOFIA first. FreeSIS `getMetaDataList.do` for aggregate series.

### Gaps
- Not built or run (no key). Unverified rate limits on KOFIA.
