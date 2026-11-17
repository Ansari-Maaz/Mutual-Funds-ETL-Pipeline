# Core Western Europe: official fund data sources (FR, LU, IE, DE, GB, CH, AT, BE, LI, MT)

Research date: 2026-11-17. About 15 web tool calls; several official pages were not fully readable. Items marked [UNVERIFIED] come from background knowledge and were not confirmed in this session.

Already integrated (from app/connectors file names and first-line docstrings): amf_geco (GECO compartments export), fr_lacotebleue (ISIN NAV table), central_bank_ireland (UCITS register PDF), de_bundesanzeiger (Fondsdata prices/NAVs), fca (FOI CSV fund master, no NAV), finma (approved CIS PDF), ch_six_fund_explorer (six-group.com/fqs/ref.json), uk_ft_morningstar (FT UTS archive), uk_fundslibrary, lu_euronext_funds, lu_allianz_daily_nav, nl_euronext_funds, bde_european_funds, cnmv/asisa (ES), it_borsa_nav, fi_sweden, denmark_bde_funds. Nothing is integrated yet for ESMA registers, FIRDS, GLEIF, FSMA/BE, FMA-LI, OeKB, MFSA, CSSF lists, or the FCA register API.

## 1. Which official sources close the current DB gaps (NEW vs integrated)

### Takeaway
No free official source gives bulk NAV history plus holdings for Western Europe. Free official sources are mostly identity/reference data (ESMA registers, FIRDS, GLEIF, national lists). Bulk NAV/holdings are paid via exchanges, SIX/SFD, OeKB and EPT/EMT vendors. The best new free wins are: ISIN, CFI, issuer LEI, fund name and currency from FIRDS and GLEIF (fixes DE no-ISIN, IE, GB), ESMA UCITS/AIF/cross-border registers, and FCA register API fields.

### Cited Findings
- ESMA Registers publish data via Solr indexes and a machine-to-machine (A2A) service. Documented cores include `esma_registers_upreg` (UCITS/AIFM management company entities), `esma_registers_funds` (AIF/EuSEF/EuVECA funds), `esma_registers_funds_cbdif` (cross-border marketing of AIFs and UCITS), `esma_registers_mmf04` (money market funds). Plain HTTP GET, no authentication shown, default XML, `wt=json` for JSON, `rows` for page size. Example: `https://registers.esma.europa.eu/solr/esma_registers_upreg/select?q=%7B!join+from%3Did+to%3D_root_%7Dae_entityTypeCode%3AUCI&fq=(type_s%3Aparent)(entity_type%3AaeActivity)(entity_type%3AaeActivityHistory)&rows=1000&wt=json&indent=true`. The ESMA help page says UCITS here means management companies; I did not see a UCITS fund-level core in the 100k characters read. Join keys: LEI for entities, home/host country. — [ESMA Registers A2A help](https://registers.esma.europa.eu/publication/helpApp)
- ESMA FIRDS: full reference files weekly, delta files daily (FI Sweden notice, 2017); ESMA's instructions document is ESMA65-8-5014. A transparency-file variant (ESMA65-8-5240) exists; the equity/non-equity transparency quantitative mechanism was decommissioned 21 April 2026. The FIRDS query core is `esma_registers_firds_files` (name from my background knowledge; the PDF could not be parsed here). — [FI](https://fi.se/en/published/news/2017/esma-publishes-reference-data-and-instructions-for-downloading-files/), [ESMA MiFIR reporting](https://www.esma.europa.eu/data-reporting/mifir-reporting), [ESMA65-8-5240](https://www.esma.europa.eu/sites/default/files/2023-12/ESMA65-8-5240_FIRDS_Transparency_Download_Instructions.pdf)
- GLEIF publishes daily full ISIN-to-LEI relationship CSV files (ANNA/GLEIF mapping; started as a pilot with 11 early-mover NNAs in 2019). Page file list seen only through 11 Jan 2026; current publication not confirmed. Coverage depends on which numbering agencies participate. — [GLEIF download page](https://www.gleif.org/en/lei-data/lei-mapping/download-isin-to-lei-relationship-files), [factsheet](https://www.gleif.org/lei-data/lei-mapping/download-isin-to-lei-relationship-files/2021-06-08_isin-to-lei_factsheet_v1.pdf)
- EPT (European PRIIPs Template) is a free, open field dictionary governed by FinDatEx; it is not a feed. Data is exchanged between companies; free basic exchange via Fund KIS Disclose needs sign-in and customer status. Paid EPT-derived datasets: Kneip PRIIPs Data on Deutsche Börse marketplace (over 150k EU ISINs), SIX PRIIPs data (commercial). — [BVI EPT page](https://bvi.de/en/services/samples-and-working-aids/european-priips-template-ept-comfort-european-priips-template-cept), [Kneip sheet](https://www.mds.deutsche-boerse.com/resource/blob/4095354/ed53b77559157dd08a3e0ed0454e0a36/data/Product%20Sheet_Kneip-PRIIPs%20Data_V1_290824.pdf), [SIX](https://www.six-group.com/de/products-services/financial-information/delivery-methods/files/sixflex/priips-data.html)
- Banque de France publishes OPC aggregate statistics (monthly/quarterly, also on ECB SDW), a labelled-funds referential and panorama/performance pages. I did not find a Banque de France fund-level dataset on data.gouv.fr. Its data is reported confidentially. — [BdF OPC statistics](https://www.banque-france.fr/fr/publications-et-statistiques/statistiques/organisme-de-placements-collectif-opc-et-assurances), [labelled OPC](https://www.banque-france.fr/statistiques/epargne-et-comptes-nationaux-financiers/les-autres-formes-depargne-opc-organismes-de-placement-collectifs-et-assurances/referentiel-des-opc-labellises)

### Inferences
- Priority NEW free joins: (1) FIRDS full file filtered to CFI starting "C" (collective investment vehicles) gives ISIN, name, currency, issuer LEI, CFI, trading venue, dates; this is the best way to fill DE ISIN, IE and GB identity. (2) GLEIF ISIN-LEI for fund LEI. (3) ESMA cross-border UCITS/AIF marketing register for LU/IE funds marketed in DE/FR/GB etc., plus management-company LEI. FIRDS only covers instruments admitted to or traded on EU venues, so unlisted fund shares will be missing; expect partial coverage.
- Manager and category for FR cannot come from BdF open data; use GECO fields (check whether the existing export already exposes management company and AMF classification) and ESMA management-company register.

### Gaps
- Exact FIRDS Solr URL and current file schema (PDF unreadable via fetch). Whether an ESMA UCITS fund-level core exists beyond `esma_registers_funds_cbdif`.
- AMF "Liste des OPC français" Excel weekly file: AMF's GECO note says it would be provided; not confirmed as a current open-data dataset. data.gouv.fr only confirmed for management companies (SGP): https://www.data.gouv.fr/datasets/651427eaf6eab90fa3db2da3/ — [AMF GECO ROSA note](https://geco.amf-france.org/Bio/Bio/BIO_PDFS/ROSA_DATA/Note%20d'accompagnement%20fichiers%20ROSA%20pour%20GECO.pdf), [AMF open data](https://www.amf-france.org/en/news-publications/publications/open-data)
- No source found for SFDR bulk disclosures free of charge; ECB IVF is aggregate only [UNVERIFIED in session].

## 2. Country-by-country catalogue

### Takeaway
Each country has a free regulator list (names, status, manager) but NAV is only free per-fund via exchange/fund-company pages. Per-fund scraping is lower priority.

### Cited Findings
**France**
- AMF GECO: integrated (amf_geco). NEW opportunity: weekly "Liste des OPC français" Excel (see Gaps above). Join key GECO code, ISIN.
- La Cote Bleue: integrated (ISIN-linked NAV snapshot); Euronext Paris fund lists: euronext_base pattern already used for LU/NL.
- Banque de France: aggregate only (above).

**Luxembourg**
- CSSF publishes official UCI lists and monthly "global situation of UCIs" press releases and statistics; the monthly releases list UCITS Part I additions/removals. A fully machine-readable bulk list download was not confirmed. — [CSSF statistics](https://www.cssf.lu/en/statistics/), [monthly release example](https://www.cssf.lu/en/2026/03/global-situation-of-undertakings-for-collective-investment-at-the-end-of-january-2026/). CSSF SFDR UCI data collection exists but is a regulator filing, not public data. — [guide](https://www.cssf.lu/wp-content/uploads/User_Guide_-_SFDR_UCI_Data_Collection_-_practical-guide.pdf)
- LuxSE (bourse.lu / luxse.com): market data is a commercial product (FTP/email, end-of-day and about 30 years of history, hosted on Euronext Optiq); academic licence EOD history only; whether NAV is a field was not confirmed. — [LuxSE data products](https://www.bourse.lu/data-product-range), [academic](https://luxse.com/market-data-services/market-data-products/data-for-academic-purposes)
- Allianz GI daily NAV: integrated. NEW idea: repeat the pattern for other large LU fund-company regulatory/facilities pages (official, per-company HTML tables).

**Ireland**
- CBI registers: downloads page lists PDFs only: authorised UCITS (updated 16 Oct 2026), ICAVs (27 Oct 2026), unit trusts, CCFs, investment LPs, designated investment companies (16 Nov 2026), AIFM and UCITS management company registers. Links are ASP.NET postbacks, no static URLs. UCITS PDF integrated; NEW: the other PDFs (ICAV, AIF-related), and management companies. — [CBI downloads](https://registers.centralbank.ie/downloadspage.aspx)
- Euronext Dublin: Daily Official List PDFs (free; includes investment funds); Bond & Fund Feed is paid and includes mutual fund NAVs. Live funds list pages show name, ISIN, symbol, last price, no confirmed CSV export. — [Euronext Dublin DOL](https://live.euronext.com/de/markets/dublin/daily-official-list), [Bond Fund Feed](https://www.euronext.com/en/data/reference-data/dublin-bond-fund-feed), [live list](https://live.euronext.com/en/products/funds/list)

**Germany**
- BaFin Investment Funds Database covers retail funds marketed in Germany, searchable by name/BaFin id/management company; no bulk download confirmed. — [BaFin](https://www.bafin.de/ref/19590926) (found via search; page content not verified)
- Bundesanzeiger Fondsdata: integrated. BVI: EPT/CEPT template guidance only; BVI fund statistics are aggregate [UNVERIFIED].

**United Kingdom**
- FCA Financial Services Register API base `https://register.fca.org.uk/services/V0.1`; headers X-AUTH-EMAIL and X-AUTH-KEY after free registration; fund endpoints `/CIS/{PRN}`, `/CIS/{PRN}/Names`, `/CIS/{PRN}/Subfund`; `/Search?q=&type=fund`. Per-fund only, gives status, names, sub-funds, no NAV. Source is a third-party library doc; official docs unverified. NEW (FCA FOI CSV is integrated). — [library docs](https://financial-services-register-api.readthedocs.io/en/latest/sources/usage.html)
- FCA runs its own post-Brexit FIRDS-equivalent at data.fca.org.uk (UK ISIN/CFI reference data). NEW. — [FCA FIRDS spec](https://www.fca.org.uk/publication/systems-information/fca-firds-tech-spec_0.pdf)
- FT/Morningstar and FundsLibrary: integrated; both are unofficial/commercial.

**Switzerland**
- Swiss Fund Data (swissfunddata.ch) is the FINMA-recognised official publication platform for Swiss-registered fund reference data, prices, corporate actions and documents; SIX became sole owner in Jan 2025 (an older page says 70% AMAS / 30% SIX). Its terms prohibit systematic extraction/scraping by data distributors, so it is a licensing risk. SIX fund explorer ref.json is already integrated (check against same terms). — [SFD](https://www.swissfundplatform.ch/en/swiss-fund-data), [SIX release](https://www.six-group.com/en/newsroom/media-releases/2025/20250117-six-sfd.html), [SIX fund detail example](https://www.six-group.com/en/market-data/mutual-funds/fund-explorer/fund-detail.CH0200600911CHF4.html)
- FINMA list: integrated.

### Inferences
- Most feasible new connectors by effort/value: FIRDS (bulk, free), GLEIF (bulk, free), ESMA registers (bulk, free), FSMA-BE and FMA-LI lists (small), FCA API (per fund, free key), OeKB free price data (needs confirmation of format).

### Gaps
- Exact URL/format for CSSF UCI list, FSMA-BE export, OeKB free price endpoint, MFSA Malta, BaFin bulk export, FMA Austria. Approximate fund counts per source not obtained.

## 3. Bulk NAV history vs per-fund scraping

### Takeaway
Bulk NAV history is only available commercially (LuxSE, Euronext feeds, Kneip, SIX, OeKB portal). Free official NAV is per-fund or snapshot (latest only) tables: lower priority, except snapshot tables already integrated and accumulated daily.

### Cited Findings
- Euronext Bond & Fund Feed and LuxSE products are paid feeds; SFD forbids scraping by distributors; OeKB FundsXML portal is fee-based. See citations in section 2.
- EUROFIDAI (academic, not a regulator) offers a mutual funds database with NAV for traded and unlisted funds, access by EUROFIDAI code. — [EUROFIDAI guide](https://eurofidai.org/sites/default/files/2024-05/Mutual_funds_database_description_guide.pdf)

### Inferences
- Because snapshots lack history, schedule the integrated daily NAV connectors (Allianz, La Cote Bleue, Euronext, FT, SIX) to store each run into nav_observations to build history forward.

### Gaps
- No free bulk historical NAV source confirmed for any of the ten countries.

## 4. Overlap with Twelve Data mutual fund fields

### Takeaway
Fields obtainable from free official sources: ISIN, name, currency, domicile, management company, status/authorisation date (identity). Fields needing EPT/EMT or fund-company data: SRI, ongoing charges, benchmark, holdings, AUM.

### Cited Findings
- EPT carries PRIIPs data (SRI, costs, performance scenarios); available only via paid or customer-only exchange. — see section 1.
- FIRDS provides CFI, ISIN, issuer LEI, currency per instrument (background knowledge for field list; [UNVERIFIED] against the current schema).

### Inferences
- Twelve Data overlap (not verified against Twelve Data docs in this session): name, ISIN, currency, exchange/ticker, fund family (maps to manager), category, NAV, net assets, expense ratio. Free official coverage: name, ISIN, currency, ticker/venue (FIRDS), family (ESMA/national lists). NAV, category, AUM, fees remain unmet.

### Gaps
- Twelve Data field list was not fetched.
