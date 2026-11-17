# US Mutual Fund / ETF ISIN and CUSIP: sources and redistribution licensing (as of Nov 2026)

Scope: US-domiciled open-end mutual fund share classes and ETFs only. Not legal advice. Research was limited (about 15 tool calls); several primary documents (CGS licence-fee page, CGS subscription agreement, ANNA ASB licence, final FDTA rule text) could not be read directly and are listed under Gaps.

## 1. Which sources publish fund-class CUSIPs/ISINs, and is any of it free and redistributable?

### Takeaway
No free source was found that is both complete for fund share-class CUSIPs and clearly redistributable. The SEC publishes free US government data keyed on ticker plus Series/Class IDs (no CUSIP/ISIN in the mutual fund ticker file). The CUSIPs that do appear in free SEC files (13F list, N-PORT holdings) are subject to a separate question of CGS's claimed rights, and the SEC pages I read carry no explicit CGS licence notice.

### Cited Findings
- SEC `company_tickers_mf.json` has four fields per record: a numeric registrant ID, Series ID (S000...), Class ID (C000...), and ticker (e.g. LACAX). It contains no CUSIP or ISIN. Field labels are absent from the file; field meanings are inferred from formats. — [SEC](https://www.sec.gov/files/company_tickers_mf.json)
- The SEC 13F "Section 13(f) securities" list is published quarterly under Section 13(f)(4) and includes a "CUSIP Number" field (positions 01-09). The page states no CUSIP usage restriction and does not say whether it covers mutual funds. ETFs are exchange-listed equities and generally appear on such lists (my inference, not stated on the page); open-end mutual funds are not 13(f) securities by definition (inference). — [SEC 13F list](https://www.sec.gov/divisions/investment/13flists.htm)
- SEC publishes quarterly Form N-PORT data sets (zip files, landing page under sec.gov/data-research/sec-markets-data/form-n-port-data-sets). Third-party descriptions say holdings records carry CUSIP/ISIN/LEI of held securities. These identify the securities a fund holds, not the fund's own share-class CUSIP (inference). I did not verify against the SEC readme. — [Data.gov catalog](https://catalog.data.gov/dataset/form-n-port-data-sets), [sec-api.io](https://sec-api.io/datasets/form-nport)
- DTCC Fund/SERV is described as the US industry standard for processing and settling mutual fund transactions; the DTCC MFPS II fact sheet lists access to "Fund/SERV Security Master File information" as a benefit. This is a participant/subscription service, not a public feed. — [DTCC MFPS II fact sheet](https://www.dtcc.com/-/media/Files/Downloads/Investment-Product-Services/Wealth-Management-Services/Funds/MFPS-II-Fact-Sheet.pdf), [DTCC Learning](https://dtcclearning.com/products-and-services/mutual-fund-services.html)
- Nasdaq's fund pricing service (launched 1984 as Mutual Fund Quotation Service; now Nasdaq Fund Network) has data formats with CUSIP fields; Nasdaq says it validates CUSIPs entered by pricing agents and fund families. Data products are Nasdaq-licensed. — [Nasdaq MFQS FAQ (2011, stale)](https://nasdaqtrader.com/content/newsalerts/2011/dn/mfqs0050_faqs.pdf), [Finextra](https://www.finextra.com/pressarticle/73283/nasdaq-rebrands-and-relaunches-mutual-fund-quotation-service), [Nasdaq Trader NFN](https://nasdaqtrader.com/Trader.aspx?id=MFQS)
- FINRA Market Data Center lets users search by symbol, CUSIP or keyword for equities, ETFs, mutual funds; FINRA says it is retiring it and launching a "Market Data and Investments Explorer" on Oct 1, 2026. Whether it displays CUSIPs and permits redistribution was not verified. — [FINRA market data FAQ](https://www.finra.org/Investors/MarketData/P124134)
- ANNA lists CUSIP Global Services (CGS) as the Substitute Numbering Agency for the US (code XA); US ISINs are assigned by CGS. — [ANNA FAQ](https://anna-web.org/faq-page/)
- CGS site: a CGS ISIN is a 12-character identifier (country code + 9-character CUSIP/CINS + check digit); CGS assigns ISINs in the US. — [CUSIP.com](https://www.cusip.com/identifiers.html)

### Inferences
- Fund sponsors print CUSIPs on prospectuses/fact sheets and issuer sites (not verified in this research); scraping those is a practical but legally unclear route (see section 2).
- Realistic free path: SEC ticker/Series/Class IDs plus 13F-list CUSIPs for ETFs. Mutual fund share-class CUSIPs need a licensed feed.

### Gaps
- Did not verify whether SEC N-PORT/N-CEN/485BPOS filings expose share-class CUSIPs (N-CEN/prospectus cover pages generally give ticker, not CUSIP).
- No confirmed FINRA, Nasdaq NFN or DTCC pricing/redistribution terms for CUSIP.
- Did not verify issuer-website CUSIP availability.

## 2. CGS licence terms, ABA/CGS redistribution, fee schedule, and the open-identifier debate

### Takeaway
CGS's published website terms restrict CUSIP database use to internal trading/settlement and forbid publishing or distributing the database or subsets; CGS licenses end users by identifier volume and has pressed firms to sign even when data arrives via third-party vendors. The legality of those claims is in active antitrust litigation (Section 2 Sherman Act claim survived dismissal in 2023). A 2021-era European settlement gave vendors a capped licence for US ISIN data, but it is EU-specific.

### Cited Findings
- CGS grants a "personal, revocable, non-exclusive, non-transferable, limited license" to its sites for viewing and ad hoc noncommercial use; redistribution of site content and derivative works are prohibited. For the CUSIP database, use of numbers/descriptions is limited to internal trading and settlement, and the database or subsets may not be published or distributed. CGS "reserves the right to change fees at any time." — [CUSIP.com](https://www.cusip.com/identifiers.html)
- CGS published CUSIP Entity Identifier (CEI) fees effective Jan 1, 2025 ($100 per request for 1-10 CEIs down to $35 for 501+; annual renewal $50 to $15 per entity). The page refers to a separate licence-fees page for CUSIP/ISIN fees, which I did not read. CEI is for entities in the syndicated loan market, not fund share classes. — [CUSIP.com](https://www.cusip.com/identifiers.html)
- Trade press: a 2022 complaint cites an example of about $477,750 a year for an end user with over 40,000 securities across four or more business lines and three or more regions; a later report cites a calculator maximum of $518,138 and a waiver of the fee (but not the licence) for users under 500 identifiers per 12 months. — [WatersTechnology (2022)](https://www.waterstechnology.com/regulation/7936086/class-action-lawsuit-takes-aim-at-cusip-sp-factset-aba); search-result summary of [WatersTechnology](https://www.waterstechnology.com/node/7952504) (figures unverified at source, paywalled).
- Third-party contract forms say any use outside clearing and settlement requires a CGS licence and fee based on usage; FactSet's copy of a CUSIP agreement (a data-feed trial agreement) says its terms are mandated by CGS and cannot be altered by FactSet. The PDF text was unreadable to my tool, so this comes from search-result snippets. — [FactSet CUSIP agreement PDF](https://go.factset.com/hubfs/Website_Downloads/Third-party%20Terms/cusip_agreement.pdf)
- European Commission settlement (S&P era): US ISIN masterfile data in standalone form with a cost-recovery cap of US$15,000 per year for European firms and data vendors redistributing; S&P stopped double-charging firms sourcing ISINs from other vendors. Critics said end users still had to sign a data contract and could not cut the CUSIP out of the ISIN or resell it. Dated roughly 2011-2017 and EU-specific, so potentially stale. — [A-Team Insight](https://a-teaminsight.com/blog/sps-purcell-discusses-the-european-commissions-ruling-regarding-us-isin-pricing-practices), [EFAMA/BVI 2017 paper](https://www.bvi.de/fileadmin/user_upload/Regulierung/Positionen/ISIN/efama-ISIN_Case-situation-post-expiry-20170517.pdf)
- CGS changed hands: FactSet agreed in Dec 2021 to buy CGS for nearly $2B; the European Commission had required S&P to divest it in the IHS Markit merger. — [WatersTechnology](https://www.waterstechnology.com/regulation/7936086/class-action-lawsuit-takes-aim-at-cusip-sp-factset-aba)
- Litigation: Dinosaur Financial Group and Swiss Life Investment Management filed a class action on March 4, 2022 (SDNY, 22 Civ. 1860) against S&P Global, CGS, ABA and FactSet alleging licence fees rest on a baseless ABA copyright claim; data vendors are excluded from the class. In July 2023 Judge Failla dismissed all claims except a Section 2 Sherman Act claim; plaintiffs now include Hildene Capital Management. These are allegations; no final merits ruling was found. — [WatersTechnology complaint](https://www.waterstechnology.com/regulation/7936086/class-action-lawsuit-takes-aim-at-cusip-sp-factset-aba), [WatersTechnology ruling (19 Jul 2023)](https://www.waterstechnology.com/node/7951120), [SEC comment letter noting denial in large part](https://www.sec.gov/comments/s7-2024-05/s7202405-526315-1509703.pdf)
- June 2024: CGS/FactSet sent letters to a US broker-dealer threatening to cut off access unless it signs a CGS licence even though it gets CUSIP data through third-party vendors. — [WatersTechnology, 6 Jun 2024](https://www.waterstechnology.com/node/7951850) (only the opening was visible)
- Open identifier debate: in Aug 2024 nine US agencies proposed FDTA joint data standards naming FIGI as the financial instrument identifier; industry (including CUSIP-aligned parties) objected. A final joint rule was published in the Federal Register on June 25, 2026 and, per a search summary, does not establish FIGI as the standard; LEI (ISO 17442) is the entity standard. I could not read the rule text to see what instrument-identifier outcome it states. — [Chapman summary](https://www.chapman.com/media/publication/15141_Chapman-Financial-Regulatory-Agencies-Propose-FDTA-Rule-090524.pdf), [Peirce statement](https://www.sec.gov/newsroom/speeches-statements/peirce-statement-financial-data-transparency-act-080224), [Federal Register 2026-12787](https://www.federalregister.gov/documents/2026/06/25/2026-12787/financial-data-transparency-act-joint-data-standards) (not fetched; result via search summary only)

### Inferences
- Published terms require a CGS licence for any commercial use beyond clearing/settlement; displaying or serving CUSIPs through an API to third parties is redistribution and would, on these terms, need CGS authorisation. No public redistributor/vendor tier or fee schedule was found (the $15,000 cap was EU-specific and old). Expect a negotiated contract.
- The litigation is unresolved as far as found, so neither CGS's position nor the plaintiffs' is confirmed; the open-identifier debate did not, per sources found, create a legal safe harbour for redistributing CUSIPs.

### Gaps
- CGS licence-fees page, subscription agreement and any "data vendor/redistributor" licence were not read; no confirmed fee tier for redistribution.
- Current status (2025-2026) of Dinosaur Financial v. S&P Global not found.
- Final FDTA rule text on instrument identifiers not verified.

## 3. Is a US ISIN a derived work of the CUSIP? ANNA / ISO 6166

### Takeaway
No source states a legal "derived work" determination. CGS's own description embeds the CUSIP in the ISIN, and critics report CGS contracts bar stripping the CUSIP from an ISIN; ANNA's position is that CUSIP-based ISINs are not available under an open licence in the US.

### Cited Findings
- US ISIN = "US" + 9-character CUSIP + check digit; CGS assigns it as the US substitute numbering agency. — [CUSIP.com](https://www.cusip.com/identifiers.html), [ANNA FAQ](https://anna-web.org/faq-page/)
- Contract commentary: the CGS data contract requires firms to guarantee they will not cut the CUSIP out of the ISIN or resell the ISIN to another party. CGS said the EU issue was "only ... using the ISIN for cross referencing purposes." — [A-Team Insight](https://a-teaminsight.com/blog/sps-purcell-discusses-the-european-commissions-ruling-regarding-us-isin-pricing-practices)
- ANNA comment letter (Fed/FDTA docket, 2024) said, as paraphrased by a search summary, that CUSIP and ISINs embedding it are not available under an open licence in the US. — [Federal Reserve comment R-1837](https://www.federalreserve.gov/SECRS/2024/November/20241112/R-1837/R-1837_102324_161733_421326575288_1.pdf) (paraphrase only; letter not read)
- ISO designates ANNA as Registration Authority for ISO 6166; ANNA Service Bureau (run with CGS and SIX) offers subscription ISIN data to non-members; ANNA's ASB Data Licence Agreement exists but was not read. — [WatersTechnology](https://www.waterstechnology.com/inside-reference-data/news/2094805/iso-chooses-anna-registration-authority-6166), [ANNA reports](https://anna-web.org/report/page/29)

### Inferences
- Since the ISIN contains the full CUSIP, a vendor that publishes US ISINs is, as a practical matter, publishing CUSIPs; the CGS contract language reported suggests CGS treats them together. Whether that is legally a derived work is not stated anywhere I found.

### Gaps
- ISO 6166 text (paywalled) and ASB licence text not read.

## 4. Alternatives

### Takeaway
OpenFIGI/FIGI is free to redistribute. SEC Series/Class IDs plus ticker, and LEI for fund entities, are open. None replaces CUSIP/ISIN for customers who require them.

### Cited Findings
- OpenFIGI Terms of Service (last updated Nov 27, 2018, so older than 2023, potentially stale): allows use, display, reproduction, distribution and creation of derivative works of FIGI identifiers, including passing them to customers, for commercial or non-commercial purposes; identifiers dedicated to the public domain and free. The terms do not mention API rate limits (see API docs). — [OpenFIGI terms](https://openfigi.com/docs/terms-of-service)
- OpenFIGI FAQ states no licensing or reuse restrictions or hidden fees; the OMG FIGI standard is described under MIT licence; API schema lists Apache 2.0 (inconsistent descriptions). — [OpenFIGI FAQ](https://openfigi.com/docs/faqs), [OpenFIGI API schema](https://api.openfigi.com/schema)
- OpenFIGI API maps tickers to FIGIs; EODHD advertises mapping between CUSIP, ISIN, FIGI, LEI, CIK and ticker. — [EODHD llms-full](https://eodhd.com/llms-full.txt)
- SEC ticker file provides Series ID / Class ID / ticker for mutual fund share classes at no cost (see section 1). — [SEC](https://www.sec.gov/files/company_tickers_mf.json)
- LEI is the FDTA legal-entity standard (ISO 17442); LEIs identify fund legal entities, not share classes (inference). — [Federal Register summary via search](https://www.federalregister.gov/documents/2026/06/25/2026-12787/financial-data-transparency-act-joint-data-standards)

### Inferences
- Recommended key design: SEC Class ID + ticker (+ FIGI via OpenFIGI) as primary keys; offer CUSIP/ISIN only if licensed. OpenFIGI's ability to return CUSIP/ISIN is not documented here; do not assume it can be used to obtain them.

### Gaps
- Current OpenFIGI rate limits and whether share-class FIGI coverage of US mutual funds is complete were not checked.

## 5. How other vendors say they source/license ISIN and CUSIP

### Takeaway
Little is publicly stated. Vendors mostly treat ISIN/CUSIP as a paid add-on or enterprise feature and push commercial/redistribution use to custom licensing.

### Cited Findings
- Twelve Data: its LLM reference says ISIN and CUSIP are available via Data add-ons, and FIGI on Ultra/Enterprise plans. Sourcing not stated. — [Twelve Data llms-full](https://twelvedata.com/llms-full.txt)
- EODHD: pricing-page packages are personal use only; commercial use needs a quote; says it does not use exchange feeds and aggregates 100+ OTC/trading-platform sources; says it must report commercial users to exchanges. Does not discuss redistribution or CUSIP licensing there. — [EODHD commercial terms](https://eodhd.com/financial-apis/commercial-vs-personal-license-use)
- Financial Modeling Prep joined FISD and says its licensing/entitlement structures align with exchange norms; no CUSIP/ISIN statement found. — [FMP announcement](https://site.financialmodelingprep.com/education/news/fmp-joins-fisd-strengthening-alignment-with-global-marketdata-standards)

### Gaps
- Nothing found for Tiingo or Polygon. No vendor statement naming CGS as its CUSIP source or describing redistribution rights was found.

## 6. Cost and procurement path for a startup API

### Takeaway
No published startup or redistributor price was found. Procurement is by contract with CGS (FactSet) directly, or by buying CUSIP/ISIN-enriched data from a vendor whose licence permits onward redistribution.

### Cited Findings
- End-user fee reports range up to roughly $477,750 to $518,138 per year at the top tier; small users under 500 identifiers get the fee waived but still need a licence. — [WatersTechnology](https://www.waterstechnology.com/regulation/7936086/class-action-lawsuit-takes-aim-at-cusip-sp-factset-aba), summary of [WatersTechnology](https://www.waterstechnology.com/node/7952504)
- CEI-only fee schedule published (loan-market entities, not applicable to share classes). — [CUSIP.com](https://www.cusip.com/identifiers.html)

### Inferences
- A US fund universe is large (my estimate, unsourced: tens of thousands of share classes), so an API would likely be in a mid-volume tier plus a redistribution/vendor agreement. Realistic routes: (1) contact CGS/FactSet for a vendor redistribution licence; (2) licence from a data aggregator (Morningstar, Refinitiv/LSEG, ICE, etc.) with display/redistribution rights, not verified here; (3) skip CUSIP/ISIN and ship SEC IDs + ticker + FIGI.

### Gaps
- No quote or published redistributor tier; no startup-specific pricing found. Aggregator licence terms not researched.
