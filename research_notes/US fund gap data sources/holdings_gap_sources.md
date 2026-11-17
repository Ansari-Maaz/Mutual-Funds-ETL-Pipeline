# Official sources for filling missing US mutual fund / ETF portfolio holdings (as of 2026-11-17)

Research caveats: several SEC PDFs (Form N-PORT instructions, DERA readme, adopting releases) could not be parsed by the fetch tool or returned 404; claims from them are taken from SEC pages/law-firm summaries and flagged. Issuer terms-of-use texts were mostly not retrievable.

## 1. Form N-PORT public disclosure timing, DERA data set schedule, new series, gaps

### Takeaway
Under the regime currently in force (as best verified), each fund files N-PORT within 60 days after fiscal-quarter end and only the third-month report is public, so a fund's holdings are public with a lag of up to about 60 days from the quarter-end date and arrive only quarterly. The 2024 amendments (monthly filing in 30 days, monthly public release at 60 days) were deferred to Nov 2027 / May 2028, and a Feb 2026 proposal would instead keep public release quarterly. The SEC DERA data set is itself a quarterly zip, adding a further lag.

### Cited Findings
- Interim final rule (2019): first and second monthly reports of each fiscal quarter are nonpublic; the third-month report (NPORT-P) is public; reports for all months in a quarter are due within 60 days after quarter end; a nonpublic report is NPORT-NP — [SEC interim final rule](https://www.sec.gov/rules-regulations/2019/02/amendments-timing-requirements-filing-reports-form-n-port) (as summarized by search result; PDF not read directly).
- Phase-in history: compliance April 1, 2019 (large groups), April 1, 2020 (small groups) — same source as above, so funds launched since then file under the normal regime.
- Aug 2024 amendments (SEC press release 2024-110): monthly filing within 30 days; each month's report public 60 days after month end; compliance originally Nov 17, 2025 (large) and May 18, 2026 (groups under $1B) — [SEC press release](https://www.sec.gov/newsroom/press-releases/2024-110).
- Compliance for those more-frequent-reporting amendments extended to Nov 17, 2027 (>= $1B) and May 18, 2028 (< $1B) — [Thompson Hine](https://www.thompsonhine.com/insights/sec-extends-compliance-date-for-amendments-to-form-n-port). Names-Rule N-PORT items extended to Nov 17, 2027 (>= $10B groups) / May 18, 2028 (smaller), effective Mar 25, 2026 — [SEC](https://www.sec.gov/rules-regulations/2025/03/s7-16-22).
- Feb 18, 2026 proposal: +15 days to file (45 days after month end), public release moved from monthly to quarterly (60 days after quarter end), ETF share-class data added; comments closed Apr 24, 2026 — [Simpson Thacher](https://www.stblaw.com/about-us/publications/view/2026/05/11/sec-proposes-amendments-to-form-n-port-and-extends-compliance-dates-for-names-rule-reporting-(registered-funds-regulatory-update)); [JD Supra/other summaries via search](https://www.jdsupra.com/legalnews/sec-proposes-amendments-to-form-n-port-3281030/). No final adoption found as of search (latest source May 2026).
- DERA data set: quarterly zips 2019 Q4 to 2026 Q3 (page last reviewed Sept 30, 2026); covers monthly portfolio reports from registered management investment companies and ETFs organized as UITs; money market funds and SBICs (Form N-5) excluded; only publicly disseminated information; filings after 5:30 PM ET on last business day of a quarter go into the next posting; SEC does not guarantee accuracy, extraction errors possible, not a substitute for filings — [SEC N-PORT data sets](https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets).
- Filing structure: NPORT-P XML carries filer CIK and seriesClassInfo with series ID (S...) and class IDs (C...); one trust CIK can hold many series — [docoh mirror example / sec-api docs (third party)](https://sec-api.io/api-reference/form-nport.md).
- Dated-mirror discrepancy: a data.gov copy shows a 2026q2 file while another mirror stops at 2025 Q2, likely harvest dates, not a gap — search result [data.amerigeoss.org](https://data.amerigeoss.org/en/dataset/form-n-port-data-sets).

### Inferences
- A newly launched series will not appear in public N-PORT until its first fiscal quarter ends, plus up to 60 days for filing, plus the next quarterly DERA zip. A fund launched in, say, September has a public holdings report no earlier than about Nov-Dec for a Sept quarter-end fiscal year, and then appears in the next DERA release after that. Exact first-report rule for a new fund (stub period) was not confirmed in an official source.
- Because only the third-month report is public, "holdings as of month 1/2" cannot be sourced from N-PORT until at least Nov 2027 (if the monthly rule takes effect at all; the 2026 proposal would drop it).
- Funds with non-calendar fiscal quarters will appear in DERA data at their own quarter-end months, so a "latest quarter" mismatch is expected.
- Amendments (NPORT-P/A) exist as a form type; data-set handling of amendments not confirmed.

### Gaps
- Official DERA readme text and Form N-PORT General Instructions not parsed (404/PDF); amendment handling, new-fund first-filing rule, and any documented data-set gaps not confirmed. No SEC notice of a missing quarter found.
- Whether the Feb 2026 proposal was finalized after May 2026 is unconfirmed; check sec.gov rulemaking pages.

## 2. ETF daily holdings (Rule 6c-11) and issuer publication / terms

### Takeaway
Rule 6c-11 requires every relying ETF to publish its full holdings on a free public website every business day before the open, so official daily holdings exist for essentially all ETFs; there is no mandated file format, so each issuer uses its own CSV/XLSX/PDF/JSON pages, and reuse terms are issuer-specific and mostly unverified.

### Cited Findings
- Rule text: each business day, disclose prominently on a website that is publicly available and free of charge, before the opening of regular trading on the primary listing exchange, each portfolio holding that will form the basis of the next NAV calculation: ticker, CUSIP or other identifier, description, quantity, percentage weight; plus NAV, market price, premium/discount as of prior business day end — [17 CFR 270.6c-11 (Cornell LII)](https://www.law.cornell.edu/cfr/text/17/270.6c-11).
- SEC staff (ADI 2025-15) observed some ETFs omitted CUSIPs/identifiers; ETFs operating under exemptive orders (non-6c-11) follow their orders — [SEC IM ADI 2025-15](https://sec.gov/about/divisions-offices/division-investment-management/accounting-disclosure-information/adi-2025-15-website-posting-requirements).
- Staff statement (Jan 2024): foreign currency positions must not be shown merely as "cash" — summarized in [Vedder Price](https://vedderprice.com/sec-staff-issues-statement-regarding-etfs-disclosure-of-foreign-currency-holdings).
- Adopting-release commentary: the adopted rule does not require Regulation S-X-format holdings (proposal had) — [Seward & Kissel summary](https://sewkis.com/?p=7019) (secondary; conflicts with 2018 proposal summary by Perkins Coie).
- ARK: help center says holdings are updated daily on ark-funds.com as PDF and CSV; file date is the next trading day — [ARK help center](https://helpcenter.ark-funds.com/en/where-can-i-download-the-latest-etf-holdings), [date note](https://helpcenter.ark-funds.com/can-you-explain-the-date-listed-on-the-ark-etf-holdings-documents). Exact CSV URL not confirmed.
- BlackRock/iShares report-tool terms: downloads are "for your internal use only" (applies to the report-generation tool page; holdings not mentioned) — [iShares report tool](https://www.ishares.com/us/resources/tools/report-generation-tool/create-report). iShares site-wide T&C at [BlackRock T&C](https://www.blackrock.com/corporate/compliance/ishares-terms-and-conditions) — scraping/redistribution clauses not retrieved.
- Third-party tools scrape iShares and ARK (open source `talsan/ishares`, `frefrik/ark-invest-api`) — unofficial, legal status unchecked.

### Inferences
- Daily holdings can be sourced officially from issuer files, but each issuer needs its own connector (iShares, SPDR/SSGA, Invesco, Vanguard, ProShares, Direxion, GraniteShares, Tidal, Themes, ETF Opportunities Trust and others); I could not verify file formats/URLs/terms for SPDR, Invesco, Vanguard, ProShares, Direxion, GraniteShares, Tidal, Themes or ETF Opportunities Trust.
- Issuer site terms commonly restrict automated access and commercial reuse; a commercial API should obtain written permission or license, or rely on SEC filings. This is inference, not verified per issuer.
- Holdings facts (names, weights) in a mandated public disclosure are not obviously copyrightable, but contractual website terms can still restrict automated collection; legal review recommended.

### Gaps
- SPDR, Invesco, Vanguard, ProShares, Direxion, GraniteShares, Tidal, Themes, ETF Opportunities Trust file formats and ToS not found. Rule 6c-11 adopting release PDF unreadable. Does "ETF" here include active non-transparent/semi-transparent ETFs (which are exempt from daily full disclosure under separate orders/Rule 6c-11 not applicable)? Not researched.

## 3. Fund types without N-PORT and where holdings appear

### Takeaway
N-PORT covers registered management companies (open-end, closed-end) and ETFs organized as UITs; money market funds (N-MFP), SBICs, non-ETF UITs, and 1933-Act commodity/crypto trusts are out of scope. Substitutes are N-MFP, N-CSR/N-CSRS, 10-K/10-Q, and issuer sites.

### Cited Findings
- N-PORT covers all registered management investment companies and ETFs organized as UITs; money market funds (rule 2a-7) and SBICs excluded — [SEC N-PORT data sets](https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets); [Willkie memo](https://www.willkie.com/~/media/Files/Publications/2016/11/SEC_Adopts_Rules_to_Modernize_Investment_Company_Reporting_and_Disclosure.pdf); [17 CFR 274.150](https://www.law.cornell.edu/cfr/text/17/274.150).
- N-MFP: monthly under rule 30b1-7, XML, made public 60 days after the month covered; SEC publishes N-MFP data sets — [Toppan Merrill](https://www.toppanmerrill.com/glossary/sec-form-n-mfp/), [N-MFP readme](https://sec.gov/files/nmfp_readme.pdf), [data.gov listing](https://catalog.data.gov/dataset/form-n-mfp-data-sets). Filing deadline varies by source (5th business day per SEC data set page per search summary); verify.
- N-CSR (annual) / N-CSRS (semiannual) contain schedules of investments in the shareholder report; examples on EDGAR, e.g. [Fidelity N-CSRS](https://www.sec.gov/Archives/edgar/data/1364924/000136492424000007/filing7261.htm). Third-party dataset: [sec-api.io](https://sec-api.io/datasets/form-ncsrs-files).
- SPDR Gold Trust files 10-K with schedule of investments (ounces, cost, fair value, % net assets), investment-company presentation since 2014 — [GLD 10-K](https://www.sec.gov/Archives/edgar/data/1222333/000119312515387033/d62404d10k.htm); sponsor site spdrgoldshares.com posts filings.
- Third-party trackers show spot bitcoin ETF holdings daily "taken from issuers" — [Glassnode](https://studio.glassnode.com/charts/institutions.UsSpotEtfBalancesAll?a=BTC) (unofficial; no regulatory source retrieved on 10-K status).

### Inferences
- Variable insurance product funds organized as registered open-end companies should file N-PORT (they are management companies); insurer separate accounts organized as non-ETF UITs do not. Not verified in sources.
- Funds of funds (registered) file N-PORT listing the underlying funds as holdings, not look-through. Not verified here.
- Commodity/crypto trusts (33 Act, e.g. GLD, spot bitcoin) hold one asset; holdings = quantity of the asset in the trust, from the issuer website daily and 10-K/10-Q. Whether they are covered by Rule 6c-11 (not investment companies) was not verified.
- Other reasons for no N-PORT rows: fund too new (see section 1); non-calendar quarter; fund liquidated/merged; ETF share class under a mutual fund series (data keyed by series not class); ticker-to-series mapping failure; fund files nonpublic only.

### Gaps
- No official source found for VIT funds, funds-of-funds, commodity/crypto trust treatment, or N-CSR schedule-of-investments requirement (Reg S-X 12-12). Exchange-traded vehicles under the 1940 Act that use derivatives (e.g., futures-based funds) file N-PORT if 1940 Act registered; unverified.

## 4. EDGAR access, rate limits, efficient N-PORT retrieval

### Takeaway
Use data.sec.gov submissions (no key), at most 10 requests/second with an identifying User-Agent, and prefer nightly bulk submissions.zip plus the quarterly DERA data sets to cut requests.

### Cited Findings
- Fair access: max 10 requests/second; scripts should send a User-Agent naming company/project and admin email, sample `User-Agent: Sample Company Name AdminContact@<domain>.com`, plus `Accept-Encoding: gzip, deflate`; SEC may lower the limit; no tech support — [SEC accessing EDGAR data](https://www.sec.gov/search-filings/edgar-search-assistance/accessing-edgar-data). Privacy page: SEC may block IPs exceeding 10/sec — [SEC privacy](https://www.sec.gov/about/privacy-information).
- Bulk: daily Feed tar.gz, daily indexes, full/quarterly indexes rebuilt weekly — same accessing-EDGAR page.
- Submissions API: `https://data.sec.gov/submissions/CIK##########.json`; recent filings up to 1,000 or one year in columnar arrays, older in extra files listed; no key; real time; no CORS — [SEC API docs](https://www.sec.gov/edgar/sec-api-documentation). Bulk `https://www.sec.gov/Archives/edgar/daily-index/bulkdata/submissions.zip` rebuilt nightly about 3am ET — same page.

### Inferences
- Efficient pattern (inferred): map fund ticker/series to trust CIK (SEC company_tickers_mf.json or series/class from N-PORT XML), pull trust submissions (or bulk submissions.zip), filter form NPORT-P (and N-CSR/N-CSRS), fetch each primary XML once, parse by seriesId. A trust CIK filing covers many series, so one fetch serves many funds. Use DERA data sets for historical bulk load and per-filing XML only for filings newer than the latest quarterly zip.

### Gaps
- Exact N-PORT XML path convention and the mapping files were not verified in this pass; the company_tickers_mf.json file was not fetched.

## 5. Programmatic route to schedules of investments in N-CSR/N-CSRS

### Takeaway
Funds absent from N-PORT still file N-CSR/N-CSRS in EDGAR with an embedded schedule of investments (HTML, no structured XML required for the schedule); retrieve via the submissions API by form type and parse the HTML.

### Cited Findings
- N-CSRS/N-CSR filings contain the schedule of investments inside the report document (example above). Vendors package them as datasets ([sec-api.io](https://sec-api.io/datasets/form-ncsrs-files)); no official structured data set for N-CSR schedules was found.
- Form N-CSR structured-data (inline XBRL for fund annual reports) not researched.

### Inferences
- Parsing requires per-filer HTML table extraction; coverage is semiannual with lag of about 10 days (transmittal to shareholders within 60 days of period end, filed on EDGAR around then). These timing values are from general knowledge, not a cited source.
- Mutual fund reports may now be short-form tailored shareholder reports (since July 2024) with full schedules of investments filed separately/available online; unverified here.

### Gaps
- Official source on N-CSR timing, tailored shareholder reports effect on schedules, and any machine-readable format not found.

## 6. Redistribution terms

### Takeaway
SEC.gov information is generally public and may be redistributed with appropriate citation (SEC logos/EDGAR marks restricted). Issuer website terms vary and may restrict automated access or reuse.

### Cited Findings
- "Information on sec.gov is generally public and may be redistributed with appropriate citation"; logos and EDGAR trademarks restricted (page last updated Nov 29, 2023) — [SEC privacy information](https://www.sec.gov/about/privacy-information). DERA data sets have no separate terms; disclaimer only — [SEC N-PORT data sets](https://www.sec.gov/data-research/sec-markets-data/form-n-port-data-sets).
- iShares report tool downloads "for your internal use only" — [iShares](https://www.ishares.com/us/resources/tools/report-generation-tool/create-report). BlackRock ibonds tool terms prohibit scraping/robots — [BlackRock ibonds terms](https://blackrock.com/us/individual/compliance/ibonds-ladder-tool-terms) (different tool; indicative only).

### Inferences
- A commercial API can redistribute holdings drawn from SEC filings (with attribution and a disclaimer on accuracy) with low risk; issuer-site-sourced holdings carry contract/ToS risk and should be cleared per issuer or licensed. Not legal advice.

### Gaps
- No issuer-specific ToS for SPDR, Invesco, Vanguard, ARK, Tidal, Themes, Direxion, ProShares, GraniteShares, ETF Opportunities Trust retrieved; robots.txt not checked.

## Stale / uncertain items
- Status of Feb 2026 N-PORT proposal after May 2026 unknown.
- Some mirror pages show older data-set coverage; the SEC page itself (reviewed Sept 30, 2026) lists through 2026 Q3.
- Some third-party summaries (search result snippets) are secondary; the primary PDFs were not parsed.
