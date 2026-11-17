# Official fund-data sources: Italy, Netherlands, Denmark, Sweden (tested 2026-11-17/18)

Legend: VERIFIED = fetched this session with curl (browser User-Agent) from this host; UNVERIFIED = from search snippets or inference only. Non-official sources are labelled UNOFFICIAL. Raw test files were kept in /tmp/t (not in repo). No repo code edited.

Cross-cutting finding: no source in these four countries publishes a free, official, bulk daily-NAV feed for the full fund universe. The only verified official daily-NAV feed is Borsa Italiana's (68 ISINs). Sweden's FI XML is the richest official bulk file and is mostly unused: it carries holdings, fund net assets, fees, benchmark and risk, but no unit NAV.

---

## 1. Italy: integrated sources, why they under-deliver, unused official sources, matrix, connector design

### Takeaway
Italy's 14 NAV rows come from a Borsa Italiana "open funds" file that covers only 68 ISINs (14 IT, 47 LU, 5 IE, 2 MT). The 1,360-fund master (BDE) has no ISIN. The best official additions are the Euronext/Borsa Italiana ETF and ATFund lists, the COVIP open-data pension registers and costs, and the Banca d'Italia/Consob registers. Consob and Assogestioni publish no bulk fund-level file that I could find.

### Cited Findings
- Connector it_borsa_nav.py reads a local CSV (data/raw/italy/borsa_italiana_daily_nav.csv) built from the Borsa Italiana NAV page. It emits ISIN, currency and one NAV row per fund, with name "Open fund — ISIN", category "not published in NAV file" and domicile only inferred from the ISIN prefix. That raw CSV is absent from this checkout, so the snapshot step is not reproducible here — `/media/asim/4_TB_1/MFAPI/MF ETL PIPELINE/app/connectors/it_borsa_nav.py`
- The IT master is BdeItalyConnector: the Banco de España list `lista-if-it.csv` (3,108,377 bytes, checked 2026-11-16). The connector keeps only the first 7 columns (code, LEI, name, manager, address, policy, open-ended flag), sets isin=None and currency=None, and filters to open-ended funds — `/media/asim/4_TB_1/MFAPI/MF ETL PIPELINE/app/connectors/bde_european_funds.py`; `/media/asim/4_TB_1/MFAPI/MF ETL PIPELINE/reports/it_bde_dataset_manifest.json`
- The Borsa Italiana NAV page (VERIFIED, HTTP 200) states the "Reference Date" is the date the NAV is transmitted, and the NAV refers to the second trading day before it; it links "Nav del giorno di tutti gli OICR aperti (txt, 512 byte)" and "Nav degli ultimi 30 giorni (txt, 11KB)" — [Borsa Italiana NAV page](https://www.borsaitaliana.it/fondi/fondi-aperti/nav/nav.en.htm)
- VERIFIED daily file: `https://www.borsaitaliana.it/borsa/atf/nav/daily-txt.html` returns content-type text/plain, 3,242 bytes, tab-separated, 5 non-empty fields per record: `dd/mm/yyyy, ISIN, CCY, NAV (comma decimal), NAV in EUR`. Sample: `16/11/2026 IT0005090870 EUR 17,144 17,144`. 68 rows, 68 ISINs, one date (16/11/2026); prefixes LU 47, IT 14, IE 5, MT 2 — [daily file](https://www.borsaitaliana.it/borsa/atf/nav/daily-txt.html)
- VERIFIED history file: `https://www.borsaitaliana.it/borsa/atf/nav/monthly-txt.html`, 68,074 bytes, 1,426 rows over the same 68 ISINs, dates 02/10-ish through 30/10/2026 (rolling ~30 days; the pull showed 19/10/2026 first row), same 5-column format — [monthly file](https://www.borsaitaliana.it/borsa/atf/nav/monthly-txt.html)
- Borsa Italiana robots.txt (VERIFIED) disallows `/media/*.pdf`, `*?filename`, and several list pages with `page=` parameters, but not `/borsa/atf/nav/*` — [robots.txt](https://www.borsaitaliana.it/robots.txt)
- Euronext Live fund directory (exchange, official market operator for Borsa Italiana): the JSON gateway `POST https://live.euronext.com/en/product_directory/data/funds-all-markets?mics=ATFX` (VERIFIED) returned iTotalRecords 68, matching the Borsa NAV file count. MIC `ATFX` is the Borsa Italiana ATFund segment. I did not diff the ISIN sets, so identity is likely but not proved. MICs XMIL and MTAA returned 0 for funds — [Euronext funds list](https://live.euronext.com/en/products/funds/list)
- VERIFIED Euronext CSV download pattern: `POST https://live.euronext.com/en/product_directory/data/funds-all-markets/download?mics=XAMS` with form body `format=csv&layout=vertical&decimal_separator=1&date_form=d%2Fm%2FY&args[initialLetter]=` and a Referer header. Header: `Name;ISIN;Symbol;Market;Currency;"Open Price";"High Price";"low Price";"last Price";"last Trade MIC Time";"Time Zone";Volume;Turnover`; disclaimer rows say "All datapoints provided as of end of last active trading day". The funds list gives exchange last PRICE, not NAV. GET on the same URL returned HTTP 500. A "pd/data/..." variant returned 500 or 301.
- Euronext ETF directory (VERIFIED): `etf-all-markets` (note: singular "etf-", not "etfs-") with `mics=XAMS` returned 547 records; with MTAA or ATFX returned 0 (Milan ETFs sit on other MICs listed in the page's jsongateway, for example MTAA is in the list but returned 0 here, so the Milan ETF MIC needs a probe). The CSV header adds "Instrument Fullname", "ESG Classification", "Closing Price", "Closing Price DateTime" — [Euronext ETF list](https://live.euronext.com/en/products/etfs/list)
- Euronext robots.txt (VERIFIED) lists sitemaps and generic comments; terms of use for redistribution not reviewed (UNVERIFIED).
- COVIP (pension-fund regulator, OFFICIAL) open-data page (VERIFIED, HTTP 200) lists 10 datasets each as JSON/CSV/XLSX: `albo-fondi-pensione-{aperti,negoziali,preesistenti-sez-speciale-1|2|3}`, `albo-piani-individuali-pensionistici`, `schede-costi-fondi-pensione-{aperti,negoziali,preesistenti}`, `schede-costi-piani-individuali-pensionistici`, under `https://www.covip.it/sites/default/files/open-data/<name>.csv` — [COVIP open data](https://www.covip.it/open-data)
- VERIFIED sample: `albo-fondi-pensione-aperti.csv` columns `TipologiaFondo, DenominazioneFondo, NumeroIscrizioneAlboFondo, DataIscrizioneAlboFondo, DataAutorizzazioneCostituzione, RegimePrestazioniFondo, DenominazioneSocieta, DataAutorizzazioneEsercizioAttivita, IndirizzoSedeLegaleSocieta, CapSedeLegaleSocieta, ComuneSedeLegaleSocieta, ProvinciaSedeLegaleSocieta, TipologiaSocieta, Note`; first row "ALLIANZ PREVIDENZA FONDO PENSIONE APERTO", registered 1998-10-16 — [COVIP CSV](https://www.covip.it/sites/default/files/open-data/albo-fondi-pensione-aperti.csv)
- COVIP returns files: `/sites/default/files/rendimentifondi/{FPN,FPA,PIP}_Rendimenti_fine2025.xlsx` give 1/3/5/10/20-year returns and category per compartment (annual, no daily unit values) — [COVIP returns](https://www.covip.it/per-gli-operatori/fondi-pensione/costi-e-rendimenti-dei-fondi-pensione/elenco-dei-rendimenti)
- Consob: `consob.it` and `assogestioni.it` home pages respond (HTTP 200). The search found only Consob's SGR/SICAV interactive area and aggregate statistical bulletins ("bs25/26/27 intermediari"); no fund-level CSV/API for UCITS marketed in Italy was found — [Consob SGR-SICAV area](https://www.consob.it/web/area-operativa-interattiva/sgr-sicav4)
- Assogestioni: the homepage links only articles; guessed paths (`/dati-e-statistiche`) returned 404. No downloadable fund data found (VERIFIED absence at the URLs tried only).
- ESMA/other: not tested here (out of scope of the four-country brief).

### Inferences
Field matrix (Italy):

| Field | Borsa NAV file | Euronext ATFX/ETF CSV | BDE list | COVIP open data | Consob/BdI/Assogestioni |
|---|---|---|---|---|---|
| daily NAV / history | YES (68 ISINs; 30-day rolling; self-archive) | no (trading price only) | no | no | none found |
| holdings | no | no | no | no | none found |
| manager | no | no | YES (name+address) | YES (fund company) | BdI register (UNVERIFIED) |
| administrator/custodian | no | no | no | no | none found |
| ISIN | YES | YES | NO (EU code, LEI only) | no | n/a |
| ticker | no | YES | no | no | n/a |
| category | no | ESG class (ETF) | policy text | category in returns xlsx | none |
| inception date | no | no | no | YES (registration/authorisation date) | n/a |
| net assets | no | no | no | no (aggregate bulletins) | aggregate only |
| currency | YES | YES | no | n/a | n/a |
| fees/TER | no | no | no | YES (schede costi / ISC) | n/a |
| risk indicator | no | no | no | not found | n/a |
| benchmark | no | no | no | not found | n/a |
| distributions | no | no | no | no | n/a |
| status | implicit | implicit | open-ended flag | albo status | n/a |
| share class | no | no | no | per-compartment | n/a |

Concrete connector design (Italy):
1. `it_borsa_nav`: fetch daily + monthly txt live (not a precomputed CSV); parse tabs, comma decimals, `dd/mm/yyyy`; upsert 30 days of NAV on every run to backfill; accumulate in nav_observations over time (history only builds from now). Note that ~46 of 68 ISINs are LU/IE funds sold in Italy, so tie to existing LU/IE funds via ISIN rather than creating "IT-BORSA" duplicates.
2. `it_euronext_atfund`: POST the ATFX CSV for names and tickers to enrich the 68 ISINs (label "Euronext/Borsa Italiana", exchange price; keep out of nav_observations or flag price_type=market).
3. `it_euronext_etf`: probe Milan ETF MICs from the jsongateway list; load ISIN/ticker/currency for funds with fund_type=ETF.
4. `it_covip_open_data`: download the 10 CSVs and the 3 returns xlsx; model as pension funds (fund_type pension) with inception (registration date), manager, fees (schede costi). Optional per the brief.
5. Do not expect ISINs for the 1,360 BDE funds from official sources; a bridge would need Consob/BdI registers or a UNOFFICIAL ISIN list (for example Morningstar/Twelve Data), labelled as such.

### Gaps
- Consob register of UCITS/AIF marketed in Italy: no downloadable file located; not tested whether a searchable web form with export exists.
- Banca d'Italia SGR/SICAV register and Base Dati Statistica OICR (Circular 189) fund-level data: not fetched this session (UNVERIFIED); earlier note says aggregated only.
- Assogestioni fund data / "Mappa del risparmio gestito" and classification: no public file found.
- Whether the 68 Borsa NAV ISINs equal the 68 Euronext ATFX ISINs was not diffed.
- Borsa Italiana terms of reuse for the NAV files: page says only that the exchange accepts no responsibility; formal licence not found.
- IVASS and manager price files (Eurizon, Anima, Generali, Mediolanum etc.) not tested.
- ETF/ETC lists on borsaitaliana.it (not Euronext Live) not fetched.

---

## 2. Netherlands: integrated sources, why they under-deliver, unused official sources, matrix, connector design

### Takeaway
NL's 84 NAV/ISIN rows come from Euronext Amsterdam's fund list, which holds only ~87 exchange-listed funds and gives a trading price, not a NAV. The AFM CIS register lists management companies, not products. There is no official Dutch product-level list with ISINs; fuller coverage needs Euronext ETF lists (547 on XAMS) and manager files.

### Cited Findings
- Connector nl_euronext_funds.py subclasses EuronextSnapshotConnector reading a local CSV (data/raw/netherlands/euronext_amsterdam_funds.csv; absent in this checkout). It keeps rows where nav>0, assigns category by name keywords ("Other" if no match), sets ticker, and creates a one-point NAV series with the last price labelled "NAV/last price published" — `/media/asim/4_TB_1/MFAPI/MF ETL PIPELINE/app/connectors/euronext_base.py`; `/media/asim/4_TB_1/MFAPI/MF ETL PIPELINE/app/connectors/nl_euronext_funds.py`
- VERIFIED: `POST https://live.euronext.com/en/product_directory/data/funds-all-markets?mics=XAMS` returns iTotalRecords 87 and rows such as `ADD VALUE FUND | NL0009388743 | AVFNV | Euronext Amsterdam | EUR 126.01 | -1.85% | 10:00 CET 17 Nov 2026`. The CSV download sample: `"ADD VALUE FUND";NL0009388743;AVFNV;"Euronext Amsterdam";EUR;128.39;...;481;61755.59` — [Euronext funds list](https://live.euronext.com/en/products/funds/list)
- VERIFIED: the individual product page `https://live.euronext.com/en/product/funds/NL0009388743-XAMS` exists (public HTML; fields beyond price not parsed here).
- VERIFIED: Euronext ETF directory for XAMS returned 547 records (`.../etf-all-markets?mics=XAMS`).
- AFM CIS register export (VERIFIED, HTTP 200, 103,605 bytes, 1,261 lines): `https://www.afm.nl/export.aspx?format=csv&type=883bcff1-0f26-442f-9faf-a39ff911b109` (also `format=xml`), columns `Statutaire naam; Handelsnaam; Plaats; Land` (management companies/entities such as AB FCP I, Aberdeen). The detail page shows only statutory name, trade name, place, country, EU-passport (incoming) service, date of entrance and last update — [AFM detail page](https://www.afm.nl/en/sector/registers/vergunningenregisters/beleggingsinstellingen/details?id=01F18A5E-51F2-E411-BA3E-005056BE011C); [AFM registers](https://www.afm.nl/nl-nl/sector/registers)
- The AFM page links to the DNB public register (`https://www.dnb.nl/openbaar-register/`) but that page was not fetched. The NL master in the DB is the BDE list `lista-if-nl.csv` (3,405,645 bytes) with the same 7 columns as Italy — `/media/asim/4_TB_1/MFAPI/MF ETL PIPELINE/reports/nl_bde_dataset_manifest.json`; `/media/asim/4_TB_1/MFAPI/MF ETL PIPELINE/reports/afm_dataset_manifest.json`

### Inferences
Field matrix (Netherlands):

| Field | Euronext XAMS funds/ETF | AFM register | BDE list | DNB register / DUFAS |
|---|---|---|---|---|
| daily NAV/history | no (exchange price only; OHLC, volume) | no | no | none |
| holdings | no | no | no | none |
| manager | no (per product page, UNVERIFIED) | entity only | YES | DNB: licensed firms (UNVERIFIED) |
| administrator/custodian | no | no | no | none |
| ISIN | YES | no | no | none |
| ticker | YES | no | no | none |
| category | ETF "ESG classification"/type only | no | policy text | none |
| inception | no | date of entrance (entity) | no | none |
| net assets | no | no | no | DNB/DUFAS aggregates only (UNVERIFIED) |
| currency | YES | no | no | none |
| fees/TER | no | no | no | none |
| risk, benchmark, distributions, share class | no | no | no | none |
| status | listed | licence | open-ended | licence |

Concrete connector design (Netherlands):
1. Replace the snapshot CSV with a live Euronext fetcher: POST the download endpoint for `funds-all-markets` and `etf-all-markets` with mics=XAMS, honouring the Referer and form fields. Store each day's closing price as a market_price observation (not NAV).
2. Pull each product page (`/en/product/funds/{ISIN}-XAMS`) for manager/fees/NAV-like fields if present (UNVERIFIED, needs testing).
3. Keep AFM export as a management-company reference table (join to BDE `manager` by name) rather than as funds.
4. For NAVs, add manager-official price files (Robeco, NN IP, ACTIAM, ASR, VanEck) per manager; none tested, so UNVERIFIED. Label Morningstar NL as UNOFFICIAL.

### Gaps
- DNB open register and DNB/DUFAS statistics: not fetched; no fund-level data expected.
- Euronext product-page field set (NAV, TER, manager) not extracted.
- Euronext data redistribution terms unverified.
- No manager price files tested (Robeco, NN IP, ACTIAM, ASR, Achmea, VanEck NL).
- AFM prospectus register not checked as a product source.
- Why 84 rows were loaded from an 87-record list (3 dropped) was not investigated; probably nav<=0 or blank rows.

---

## 3. Denmark: integrated sources, why they under-deliver, unused official sources, matrix, connector design

### Takeaway
DK (1,486 funds, 1,088 with manager) is built solely from the Banco de España list, which has no ISIN, NAV or currency. The official ISIN list I could verify is Skattestyrelsen's ABIS list (187 Danish ISINs), but it covers only equity-based investment companies, not all funds. Investering Danmark (the industry body) was unreachable from this host, so daily prices remain unverified.

### Cited Findings
- Connector denmark_bde_funds.py downloads `lista-if-dk.csv` (1,643,242 bytes), keeps rows whose code starts "DKFT" and are "open-ended", and maps manager, LEI, address and policy text only (isin=None, currency=None) — `/media/asim/4_TB_1/MFAPI/MF ETL PIPELINE/app/connectors/denmark_bde_funds.py`; `/media/asim/4_TB_1/MFAPI/MF ETL PIPELINE/reports/denmark_dataset_manifest.json`
- Finanstilsynet (FSA, OFFICIAL) register PDF (VERIFIED, 302 to CDN then HTTP 200, 29,118 bytes, Last-Modified 2025-08-26): "Kapitel 4: Register over investeringsforeninger, specialforeninger, fåmandsforeninger og hedgeforeninger", columns Reg.nr., Afd.nr., Foreningens navn, Afdeling (for example "11080 1 ABN AMRO Invest Danmark"). Association/sub-fund identity only, no ISIN — [Reg4IF.pdf](https://www.finanstilsynet.dk/media/44992/Reg4IF.pdf)
- The FSA registers page (VERIFIED) links `virksomhedsregister.finanstilsynet.dk` (company register), statistics pages (`/tal-og-fakta/statistik/...`) and a capital-market statistics XLSX; it does not list a fund-product file — [FSA registers](https://www.finanstilsynet.dk/Tal-og-fakta/Registre)
- Skattestyrelsen ABIS list (OFFICIAL tax authority, VERIFIED download): `https://skat.dk/media/ej3fviwc/november-2026-abis-liste-2021-2026.xlsx`, 1,314,915 bytes, link found on the "Beviser og aktier i investeringsforeninger og selskaber (IFPA)" page. Sheets: Forside, 2026, 2025, 2024, 2023, 2022, 2021. Columns: `Skattemæssigt hjemsted/Tax residence; ISIN-kode; Navn andelsklasse/Name Shareclass; LEI-kode; CVR/SE/TIN; Navn afdeling/Name Sub-fund; TIN; Navn/Name; Registrerede år; Ikke registrerede år`. Sheet 2026 has 5,508 data rows, 5,409 valid ISINs (LU 3,825, IE 1,135, DK 187, FI 178, DE 53, FR 22) and 226 rows with domicile "Denmark (DK)" (some "Udstedt uden" ISIN). Sample row: `DK0065095094, Investeringsforeningen BankInvest, Global AI Plus Akk., LEI 6488MW6NNV59B6270C31, CVR 13575665, registered 2026` — [skat.dk IFPA page](https://skat.dk/erhverv/ekapital/vaerdipapirer/beviser-og-aktier-i-investeringsforeninger-og-selskaber-ifpa)
- The ABIS list states it covers investment companies that informed Skatteforvaltningen they are equity-based (aktiebaserede) for 2026 and five prior years. A third-party source says Danish distributing investeringsforeninger do not need to be on the positive list — [tradedesk.dk](https://tradedesk.dk/skats-positivliste) (UNOFFICIAL, secondary).
- Skat.dk "Papir- og Kursliste" documents exist (`info.skat.dk/getFile.aspx?Id=89852`, search result only): appears to be a reporting-format document for IFPA, not a price list. The brief's idea of an annual SKAT "Kursliste" of fund ISINs was NOT confirmed (UNVERIFIED) — [search result](https://info.skat.dk/getFile.aspx?Id=89852)
- Investering Danmark (`www.investering.dk`): DNS resolves, but TCP connect timed out (curl) and WebFetch got ECONNREFUSED. Reachability failure from this host, so daily-price and fund-data availability is UNVERIFIED. A search snippet names investering.dk as the IFB industry-site source, without confirming downloads.
- Nasdaq Nordic: `nasdaqomxnordic.com` redirects to `https://www.nasdaq.com/european-market-activity`; the page `.../european-market-activity/funds` exists (HTTP 200) and references `api.nasdaq.com/api/nordic`; my screener probes returned 400 (invalid parameter) and 404, so the exact JSON schema is not established (UNVERIFIED) — [Nasdaq Nordic funds](https://www.nasdaq.com/european-market-activity/funds)
- Danske Invest offers a free daily e-mail of prices (search snippet; manager-official, UNVERIFIED as machine feed) — [Danske Invest](https://www.danskeinvest.dk/articles/annual-general-meeting-of-danske-invest-danske-invest-select-and-danske-invest-index-41280)

### Inferences
Field matrix (Denmark):

| Field | BDE list | FSA Reg4IF PDF | Skat ABIS xlsx | Nasdaq Copenhagen | Investering Danmark |
|---|---|---|---|---|---|
| daily NAV/history | no | no | no | price only if endpoint works (UNVERIFIED) | likely (UNVERIFIED, unreachable) |
| holdings | no | no | no | no | no |
| manager | YES | association name | association name | n/a | UNVERIFIED |
| administrator/custodian | no | no | no | no | UNVERIFIED |
| ISIN | no | no | YES (187 DK, plus 5,200 foreign) | YES (listed ones) | UNVERIFIED |
| ticker | no | no | no | YES | UNVERIFIED |
| category | policy text | no | no | no | UNVERIFIED |
| inception | no | no | registered years | no | no |
| net assets | no | no | no | no | aggregate stats |
| currency | no | no | no | YES | UNVERIFIED |
| fees/TER | no | no | no | no | UNVERIFIED |
| status | open-ended | listed | registered/deregistered years | listed | n/a |
| share class | no | sub-fund (Afd.nr.) | YES (class name) | no | UNVERIFIED |

Concrete connector design (Denmark):
1. `dk_skat_abis`: download the xlsx from the IFPA page (resolve link by parsing the page, since the media path changes monthly), read sheet 2026 (and earlier years), upsert ISIN + share-class name + sub-fund + LEI + CVR; join to the BDE rows by CVR/LEI/fuzzy name to populate `isin`. Domicile Denmark rows (226) first. Label "Skattestyrelsen (partial: equity-based companies)".
2. `dk_fsa_reg4if`: parse the PDF with pdftotext layout mode (Reg.nr., Afd.nr., name, sub-fund) as the authoritative association/sub-fund master. File is dated 2025-08-26, so treat as slightly stale; revisit FSA pages for updates.
3. `dk_nasdaq_cph`: reverse-engineer the api.nasdaq.com/api/nordic endpoint (inspect XHR in a real browser) for listed funds/ETFs: ISIN, ticker, currency, last price.
4. Investering Danmark and manager sites (Nordea Invest, Danske Invest, Jyske Invest, Sparinvest, BankInvest): test from a different network; the connection failure may be IP-specific.

### Gaps
- Investering Danmark's actual data files/APIs: unreachable from this host; unverified.
- Whether SKAT publishes a full-fund "Kursliste" with ISINs: not found; only the ABIS list verified. Whether more complete tax lists exist (for example Skat's lists of investeringsforeninger with minimumsbeskatning/kontoførende) not fetched.
- Nasdaq Copenhagen exact fund/ETF endpoint and fields.
- Danmarks Nationalbank statistics: not fetched; aggregate only expected.
- Manager-official price files not tested.
- Whether the FSA publishes a newer Reg4IF edition than 2025-08-26.

---

## 4. Sweden: FI XML schema, integrated source under-delivery, unused official sources, matrix, connector design

### Takeaway
FI's quarterly "Fondinnehav" XML (OFFICIAL, free, bulk) is already downloaded (726 files) but only fund number, ISIN and name are imported. The same files carry full holdings (122,248 instruments), fund net assets, management fee, benchmark, 24-month standard deviation, active risk, fund-company LEI and "inactive" status. FI has no unit NAV, manager name per fund beyond the fund company, or inception date. Pensionsmyndigheten and Fondbolagens förening offer no verified machine-readable price feed.

### Cited Findings
- Connector fi_sweden.py scrapes the FI page, downloads the zip for the latest quarter, extracts the XMLs, and reads only `Fond_institutnummer`, `Fond_namn`, `Fond_ISIN-kod` (isin may be blank) — `/media/asim/4_TB_1/MFAPI/MF ETL PIPELINE/app/connectors/fi_sweden.py`; the manifest shows 726 files extracted, zip 6,693,565 bytes, empty `period` string — `/media/asim/4_TB_1/MFAPI/MF ETL PIPELINE/reports/fi_sweden_dataset_manifest.json`
- VERIFIED FI index page lists quarterly zips with names like `Fondinnehav 2026Q2 2026-11-12 13.02.zip` (6.39 MB) back to 2020-2021, download pattern `/FondInnehavLista/download?filnamn=Fondinnehav_2026Q2_2026-11-12 13.02.zip` (note the space). The page redirects to `/en/vara-register/fund-holdings/quarterly-fund-holdings/` — [FI quarterly fund holdings](https://www.fi.se/en/vara-register/fund-holdings/quarterly-fund-holdings/?navigation=open)
- VERIFIED local XML (root `VärdepappersfondInnehav`, namespace `http://schemas.fi.se/publika/vardepappersfonder/20200331`): one file per fund, named like `AIX Dynamic_86205_VPFO_2026Q2_2026-07-09 14.44.xml`. Elements: `Rapportinformation/Kvartalsslut` (2026-06-30); `Bolagsinformation/{Fondbolag_namn, Fondbolag_institutnummer, Fondbolag_LEI-kod}`; `Fondinformation/{Fond_institutnummer, Fond_ISIN-kod, Fond_namn, Fond_status}`; `Förvaltningsavgift` with `MedAndelsklasser/Förvaltningsavgift/{Andelsklass_namn, Förvaltningsavgift_Typ/{Förvaltningsavgift_fast, Förvaltningsavgift_Prestationsbaserad/{Avkastningströskel, ProcentuelltUttag}}}` or `UtanAndelsklasser`; `Fondförmögenhet`; `Likvida_medel`; `Övriga_tillgångar_och_skulder`; `Standardavvikelse_24_månader`; `Aktiv_risk`; `Jämförelseindex/Jämförelseindex`; `FinansiellaInstrument/FinansielltInstrument/{Tillgångsslag_enligt_LVF_5_kap, Instrumentnamn, ISIN-kod_instrument, Landkod_Emittent, Valuta, Antal, Nominellt_belopp, Kurs_som_använts_vid_värdering_av_instrumentet, Valutakurs_instrument, Marknadsvärde_instrument, Andel_av_fondförmögenhet_instrument, Bransch/{Branschkod_instrument, Bransch_namn_instrument}}` — files in `/media/asim/4_TB_1/MFAPI/MF ETL PIPELINE/data/raw/sweden/xml/`
- Element presence over the 726 files (my count): Fond_ISIN-kod element in 726 but 38 are empty; Fondförmögenhet, Förvaltningsavgift_fast and holdings in 677; Standardavvikelse_24_månader 655; Aktiv_risk 561; share-class fees (MedAndelsklasser) 504; performance fee 49; `Fond_status = "Ej aktiv fond"` 49 (these have no other data). Total 122,248 instruments, max 3,330 in one fund. Median Fondförmögenhet ≈ 3.07e9, consistent with SEK in whole krona (unit not stated in the file; UNVERIFIED).
- So the "holdings flag 688" in the DB equals funds with ISIN, not funds with imported holdings: no portfolio_holdings rows are loaded for SE.
- FI does not publish unit NAV or "Fonders värde per andel" in this file (no such element found in the scan).
- Pensionsmyndigheten: `https://www.pensionsmyndigheten.se/service/fondtorg/sok` (HTTP 200) is an interactive Fondtorg search; no download link was found. An existing note cites a fund catalogue PDF and monthly Fondhandelsrapport PDFs (not re-fetched) — [Fondhandelsrapport PDF](https://www.pensionsmyndigheten.se/content/dam/pensionsmyndigheten/blanketter---broschyrer---faktablad/statistik/premiepension/fonddata/Fondhandelsrapport%20mars%202023.pdf). The fund-company guidance says approved price reporting is required for a fund to be on Fondtorget; that does not mean prices are published as open data — [Anvisningar till fondavtalet](https://www.pensionsmyndigheten.se/content/dam/pensionsmyndigheten/blanketter---broschyrer---faktablad/f%C3%B6r-fondbolag/Anvisningar%20till%20fondavtalet%204.0.pdf)
- Fondbolagens förening (fondbolagen.se, trade body): site responds; statistics page `https://fondbolagen.se/fakta_index/fondmarknadens-utveckling/` is narrative; the site links fondkollen.se (consumer fund comparison). No data file found. Guessed URLs gave 404 — [Fondbolagen](https://fondbolagen.se/fakta_index/fondmarknadens-utveckling/)
- Nasdaq Stockholm funds: same Nasdaq Nordic redirect and `api.nasdaq.com/api/nordic` unknown schema as Denmark (UNVERIFIED).
- Skatteverket: no price-list or fund-list download found; guidance for KU40/KU41 says the fund's ISIN goes in field 572 — [Skatteverket KU40/KU41](https://skatteverket.se/foretag/skatterochavdrag/kontrolluppgifter/kontrolluppgiftomfondandelarku40ochku41.4.6e8a1495181dad540843908.html) (search result; page not fetched).
- SEB publishes a PDF "fonder_isinkoder" (manager-official, UNVERIFIED) — [SEB ISIN list](https://seb.se/globalassets/global-blocks/asset-management/news/fonders-nyheter-bilagor-och-new-list-block/fonder_isinkoder.pdf)

### Inferences
Field matrix (Sweden):

| Field | FI quarterly XML | Pensionsmyndigheten | Fondbolagen | Nasdaq Stockholm |
|---|---|---|---|---|
| daily NAV/history | no | web search only (no feed found) | no | price (UNVERIFIED) |
| holdings | YES (ISIN, qty, price, MV, weight, sector, country) quarterly, history back to ~2020 | no | no | no |
| manager | fund company name, number, LEI | n/a | n/a | n/a |
| administrator/custodian | no | no | no | no |
| ISIN | YES (688 of 726) | UNVERIFIED | no | YES |
| ticker | no | no | no | YES (UNVERIFIED) |
| category | no (sector per holding only) | fund type (catalogue PDF, UNVERIFIED) | no | no |
| inception | no | no | no | no |
| net assets | YES (Fondförmögenhet, quarter-end) | no | aggregates | no |
| currency | no at fund level (instrument currency only) | no | no | YES |
| fees | YES management fee per share class, performance fee terms | YES fee in catalogue (UNVERIFIED) | no | no |
| risk indicator | YES std dev 24m, active risk (not SRRI) | risk level (UNVERIFIED) | no | no |
| benchmark | YES (text; often "saknas") | no | no | no |
| distributions | no | no | no | no |
| status | "Ej aktiv fond" | n/a | no | no |
| share class | YES class names with fees | no | no | no |

Concrete connector design (Sweden):
1. Extend `fi_sweden` to parse every element above: write funds (ISIN, manager=Fondbolag_namn, LEI, fee, benchmark, risk, net_assets with `net_assets_date = Kvartalsslut`, status inactive), fund_profile_snapshots (fee tree, std dev, active risk), and portfolio_holdings/holding_metrics (122k rows per quarter; weight = `Andel_av_fondförmögenhet_instrument`, MV, country, sector). Fix the manifest `period` regex so it records the quarter (it is blank).
2. Backfill history quarters from the FI index (zips back to 2020/2021).
3. NAV: no official bulk source verified. Candidates to test: Pensionsmyndigheten Fondtorg back-end JSON (inspect XHR), Nasdaq Nordic API (listed funds), and manager-official files (Swedbank Robur, SEB, Handelsbanken, AMF, Lannebo, Nordea). All UNVERIFIED. Morningstar/Fondkollen would be UNOFFICIAL.
4. 38 blank-ISIN files are mostly inactive or new funds: keep them keyed by FI institutnummer.

### Gaps
- No verified daily NAV source for Sweden.
- Fondförmögenhet currency/unit not documented in the XML; no FI schema documentation was fetched.
- Pensionsmyndigheten Fondtorg data API/downloads and the current fund catalogue PDF: not re-fetched.
- SCB/Riksbank statistics (aggregate Fondförmögenhet tables) and Skatteverket year-end fund price list: not found or not tested.
- Nasdaq Nordic API schema unknown.
- FI's other registers (company register) not examined for fund-company master data.

---

## 5. Cross-cutting: bulk vs per-fund, authentication, rate limits, terms, reachability

### Takeaway
Everything verified is anonymous and public; bulk files exist for Borsa Italiana NAV, Euronext lists, AFM, COVIP, FI and Skat. Per-fund access is needed for Euronext product pages and Fondtorget. No explicit licence for reuse was confirmed on any source.

### Cited Findings
- Borsa Italiana txt NAV: anonymous GET, two bulk files, no auth (VERIFIED); robots.txt does not disallow it — [robots.txt](https://www.borsaitaliana.it/robots.txt)
- Euronext Live: anonymous POST with Referer; GET download returns HTTP 500; the site is CloudFront-fronted; robots.txt lists sitemaps (VERIFIED) — [Euronext robots](https://live.euronext.com/robots.txt)
- AFM export: anonymous GET, CSV/XML (VERIFIED). COVIP open data: anonymous GET CSV/JSON/XLSX (VERIFIED). Finanstilsynet PDF: anonymous (VERIFIED, 302 to cdn.finanstilsynet.dk). Skat.dk xlsx: anonymous (VERIFIED). FI zips: anonymous GET (VERIFIED).
- investering.dk connection times out/refused from this host (VERIFIED failure); all other tested domains answered, including consob.it, assogestioni.it, covip.it, fondbolagen.se, pensionsmyndigheten.se, nasdaq.com.
- Banco de España CSVs for IT/NL/DK/LU/DE are bulk and anonymous (already integrated; verified earlier by manifests dated 2026-11-16).

### Inferences
- Rate limits were not stress-tested; use a polite 1 request/second and cache. Terms of reuse for Borsa Italiana, Euronext, FI and Skat should be checked before redistribution (the repository marks them "Public; terms to confirm").

### Gaps
- No formal rate-limit or licence text collected for any source.
