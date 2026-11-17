# East Asia official fund data sources (CN, JP, KR, TW, HK, SG, MN/MO)

Scope note: research was limited (~15 tool calls; web search is US-only and returned weak results for CJK queries). Items marked VERIFIED were fetched or curl-tested on 2026-11-17. Items marked UNVERIFIED come from background knowledge or secondary search snippets and must be checked before building. Unofficial sources are labelled UNOFFICIAL.

## 1. Why HK, KR, TW, SG yield ~0 funds today (diagnosis)

### Takeaway
HK is a connector parser bug (fixable, about 2,255 funds); TW is a publisher timeout from this host (connector not yet written); SG has only a register page and no connector; KR loads 1,132 IBK rows, which the coverage table lists as "??" or source-market only.

### Cited Findings
- HK: reports/latest_run.md lists hk_sfc_authorised_unit_trusts with 2,255 extracted and 0 loaded. reports/hong_kong_rejected_records.jsonl is full of rows `{"source_fund_id": "HK", "reason": "duplicate CE number with conflicting names"}` — local files (/media/asim/4_TB_1/MFAPI/MF ETL PIPELINE/reports/).
- Root cause (VERIFIED in app/connectors/hk_sfc_funds.py `_load`): `re.search(r"\(([A-Za-z0-9]+)\)", target)` returns the FIRST parenthetical. The SFC table's sub-fund cells look like `Name (USD) (BYK033)` or `Name (Lux) (BRB594)` (grep of data/raw/hong_kong/sfc_unit_trusts_mutual_funds.html), so the "CE number" becomes `USD`, `HK`, `LUX`, etc. Hundreds of distinct funds collide on those keys and are rejected as "duplicate CE number with conflicting names". Fix: take the LAST parenthetical group matching the CE pattern `\(([A-Z]{3}\d{3})\)\s*$`, and strip only that suffix from the name. CE refs are 3 letters + 3 digits (e.g. ADX424, AUI725).
- HK page structure (VERIFIED): columns Product (CE No.), Sub-fund (CE No.), Issuer, Authorisation date, Documents, Derivative funds. Offering-doc links embed the CE ref: `searchProduct/getDocListNoDate.do?lang=EN&ceref=ADX434&docType=OD` — [SFC product list](https://apps.sfc.hk/productlistWeb/searchProduct/UTMF.do?lang=EN). Authorisation date and "derivative funds" (Y/N) are available but not currently parsed. Also rows are duplicated in the HTML (each sub-fund appears twice), so dedupe by CE ref.
- TW: the data.gov.tw dataset 11109 lists CSV https://www.sitca.org.tw/MemberK0000/F/03/nav.csv, daily, free, Open Government Data License 1.0, fields Date, Member ID, Company name, Tax ID, Fund code, Fund name, NAV, Rise/fall, Rise/fall %, Type code, Currency, Beneficiary Certificate Code — [data.gov.tw](https://data.gov.tw/en/datasets/11109). curl from this host timed out at 25 s with 0 bytes (VERIFIED), consistent with the catalog note. No TW connector exists in app/connectors/ (no sitca file) — the catalog entry is metadata only.
- SG: the MAS OPERA CIS page is reachable (HTTP 200, 78 KB HTML, VERIFIED with curl) but there is no connector in app/connectors/ for it, so nothing loads — [MAS OPERA](https://eservices.mas.gov.sg/opera/Public/CIS/ViewSchemes.aspx).
- KR: the IBK CSV is imported (1,132 rows) with null domicile/currency, so it lands in the "??" bucket; dis.kofia.or.kr timed out from this host at 25 s (VERIFIED) — [import note](reports/japan_south_korea_import_2026-11-06.md).

### Inferences
- Fixing the HK regex alone should add roughly 2,000+ rows (the file has 2,411 `<tr>`, about 2,255 unique extracted). Since HK domicile is null, set country by `source market` as KR does, or the rows will again appear under "??".
- TW needs a retry/proxy or a fetch from another network; the endpoint may geo-throttle non-Taiwan IPs (inference only).

### Gaps
- Not verified whether the SITCA timeout is IP-based; not tested from another network.

## 2. China (CN)

### Takeaway
No free official bulk daily-NAV feed for all public funds was confirmed. The best official routes are the CSRC fund e-disclosure site (eid.csrc.gov.cn/fund, per-fund filings), manager announcements, and exchange ETF/LOF data. Tiantian/Eastmoney is UNOFFICIAL.

### Cited Findings
- Already integrated: csrc_public_fund_index (dated XLSX, name/currency only, 14,170 rows) — [CSRC index page](https://www.csrc.gov.cn/csrc/c101900/c1029655/content.shtml) (page returns HTTP 200, VERIFIED).
- A fund listing notice dated Oct 2025 states the full text is disclosed on the managers' sites and on the CSRC fund e-disclosure site at eid.csrc.gov.cn/fund (secondary snippet from [China Securities Journal PDF](https://epaper.cs.com.cn/zgzqb/images/2025-10/29/B023/zqB02329.pdf)). The older host fund.csrc.gov.cn was not confirmed as current.
- Search did not surface any official AMAC (amac.org.cn) public-fund NAV download page or SSE/SZSE ETF NAV download page; the only NAV-dataset hit was a commercial vendor product ([LSEG](https://www.lseg.com/en/data-catalogue/funds/pricing/mutual-fund-shanghai-stock-exchange-sse)).

### Inferences (UNVERIFIED, from background knowledge, check before use)
- NEW candidates: (a) eid.csrc.gov.cn/fund per-fund periodic reports (quarterly top-10 holdings, annual full holdings, custodian, manager, fees, NAV tables) as PDF/XBRL-like documents, Chinese only, per-fund; (b) AMAC fund information disclosure (gs.amac.org.cn / fund.amac.org.cn?) listing fund code, manager, custodian, filing/inception date and status for public funds, Chinese only, JavaScript query; (c) SSE (sse.com.cn) and SZSE (szse.cn) ETF/LOF product lists with fund code, manager, inception, listing date, shares outstanding, and published daily NAV/IOPV, Chinese and partly English, per-product or table export; (d) ChinaBond/ChinaClear are not fund-NAV sources. Join key: 6-digit fund code (primary share class; A/C classes have separate codes) — this is the best key to ISIN-less CN data.
- UNOFFICIAL: Tiantian Fund (fund.eastmoney.com), Sina, Howbuy — widely scraped, covers all 6-digit codes with NAV history, but no license; label as fallback only.

### Gaps
- No verified machine-readable official NAV bulk source, no verified fund count or ToS for any CN source. A browser-session check of eid.csrc.gov.cn and amac.org.cn is needed.

## 3. Japan (JP)

### Takeaway
EDINET API v2 (FSA, free key) is the best NEW official source for fund filings with holdings/NAV in XBRL; JPX publishes ETF lists; the IMAJ search library (the only place with daily base prices for nearly all trusts) prohibits scraping.

### Cited Findings
- Already integrated: jp_imaj_nisa_growth_funds (2,364), jp_fsa_tsumitate_funds (366), jp_imaj_new_funds (11), imaj_fund_statistics (aggregate only); jp_imaj_fund_search_library registered but NOT scraped because its terms prohibit robots (catalog.py, app/connectors/japan_funds.py).
- EDINET API v2: endpoint `https://api.edinet-fsa.go.jp/api/v2/documents.json?date=YYYY-MM-DD&type=2` returns HTTP 401 "Access denied due to invalid subscription key" without a key (VERIFIED with curl) — so a (free) API key is required. Official spec is Japanese-only, Version 2, Oct 2025 ([spec PDF](https://disclosure2dl.edinet-fsa.go.jp/guide/static/disclosure/download/ESE140206.pdf)). The document list includes `fundCode`, `ordinanceCode`, `docTypeCode` (120 = securities report), per a research presentation ([PDF](https://researchmap.jp/jgy/presentations/35656008/attachment_file.pdf)); get-document API: type=1 XBRL ZIP, type=2 PDF per a third-party blog ([edinetdb.jp](https://edinetdb.jp/blog/edinet-system-overview)). Free key via email registration and commercial use allowed are reported only by that third-party blog.
- EDINET maintenance window announced 21 Nov 2026 08:00-11:00 JST ([EDINET notice](https://disclosure2.edinet-fsa.go.jp/WEEK0020.aspx)).
- JPX ETF issue lists (English page exists) give code, name, management company, trust fee, listing date, trading unit — [JPX ETF issues](https://www.jpx.co.jp/english/equities/products/etfs/issues/01-01.html); the ETF database Excel (year-end edition, updated about annually) includes NAV/PCF distribution and creation/redemption units — [JPX investors page](https://www.jpx.co.jp/equities/products/etfs/investors/); monthly per-issue price Excel files are at [JPX data](https://www.jpx.co.jp/equities/products/etfs/data/01.html). Direct download URL/net assets not confirmed; WebFetch got 403 on the English index page.

### Inferences (UNVERIFIED)
- NEW: EDINET filings by domestic investment trusts (annual securities reports, semi-annual reports) contain fund code (ファンドコード, e.g. 5-char code/ISIN fields in XBRL cover), NAV, net assets, holdings list, manager, custodian (trustee), fees, inception. About several thousand funds; one document per fund per period (so history is coarse, 6-12 month points, not daily).
- JPX ETF files fill ETF master gap (about 300-400 ETFs/ETNs) with ISIN-able codes; JPX ISIN is derivable from the 4-digit code via the Japan ISIN list.
- IMAJ library join key is the association fund code (协会コード) already in jp_imaj_nisa_growth_funds; it is the only free daily-NAV bulk-like source but terms prohibit automation, so use only manual or licensed.

### Gaps
- EDINET docType/ordinance codes for investment trusts, XBRL element names for holdings, and exact rate limits were not verified.

## 4. South Korea (KR)

### Takeaway
KOFIA is the system of record but has no verified open bulk feed; data.go.kr hosts FSC datasets requiring a free serviceKey, but the ones found are statistics, not fund NAV.

### Cited Findings
- Already integrated: kr_ibk_fund_information (1,132, CSV on data.go.kr 15020770), kofia_fund_info and kofia_dis_fund_nav_search (registered, not automated), kr_fsc_krx_trust_security_prices (listed-security prices only, KOGL type 4, no redistribution) (catalog.py; reports/japan_south_korea_import_2026-11-06.md). The import note records that KOFIA OpenAPI requires application and approval.
- FSC fund-product sales API: `https://apis.data.go.kr/1160100/GetFdSaleInfoService_V2`, JSON/XML, free serviceKey, KOGL type 4 (attribution, no commercial use, no modification); only aggregate balances by fund type/institution/customer — [data.go.kr 15151230](https://www.data.go.kr/data/15151230/openapi.do). Not fund-level.
- Search found FSC-published datasets "펀드상품기본정보" (basic info with name/code, queryable by 기준일자) and "금융투자협회종합통계정보" (aggregate statistics, monthly) on data.go.kr, but exact dataset IDs, endpoints and fields were not confirmed — [FSC press release list](https://www.fsc.go.kr/no010101/76909?curPage=1), [wikidocs listing](https://wikidocs.net/475760).
- Post Office Fund monthly best (data.go.kr 15156910) is sales ranking, not a fund master — [data.go.kr](https://www.data.go.kr/data/15156910/openapi.do).

### Inferences (UNVERIFIED)
- NEW to probe: data.go.kr "금융위원회_펀드상품기본정보" (via the FSC 1160100 service namespace) is the most likely open source of fund code, name, manager, type, and risk; verify the listing and its KOGL type before building. OpenDART (opendart.fss.or.kr, free key) covers listed companies and some funds' filings but investment-trust holdings are not its focus. KRX ETF data (data.krx.co.kr) gives ETF list, NAV, net assets, tracking error via a web UI; terms restrict redistribution.
- Korean fund codes are KOFIA standard codes (e.g. KR5xxxxxxxxx ISIN-like 12-char) — usable join key if the source supplies them.

### Gaps
- Dataset IDs for FSC fund basic info/base price not found; dis.kofia.or.kr unreachable (timeout) from this host.

## 5. Taiwan (TW)

### Takeaway
SITCA/FSC open CSV is the best official daily NAV source (free, licensed for reuse), already catalogued but never imported because the endpoint timed out.

### Cited Findings
- Daily NAV CSV, fields and license as in section 1 — [data.gov.tw 11109](https://data.gov.tw/en/datasets/11109). Daily "Every 1 day", free, Open Government Data License v1.0. Only domestic funds (境內).
- Companion dataset (SITCA) with ISIN code, short-term trading restriction days, monthly-report URL, share class, fund manager name and announcement date — last updated May 2021, so possibly stale — [NCHC mirror](https://scidm.nchc.org.tw/en/dataset/b1e1f0ab-a78b-4609-aee7-9741cd319ea3/resource/5cfd2ca5-1cae-4d95-bb26-58c50ab27f8f). An FSC "境內基金基本資料" dataset exists but one mirror page showed no data; the FSC OAS API docs live at stat.fsc.gov.tw/FSC_OAS3_RESTORE (not opened) — [NCHC mirror](https://scidm.nchc.org.tw/dataset/best_wish43476).
- Join key: fund code plus "Beneficiary Certificate Code" (SITCA code); ISIN from the companion dataset.

### Inferences
- NEW: the SITCA ISIN/manager dataset and TWSE ETF NAV (TWSE OpenAPI openapi.twse.com.tw, JSON, free; UNVERIFIED) would fill ISIN, manager and ETF NAV. MOPS and TDCC not checked.

### Gaps
- Offshore funds (境外基金, about 1,000+ funds via the Offshore Funds Institute/SITCA) not researched. History depth of nav.csv appears to be current day only (inference; unverified).

## 6. Hong Kong (HK)

### Takeaway
SFC list is a public-offer register only (fix the parser). MPFA publishes official monthly MPF unit prices as XLS (12 months); HKEX ETP data and SFC daily NAV are not verified.

### Cited Findings
- Already integrated (broken): hk_sfc_authorised_unit_trusts; sfc_fund_statistics (aggregate, not loaded).
- NEW: MPFA monthly MPF constituent-fund prices, one XLS per month-end, `.../monthly-fund-price/consolidated_list_for_[mon]_[yy]_read_only.xls`; page lists 12 months (Nov 2025 to Oct 2026); column layout and terms not stated; the Oct 2026 entry links to the September file (page inconsistency); a test request for `.../consolidated_list_for_oct_26_read_only.xls` returned HTTP 200 (VERIFIED) — [MPFA page](https://www.mpfa.org.hk/en/info-centre/fund-information/monthly-fund-price/monthly-unit-prices-of-mpf-constituent-funds). MPFA says prices come from trustees and it does not guarantee accuracy — [MPFA search snippet](https://www.mpfa.org.hk/en/info-centre/fund-information/monthly-fund-price).
- MPFA also publishes net asset values of approved constituent funds and a Fund Performance Platform; a data dictionary exists for "netassetvaluesofapprovedconstituentfunds" — [MPFA dictionary PDF](https://www.mpfa.org.hk/tc/-/media/files/information-centre/research-and-statistics/other-reports/dictionary/netassetvaluesofapprovedconstituentfunds-data-dictionary.pdf). data.gov.hk carries MPFA datasets (e.g. DIS fund assets, quarterly) — [data.gov.hk](https://data.gov.hk/en-data/dataset/mpfa-mpfa-mpf-assets-invested-in-dis-constituent-funds). Third-party yflife.com publishes daily MPF history (UNOFFICIAL, trustee site).
- HKEX ETP list page loaded but showed no download link in the fetched text — [HKEX](https://www.hkex.com.hk/Market-Data/Securities-Prices/Exchange-Traded-Products?sc_lang=en).

### Inferences (UNVERIFIED)
- SFC list per CE reference supports offering documents (KFS with ongoing charge, risk class) as PDFs, enabling a fee/risk extraction pipeline but at high effort. HKEX publishes an ETP list (stock code, ISIN, issuer) in downloadable Excel; verify.

### Gaps
- MPF XLS columns, per-fund count (about 400-ish constituent funds, unverified), SFC/HKMA terms.

## 7. Singapore (SG)

### Takeaway
MAS OPERA gives a register only; NAV/holdings must come from SGX (ETFs) or CPFIS lists, none verified.

### Cited Findings
- OPERA CIS page reachable (VERIFIED); lists scheme number, name, umbrella, status, manager per catalog.py. Not integrated (no connector).
- My attempts: SGX ETF lists and CPFIB/CPFIS included-funds list (CPF site URL returned 404) were not located; search returned nothing relevant.

### Inferences (UNVERIFIED)
- CPF Investment Scheme included-funds list (CPF Board, Excel/PDF; includes manager, risk class, expense ratio, returns) and SGX ETF/securities data are the probable NEW sources; MAS has an API portal (eservices.mas.gov.sg/apimg-gw) with some FSS/statistics APIs but no fund NAV known.

### Gaps
- Everything beyond OPERA for SG is unverified.

## 9. Overlap with Twelve Data mutual-fund fields (summary)

### Takeaway
The official East Asian sources give identifiers, manager, type, NAV and currency at best; holdings, fees and risk come only from filings (EDINET, CSRC) or KFS PDFs.

### Cited Findings
- I did not re-read the Twelve Data field list; see reports/twelvedata_field_coverage_2026-11-09.csv for it.
- Field coverage by source (VERIFIED where cited above): SITCA nav.csv = date, code, name, NAV, change, currency, manager company (fills NAV, currency, issuer); MPFA XLS = month-end price (columns unverified); SFC list = name, issuer, authorisation date, CE ref; IBK CSV = code, manager, type, risk grade, returns, fees; IMAJ = code, manager, inception, category.

### Gaps
- Holdings, ISIN, benchmark and distributions have no verified official bulk source in any of these markets except possibly EDINET (JP) and CSRC filings (CN).

## Priority recommendations
1. Fix HK CE-number regex (immediate, about 2,255 funds); also parse authorisation date and derivative flag.
2. Add TW SITCA nav.csv connector with retries and run from a different network; add SITCA ISIN dataset.
3. Register for an EDINET API key and prototype a fund-filing pull (JP NAV/holdings).
4. Add MPFA monthly XLS and SG OPERA connectors.
5. Browser-verify eid.csrc.gov.cn, amac.org.cn, SSE/SZSE ETF pages, and data.go.kr FSC fund-basic-info before committing to CN/KR work.
