# Official fund-data sources for Germany, France and Switzerland (state: 18 Nov 2026)

Method: connector code read in app/connectors/, local raw files and reports/*manifest.json inspected, and every endpoint below fetched with curl/python using a normal browser User-Agent on 17-18 Nov 2026. VERIFIED = fetched this session (sample or header quoted). UNVERIFIED = seen only in page text/JS or not reachable. UNIFICIAL items are labelled UNOFFICIAL.

Headline findings (new vs prior notes):
1. FRANCE: the AMF GECO back-office (the same JSON API the ETL already calls for the list) exposes per-share daily NAV history back to 2004, net assets, shares outstanding, coupons (distributions) and corporate actions for French OPC, unauthenticated. Verified live. This single source can replace the "90 NAV" gap. Prior note and the ETL's import doc said GECO has no bulk NAV feed; that is true for a file, but the per-share JSON is open.
2. SWITZERLAND: FINMA publishes the approved-CIS list as XLSX (afch.xlsx) as well as PDF; the XLSX carries Fondsleitung (manager), Depotbank (custodian), legal form and fund-type flags that the PDF connector throws away. SIX `fqs/ref.json` also lists 2,334 ETFs (ProductLine=ET), not only the 49 "IF" rows the connector reads. Swiss Fund Data prohibits systematic extraction by market-data distributors.
3. GERMANY: BaFin's Investmentfonds-Datenbank has a CSV export (verified, 21,611 rows across letters A-Z, with Verwaltungsgesellschaft, launch date, fund type; ISIN on only 6,632). Bundesanzeiger Fondsdata offers a free daily CSV of that day's published prices (verified, 404 rows today) but no history file; the connector expects a local CSV that is not in the repo.

---

## Q1. FRANCE: integrated sources, why they under-deliver, and every unused official source

### Takeaway
The ETL pulls only name/ISIN from GECO's list endpoint and ignores the manager, depositary, classification, creation date, LEI and currency that the same API returns, and never calls GECO's per-share NAV endpoint; La Cote Bleue (UNOFFICIAL) is a ~50-row table that explains the 90 NAVs, and Euronext's funds list contains zero Paris funds. The fix is a GECO share-level NAV/profile crawl.

### Cited Findings

**Integrated sources (what they give / why they under-deliver)**
- amf_geco.py POSTs to `https://geco.amf-france.org/back-office/funds/compartments` (body `productType FR`, `total 100000`) and caches 72 MB `geco_compartments.json` with 15,955 compartment rows (manifest: records 15,955, checked 2026-11-16). VERIFIED locally. Status counts: VIV 13,161, SLD 2,433, ECL 361; prdFaml FIA 11,384, OPCVM 3,571, OFIA 1,000. — local file data/raw/france/geco_compartments.json, reports/amf_geco_dataset_manifest.json
- Fields present in each row (counts of non-empty out of 15,955): prdFamlLib, prdNatureLib, prdSsNatureLib (FCP/SICAV), cmpClssFndAmfCode/Lib (AMF classification e.g. FDSOB "Fonds obligations", 13,114), cmpDateCreation (15,955), cmpDateLqdtn (2,517), nomDepositaire (13,325), gestionnaire + gestionnaireAssocie (manager, with LEI, website, history of names), lei (8,207), sharesIsins (14,600), cmpLblEuveca/Eltif/Eusef labels, fiaEprngSalCode (2,131), prdLblEuveca. — same file. The connector keeps only name, isin, source id: category, manager, depositary/administrator, inception date, status, LEI are all dropped. Hence DB: FR ISIN 25,570, but manager/category/inception 0.
- GECO per-share endpoint `GET https://geco.amf-france.org/back-office/funds/compartment/{cmpId}/shares` VERIFIED (c117009): returns parId (e.g. sh117010), isin FR0014010Q26, parNom "C", parRefDevCode EUR, parAffctnRevnuCode "C" / "Capitalisation pure" (accumulating vs distributing), parTypeSouscrLib, parDateCreation, parStatutCode. — [GECO API](https://geco.amf-france.org/back-office/funds/compartment/c117009/shares)
- GECO NAV endpoint `GET /back-office/funds/vlsCouponsAndOst/{parId}?startDate=YYYY-MM-DD&endDate=YYYY-MM-DD` VERIFIED. Returns `{"netAssetValueDTO":[...],"couponDTOS":[...],"corporateActionDTOS":[...]}`. Sample (AMUNDI EUROPE MONDE OPCVM, sh29449, ISIN FR0010093682): 5,532 distinct daily valuation dates from 2004-09-24 to 2026-11-13; last row `valuationDate 2026-11-13, netAssetValue 68.62, assetUnderManagement 239372.87852 (K EUR), shareNumber 3487940.226, quotationCurrency EUR, cancellation false, transmissionDate 2026-11-16T19:05`. Coupons list from 2005 (`couponDate 2005-03-30, couponAmountInEuro 0.81, exCouponNetAssetValue 33.75`). Full-history call took 7.5 s. — [GECO API](https://geco.amf-france.org/back-office/funds/vlsCouponsAndOst/sh29449?startDate=1990-01-01&endDate=2026-11-17)
- Coverage test: random 25 live compartments -> 34 shares probed, 26 returned NAV history (examples: FIA SELECTION FRANCE SOCIAL 1,214 obs; GAY-LUSSAC MICROCAPS 1,719; REVAIA GROWTH I SLP 19 obs quarterly; FRANCE INVESTISSEMENT CROISSANCE 3 FIA 13 obs). One probed share-class set was empty (CPR CREDIXX INVEST GRADE, 2 shares; likely no VL transmitted), and 5 calls errored on a missing `isin` key in my probe script (shares without ISIN). So roughly 75% of sampled shares have NAV; funds report VL via custodians' transmissions (remitter e.g. caceis, natixis, BNP, SGSS) to AMF. Frequency varies (daily for OPCVM, monthly/quarterly for private FIA). — own probe, 17 Nov 2026
- The GECO front-end (main.js) also references `lastVl/{id}`, `compartment/{id}`, `getCompartmentsBycriteria`, `search`, `chart/{id}`, `shareByCmpCodeParPrincp/{isin}`, `document/byShare/{id}`, `document/download/{id}` and `agreement/grid|number` endpoints (documents = DICI/KID, prospectus). `lastVl/sh33...` returned an empty body (HTTP 200) for the id I tried; `document/*`, `agreement/*`, `chart/*` returned HTTP 400 without correct path/params. UNVERIFIED for documents/KID. — [GECO main.js](https://geco.amf-france.org/main.js)
- GECO UI export columns (from JS): per-share VL export has `Date VL, VL en EUR, Nombre de parts, Actif net en KEUR`; share export has `Nom de la part, Code ISIN part, Categorie de part, Affectation des resultats`. — same main.js
- AMF's own guidance says to find an OPC NAV via GECO or the management company, which must supply it on request; publication frequency is set in the prospectus. VERIFIED page. — [AMF: Ou trouver la VL](https://www.amf-france.org/fr/ou-trouver-la-valeur-liquidative-dun-opc-0)
- fr_lacotebleue.py reads a local CSV `data/raw/france/lacote_bleue_navs.csv` (file absent in repo) scraped from `actusite.lacotebleue.fr/opcvm/` (UNOFFICIAL, third-party). The live page (VERIFIED) is a table of 51 rows: ISIN, Nom, Gestion, Date VL, VL, Actif, filtered by ~35 issuers (Aviva Investors France, Cpr AM, Amiral, Carmignac, etc.), "Derniere mise a jour: 17 nov. 2026 19:30". That is why only 90 NAV rows exist. Its robots.txt only disallows SemrushBot. — [La Cote Bleue](https://actusite.lacotebleue.fr/opcvm/)
- Euronext Paris funds: Euronext's all-markets Funds CSV `https://live.euronext.com/product_directory/data/funds-all-markets/download?mics=ATFX,XAMS,XBRU,XLIS,XMLI,XPAR` VERIFIED today: 161 data rows; ISIN prefixes NL 85, LU 49, IT 14, IE 5, MT 2, BE 2, PT 1; zero FR. Columns `Name;ISIN;Symbol;Market;Currency;Open/High/Low/last Price;last Trade MIC Time;Time Zone;Volume;Turnover`. `mics=XPAR` alone returns 0 rows. So Euronext "Funds" is not a French open-end fund source; French-domiciled ETFs trade as ETFs on Euronext Paris (separate ETF list; my POST to pd_es/data/etfs returned empty so UNVERIFIED). — [Euronext funds list](https://live.euronext.com/en/products/funds/list)
- euronext_base.py + lu/nl connectors read locally-saved CSV snapshots (no downloader), so the NAV is whatever was manually saved. — app/connectors/euronext_base.py, snapshots.py

**Official sources not yet used (France)**
- GECO share + NAV + coupon + corporate-action API (above). VERIFIED, no auth, no key. Terms: GECO page carries no reuse licence text that I could find; AMF mentions-legales text search for "reutilisation/Licence ouverte/Etalab" returned nothing (UNVERIFIED terms). geco robots.txt URL returns the SPA HTML (no robots file). Rate limit unknown; full history call 7.5 s.
- AMF open data on data.gouv.fr: only "Liste des societes de gestion de portefeuille (SGP) agreees" (licence `lov2`, CSV `https://amf.s3.sbg.io.cloud.ovh.net/LISTESSGP/export_od_listesgp_20261117094500_20261117101000.csv`, modified 2026-11-17) plus blacklists, PSCA/DASP white list and net short positions. VERIFIED via data.gouv API. No OPC dataset: data.gouv search "OPCVM" returns only the SGP list. The weekly "Liste des OPC francais" Excel could not be found as open data (prior note unconfirmed; still unconfirmed). — [data.gouv SGP](https://www.data.gouv.fr/datasets/651427eaf6eab90fa3db2da3/); [AMF open data page](https://www.amf-france.org/en/news-publications/publications/open-data)
- SGP list gives manager-level attributes (AMF code, LEI, address) usable to link `gestionnaireId`. VERIFIED listing, columns not inspected.
- Banque de France Webstat IVF1 "Informations sur les fonds d'investissement non monetaires": CSV `https://webstat.banque-france.fr/export/csv/fr/catalogue/ivf1` VERIFIED (5.7 MB, 16,243 rows). Header `series_key;time_period;...;obs_value;...;IVF_ITEM;REF_AREA;DATA_TYPE;IVF_REP_SECTOR;...`. Monthly aggregate series by fund type (obligations, actions, mixtes) only; no fund-level data; data.gouv resource 68ac68d8f67cdbeadc8cbae3, licence "notspecified", terms at webstat mentions-legales. Use only for sanity checks/aggregates. — [data.gouv Webstat IVF1](https://www.data.gouv.fr/datasets/68ac68d8f67cdbeadc8cbae3/)
- AFG (association): reachable; publishes monthly "French investment funds monthly statistics" and "STAT OPC" publications (aggregates, PDF/Excel) — [AFG stats Aug 2026](https://www.afg.asso.fr/en/stats-opc-statistics-on-french-funds-august-2026/). No fund-level file found. AFG data is aggregate only. UNVERIFIED for contents.
- Euronext Paris ETF list (live.euronext.com/en/products/etfs/list) for ticker/ISIN/last price of ETFs; endpoint not verified. UNVERIFIED.
- Banque de France labelled-OPC referential and ECB/BdF aggregates: per prior notes only (europe_core.md), not re-fetched. UNVERIFIED.
- Epargne retraite/PER lists, France Assureurs unit-linked lists, Ministere des Finances: nothing fund-level and machine-readable found; not fetched. UNVERIFIED / likely none.
- Management-company NAV pages: amundi.fr reachable (200); no open-data price file located. UNVERIFIED. These are issuer-official, not regulator.

**Field matrix France (source -> field)**
| Field | Best official source | Status |
|---|---|---|
| ISIN, share class, status, currency | GECO shares (isin, parNom, parStatutCode, parRefDevCode) | VERIFIED |
| Daily NAV + history | GECO vlsCouponsAndOst (2004 onward) | VERIFIED |
| Net assets, shares outstanding | GECO netAssetValueDTO (assetUnderManagement K EUR, shareNumber) | VERIFIED |
| Manager | GECO compartments gestionnaire (+LEI) | in local file, unused |
| Depositary/custodian | GECO nomDepositaire | in local file, unused |
| Category | GECO cmpClssFndAmfLib (AMF class); prdNatureLib (FIVG/FCP...) | in local file; not Morningstar-style |
| Inception date | GECO cmpDateCreation / parDateCreation | in local file |
| Liquidation date / status | cmpDateLqdtn, VIV/SLD/ECL | in local file |
| Distributions | GECO couponDTOS (couponAmountInEuro, exCouponNAV) | VERIFIED; dist policy from parAffctnRevnuLib |
| Splits | GECO corporateActionDTOS (empty in sample) | VERIFIED structure |
| Ticker | none (FR OPC have none); ETFs via Euronext | not available |
| SRI/risk, TER, benchmark | not in GECO JSON seen; in KID PDFs (GECO documents) | UNVERIFIED |
| Holdings | no official open source (AMF has none; periodic reports via issuers, PDF) | gap |

### Inferences
- The "28,465 funds / 25,570 ISIN" DB figure is 28,375 GECO class rows from the list endpoint; GECO shares + NAV crawl is the main lever (class-level ISINs complete, NAV, net assets, coupons). Estimated 13k live compartments x ~1.6 shares ~ 20k+ share calls plus the same number of NAV calls; at ~1-8 s each this is hours, feasible at low concurrency.
- Share rows lacking an `isin` key must be handled (5/34 probe errors).
- Because licence terms are unstated, prudence: attribute AMF, throttle to 1-2 req/s, cache, and ask AMF (open data contact) for written confirmation. The data is the AMF's public regulatory publication.
- Category: use AMF classification (FDSOB etc.) mapped to a Twelve-Data-like taxonomy; no official TER/SRI without KID parsing.

### Gaps
- Licence/reuse terms for GECO API not found. Rate limits unknown. Working `document/*` (KID/DICI) endpoint syntax not determined, so SRI/TER/benchmark via KID remains unverified.
- Whether GECO NAV is provided for all share classes (sample 26/34) and the typical lag (sample: transmissions 1-3 days).
- Euronext Paris ETF list endpoint; AFG fund-level data; PER/France Assureurs lists: not verified.
- Holdings for French funds: no official bulk source found.

---

## Q2. GERMANY: integrated sources, why they under-deliver, and every unused official source

### Takeaway
Germany is integrated only via the Banco de España (a Spanish central-bank list, official but foreign) identity list (6,400 open-ended funds, manager and LEI only, no ISIN, no NAV) and a Bundesanzeiger connector whose input CSV is missing, so NAV = 0. The best additions are BaFin's CSV export (ISIN-bearing for part), Bundesanzeiger's free daily price CSV (accumulate daily), and Xetra's tradable-instrument list for ETFs; there is no official German bulk NAV history.

### Cited Findings

**Integrated**
- bde_european_funds.py (DE) downloads `https://www.bde.es/webbe/en/estadisticas/otras-clasificaciones/clasificacion-entidades/listas-instituciones-financieras/listas-fondos-inversion-pais/lista-if-de.csv` (9.9 MB; manifest sha256 0d1aa3b7..., 2026-11-16). Header VERIFIED locally: `EUROPEAN CODE,LEI,FUND NAME,MANAGEMENT NAME,ADDRESS,INVESTMENT POLICY,CAPITAL VARIABILITY`. Example rows: `DEC2WG1, 894500QI0EPNHRGX3E20, "1. PS Stiftungsfonds", Ampega Investment GmbH, Koeln, Mixed, Open-ended`. Connector keeps Open-ended only (6,400), maps manager; ISIN None, currency None, NAV none. DB: 6,429 funds, manager 6,377. The source has a policy label (Equities/Mixed/Real estate/Other) that is not mapped to category in the connector (only stored in profile JSON). — local data/raw/germany/bde_de_nonmonetary_funds.csv
- de_bundesanzeiger.py reads `data/raw/germany/bundesanzeiger_fund_prices.csv` (columns isin,name,provider,currency,nav,valuation_date); that file does not exist in the repo (data/raw/germany has only the BDE csv), and the import doc says only 248 rows were ever imported from search results. DB shows 0 DE NAV. Category is name-keyword guesswork; `domicile_country` set DE only if ISIN starts DE. — app/connectors/de_bundesanzeiger.py, reports/germany_bundesanzeiger_import.md
- Bundesanzeiger Fondsdata VERIFIED: public page `https://www.bundesanzeiger.de/pub/en/fondsdata` lists latest price per fund (columns Fund name, provider, ISIN/WKN, date, offer, bid, NAV), e.g. `ABN AMRO Funds ... LU2546367892 11/16/2026 Offer 183.12 EUR Bid 183.12 NAV 183.12`. Coverage is funds that publish in the German market including LU/IE/FR, not only German domiciled. The "How it works" page says prices are published Mon-Fri 8:00-18:00, search is free, fund profile has basic data, documents, "historical price data", and "Starting at 6:00 pm on the day of publication, you can download in Fondsdata a list of all fund prices published on an up-to-date basis in CSV format"; paid customised packages via datenservice@bundesanzeiger.de. — [Fondsdata how it works](https://www.bundesanzeiger.de/pub/en/howto-fondsdata)
- Daily CSV VERIFIED: link `https://www.bundesanzeiger.de/pub/en/fondsdata?0--teaser~list-2-teaser-fund~daily~csv~panel-csv~resource~link` (needs a session cookie from the page first) returned `Content-Disposition: attachment; filename="tagesaktuelle_preise_2026-11-17.csv"`, 50,552 bytes, 404 lines, UTF-8 BOM. Header: `"Fondspreis vom","Fondsname","ISIN","WKN","Investmentgesellschaft","Waehrung","Ruecknahmepreis","Ausgabepreis","NAV"`; sample `"2026-11-17","AMUNDI EURO LIQUIDITY-RATED RESPONSIBLE","FR0014004701","","Amundi Asset Management","EUR","11.188,74","11.188,74","11.188,74"`. Numbers use German format (thousand dot, decimal comma). It contains only prices published that day (~400 funds), so history requires daily accumulation. Robots.txt only disallows /nlp, AhrefsBot and MJ12bot. Terms ("Legal / General Terms and Conditions" at /pub/en/legal) were fetched but my keyword scan for automation/scraping found nothing relevant; UNVERIFIED conclusion on automated use. — [Fondsdata](https://www.bundesanzeiger.de/pub/en/fondsdata)

**Official sources not yet used**
- BaFin Investmentfonds-Datenbank (public database of Publikums-Investmentvermoegen with distribution in Germany under KAGB sections 294/310/316/320 and domestic depositaries): portal `https://portal.mvp.bafin.de/database/FondsInfo/`, letter lists `sucheFonds.do?letterFonds=A` and CSV export `sucheFonds.do?d-16544-e=1&letterFonds=A&6578706f7274=1` VERIFIED (Content-Disposition export.csv, `;`-separated). Header: `BaFin-Id;Fonds;Land;Struktur;Umbrella;Auflegungsdatum/ Vertriebsbeginn;Fondsart;Verwalt. Ges.;Repraesentant;ISIN`. All 26 letters fetched: 21,611 rows; Land: Deutschland 8,794, Luxemburg 7,271, Irland 4,038, Oesterreich 473, Frankreich 444, Liechtenstein 319, Schweiz 76; Struktur: Einzelfonds 10,020, Teilfonds 10,242, Umbrella 1,349; ISIN non-empty on 6,632 rows only; Fondsart includes EU-OGAW 12,527, OGAW 1,893, special AIFs. Note the "Deutschland" list includes Spezial-AIF (institutional), so it is wider than retail. Verwaltungsgesellschaft shown as name in CSV; detail pages give share-class ISINs (`anteileInfo` css hints; UNVERIFIED). The BaFin page says the database is updated daily and export to CSV/XML is possible. Terms: BaFin Nutzungsbedingungen VERIFIED: content may generally be stored, passed on and reproduced "only with clear indication of source: (c) Bundesanstalt fuer Finanzdienstleistungsaufsicht / www.bafin.de"; third-party content excepted. — [BaFin database page](https://www.bafin.de/DE/die-bafin/publikationen-daten/datenbanken-uebersichten/investmentfonds/investmentfonds_node.html); [BaFin terms](https://www.bafin.de/DE/service/nutzungsbedingungen/nutzungsbedingungen_node.html)
- Deutsche Boerse / Xetra: `t7-xetr-allTradableInstruments.csv` VERIFIED (4.9 MB, "Date Last Update: 17.11.2026"), columns include Product Status, Instrument, ISIN, WKN, Mnemonic, MIC, Instrument Type; Instrument Type counts: ETF 3,182, ETN 389, ETC 206, CS 1,752 (first 100 rows scanned for type; counts across file). Gives ISIN/WKN/ticker for ETFs, not NAV. Free, no auth. Monthly ETF/ETP statistics XLSX on the cash market page (e.g. 20261031-ETF-ETP-Statistic.xlsx) are aggregates. — [Xetra downloads](https://www.cashmarket.deutsche-boerse.com/cash-en/trading/Tradable-Instruments-Xetra/Downloads)
- Boerse Frankfurt (live.deutsche-boerse.com/en/etfs reachable 200) fund price pages: exchange prices, not NAV; no free bulk feed verified. UNVERIFIED; Boerse Stuttgart/Hamburg not checked.
- Bundesbank: `https://www.bundesbank.de/en/statistics` reachable (200). Prior import doc cites investment-fund statistics (monthly aggregates, CSV time series) and the REST API `api.statistiken.bundesbank.de` (my probes: 406 without right Accept header, 404 on unknown flow; usable only for aggregates). No fund-level data. UNVERIFIED for series ids.
- BVI (bvi.de): connection failed from this host (HTTP 000 on both bvi.de URLs), so UNVERIFIED; BVI publishes aggregate statistics and performance method; no fund-level machine-readable open file known.
- KVG price files: DWS (funds.deutsche-am.com reachable), Allianz GI (regulatory.allianzgi.com reachable; ETL already uses its Luxembourg JSON for LU), Union Investment (404 on /fonds/), Deka fondsfinder (connection failed). No free ISIN price file verified except Allianz (already integrated for LU). UNVERIFIED. Issuer-official, not regulator.
- ESMA registers/FIRDS: other researcher; note that German-marketed funds appear in ESMA UCITS register under home states (mostly LU/IE) and BaFin lists 444 French and 76 Swiss funds, so DE "country" in our DB should be split into domicile DE vs marketed-in-DE.

**Field matrix Germany**
| Field | Official source | Status |
|---|---|---|
| Identity, LEI, manager name, address, policy, open/closed | BdE list | integrated |
| BaFin-ID, Verwaltungsgesellschaft, launch/distribution date, Fondsart, structure, umbrella | BaFin CSV | VERIFIED, unused |
| ISIN | BaFin CSV (6,632/21,611) + Fondsdata CSV; BdE has none | partial |
| Daily NAV (latest) with offer/bid | Bundesanzeiger daily CSV (~400/day) | VERIFIED |
| NAV history | Fondsdata per-fund profile "historical price data" (UNVERIFIED), else accumulate daily | partial |
| Ticker/WKN | Xetra allTradableInstruments (listed ETFs); Fondsdata WKN | VERIFIED |
| Currency | Fondsdata CSV | VERIFIED |
| Category | BdE investment policy (Equities/Mixed/Real estate/Other); BaFin Fondsart (legal type only) | coarse |
| Depositary | BaFin Verwahrstellen list (UNVERIFIED mapping to fund) | partial |
| Net assets, TER, SRI, benchmark, holdings, distributions | no official bulk source found (KID/annual reports in Bundesanzeiger as documents) | gap |

### Inferences
- Germany cannot reach Twelve Data parity officially: ISIN and NAV can come from BaFin + Fondsdata daily CSV; the Fondsdata CSV carries ISINs (including LU/IE/FR) that can enrich those funds' NAV across countries too.
- Matching BdE (no ISIN) to BaFin (name + Verwaltungsgesellschaft + BaFin-ID) is name-based, LEI is not in BaFin.
- Run the Fondsdata daily CSV job every evening after 18:00 CET and store NAV by date to build history from now.

### Gaps
- Fondsdata terms on automated download not confirmed; per-fund history endpoint not tested; BVI, Deka, Union, Bundesbank series pages not reached/verified; BaFin per-fund share-class pages not fetched.

---

## Q3. SWITZERLAND: integrated sources, why they under-deliver, and every unused official source

### Takeaway
FINMA's PDF parser captures only name and FINMA-ID although the XLSX of the same list has manager, custodian, legal form and fund type; SIX ref.json yields 49 listed funds (47 CH) and 2,334 ETFs but the connector uses only ProductLine=IF; Swiss Fund Data (the real full-universe platform) forbids systematic extraction, so full Swiss NAV coverage requires a licence from SIX or issuer-by-issuer official files.

### Cited Findings

**Integrated**
- finma.py parses `https://www.finma.ch/~/media/finma/dokumente/bewilligungstraeger/pdf/afch.pdf` (1.16 MB, sha256 915ee811...; 150-page landscape) with pypdf layout mode, regex `F\d{8}`; stores name + FINMA-ID; currency, isin, manager, depositary all None. 2,054 DB funds, NAV 0 (47 NAV come from SIX). — app/connectors/finma.py
- ch_six_fund_explorer.py queries `https://www.six-group.com/fqs/ref.json?select=...&where=ProductLine=IF&pagesize=99999`. VERIFIED today: totalRows 49 (47 CH + 2 NL by LegalStructureCountryCode); sample `["CH0002769351","UBS (CH) Property Fund - Swiss Commercial \"Interswiss\"","CHF",199,20261117,"CH","Real Estate","UBS Fund Management (Switzerland) AG"]`; response states `delayMinutes 15` and `(c) Copyright by SIX Group Ltd 2026. All rights reserved.` ClosingPrice is the exchange close of a listed (mostly real-estate) fund, not the daily NAV. The response header has `requestURL: /itf/fqs/delayed/ref.json`, i.e. a delayed-data gateway; licence for reuse not stated (rights reserved), so ETL status "Public; terms to confirm" is accurate. — [SIX fqs ref.json](https://www.six-group.com/fqs/ref.json?select=ISIN&where=ProductLine=IF)
- SIX ref.json with `select=*` returns 334 columns including FundBloombergTicker, FundReutersTicker, FundCurrency, FundLongName, IssuerLongNameDesc, LegalStructureCountryCode, ProductLine, AssetClassDesc, DividendFrequencyCode, ClosingPrice, FirstTradingDate etc. ProductLine ET (ETFs) returns 2,334 rows: IE 1,617, LU 472, CH 67, FR 20, DE 17, NL 4 (VERIFIED). ProductLine ETF/ETP/MF/FD return 0. — own probe

**Unused official sources**
- FINMA XLSX: `https://www.finma.ch/en/~/media/finma/dokumente/bewilligungstraeger/xlsx/afch.xlsx?sc_lang=en` VERIFIED (HTTP 200, 311 KB, 2,017 sheet rows, inline strings). Title "Genehmigte schweizerische kollektive Kapitalanlagen"; sections "Offene kollektive Kapitalanlagen (Art. 8 KAG)". Columns: `Name Einzelfonds bzw. Teilvermoegen | Name Umbrella | FINMA-ID | Fondsleitung | Depotbank | vertraglich | SICAV | SICAF | KmGK | Effektenfonds | Immobilienfonds | Uebrige Fonds fuer traditionelle Anlagen | Uebrige Fonds fuer alternative Anlagen | Qualifizierte Anleger`. Sample: `1741 CH Mid-Small-Cap, F00156731, 1741 Fund Solutions AG, Bank Julius Baer & Co. AG, X (vertraglich), X (Effektenfonds)`. FINMA's page links the same list as PDF/XLSX for other registers too (beh, raiff, uvvreg csv). No ISIN or NAV. Terms: FINMA page legal notice not read. — [FINMA authorised institutions](https://www.finma.ch/en/finma-public/authorised-institutions-individuals-and-products/)
- Swiss Fund Data (SIX Financial Information, FINMA-recognised publication platform): disclaimer VERIFIED (German). Exact wording: "Professionelle Marktdatenvertreiber duerfen die auf dieser Website zur Verfuegung gestellten Daten nicht verwenden, systematisch extrahieren, scrapen oder kommerziell verwerten. SIX FI bietet eine breite Palette lizenzierter Marktdatendienste an." and "Jegliche Vervielfaeltigung, Uebertragung ..., Aenderung, Verknuepfung, Framing oder Nutzung der Website oder ihres Inhalts fuer oeffentliche oder kommerzielle Zwecke bedarf der vorherigen schriftlichen Zustimmung von SIX FI. Die Rechte an ... Dokumenten oder Daten verbleiben bei den jeweiligen Rechteinhabern." Compliant use: manual look-ups for individuals; any automated/commercial ingestion needs a written SIX FI licence (contact via the site's "Dienstleistungen" / data products). robots.txt at /robots.txt 404 (the /sfdpub/robots.txt URL returned the SPA). Data scope: all publicly distributed Swiss CIS plus foreign funds approved for Switzerland, with documents (KIID/prospectus), statistics, NAV, performance, TER, risk. — [Swiss Fund Data](https://www.swissfunddata.ch/sfdpub/sfd-eingang)
- SIX Swiss Exchange ETF/fund reference via fqs ref.json (ET: 2,334 ISINs, tickers, currency, issuer). Same copyright caveat.
- SFAMA/AMAS (sfama.ch redirects to a 1.3 KB page; amas.ch unreachable, HTTP 000): UNVERIFIED. SFA also runs the "SFA ARI" real-estate indicator on Swiss Fund Data. SNB data portal (data.snb.ch) reachable; aggregate banking/CIS statistics only, not fund-level. UNVERIFIED for series.
- Issuer official files: UBS (HTTP 403 from this host), ZKB (reachable; no file found), Vontobel/Pictet/Julius Baer/Lombard Odier: not fetched. UNVERIFIED; no machine-readable official price file located.
- ESMA/FIRDS: BaFin lists 76 Swiss-country entries; Swiss funds are mostly outside ESMA UCITS passport; other researcher covers.

**Field matrix Switzerland**
| Field | Official source | Status |
|---|---|---|
| Name, umbrella, FINMA-ID | FINMA XLSX/PDF | integrated (PDF) |
| Manager (Fondsleitung), custodian (Depotbank) | FINMA XLSX | VERIFIED, unused |
| Legal form (contractual, SICAV, SICAF, KmGK), fund type (securities, real estate, other traditional/alternative), qualified-investor flag | FINMA XLSX | VERIFIED, unused |
| ISIN, ticker, currency, last exchange price | SIX ref.json (IF 49 + ET 2,334 incl. 67 CH ETFs) | VERIFIED; licence unclear |
| Daily NAV, history, net assets, TER, SRI, benchmark, distributions, holdings | Swiss Fund Data (licence required), issuers | not obtainable under public terms |
| Category | FINMA type flags; SIX AssetClassDesc | coarse |

### Inferences
- Replace FINMA PDF parsing with XLSX (simple, stable) and add manager/custodian/legal form/type fields. Still no ISIN: matching FINMA-ID to ISIN needs SIX/Swiss Fund Data/issuer data; name matching only for listed funds.
- Swiss NAV coverage will stay thin on free official data: realistic path is to ask SIX FI for a licence for Swiss Fund Data / fund data feed, or accept listed-fund subset (47 + 67 ETFs).

### Gaps
- SIX licence terms for ref.json and fund-explorer not found beyond "All rights reserved". SFAMA/AMAS pages not reachable; SNB series ids and issuer files not verified; FINMA legal notice for the XLSX reuse not read.

---

## Q4. Cross-border, bulk vs per-fund, auth, rate limits and a concrete connector design

### Takeaway
Only GECO offers a free per-share NAV API for any of the three countries; Germany offers daily price list + register exports; Switzerland has an official list but licensed NAV. Design: one GECO-centred FR connector, a BaFin + Fondsdata DE connector with daily accumulation, and a FINMA-XLSX + SIX-ET CH connector.

### Cited Findings
- Bulk vs per-fund: FR GECO list = bulk (1 POST, 72 MB); NAV = per share (~20k+ calls). DE BaFin = bulk CSV by letter (26 calls); Fondsdata CSV = bulk daily; Xetra instruments = bulk CSV. CH FINMA XLSX = bulk; SIX ref.json = bulk (single call). — verified above
- Auth: none for any verified endpoint; Bundesanzeiger CSV needs a cookie from the Fondsdata page first; GECO requires `Origin` and `Referer` headers of geco.amf-france.org (I sent them) and returns `Access-Control-Allow-Origin` for that origin only. — verified above
- Rate limits: none observed/published; GECO full-history call took 7.5 s, `Connection: close`. No 429s seen in ~60 GECO calls. — own probe
- Robots: bundesanzeiger.de only disallows /nlp and two bots; lacotebleue disallows SemrushBot; GECO and SIX fqs have no robots file found; swissfunddata terms forbid scraping for market-data distributors.
- Cross-border: BaFin's DB shows funds with home states LU/IE/FR/CH marketed in DE; Fondsdata daily CSV contains LU and FR ISINs (e.g. Amundi FR0014004701, ABN AMRO LU...). Prefix-based domicile (ISIN FR/DE/CH) is therefore not equal to "marketed in DE"; SIX ET list includes IE/LU/FR/DE ETFs. ESMA/FIRDS endpoints left to the other researcher.

### Connector design (concrete)
1. `fr_amf_geco_share_nav` (new, replaces fr_lacotebleue):
   - Step A: reuse cached `geco_compartments.json`; keep all statuses (store status VIV/SLD/ECL), fix the connector to also emit manager=`gestionnaire`, administrator/depositary=`nomDepositaire`, category=`cmpClssFndAmfLib`, fund_type=`prdSsNatureLib`/`prdNatureLib`, inception=`cmpDateCreation`, LEI, liquidation date, labels (ELTIF/EuVECA/EuSEF).
   - Step B: for each cmpId call `/compartment/{cmpId}/shares` -> per share ISIN, share class name `parNom`, currency `parRefDevCode`, `parAffctnRevnuLib` (acc/dist), share creation date, parId. Handle shares without ISIN (use parId/`codeExt` e.g. AMF100030471).
   - Step C: for each parId call `/vlsCouponsAndOst/{parId}?startDate=...&endDate=...`; initial backfill from 1990-01-01, afterwards incremental from last stored `valuationDate - 7d` (revisions: `cancellation`, `modificationDate`); write nav_observations (netAssetValue, quotationCurrency), net_assets=assetUnderManagementK, shares_outstanding=shareNumber into fund_profile_snapshots, coupons into a distributions table/payload, corporateActionDTOS into events.
   - Politeness: 2 concurrent requests, 0.5 s delay, resume checkpoint, send `Origin`/`Referer`, cache raw JSON; identify AMF as source; request written reuse confirmation from AMF.
   - Priority: OPCVM (3,571) then FIA (11,384).
2. `de_bafin_investmentfonds` (new): iterate letters A-Z (+ "Andere" untested) per session cookie, export CSV, parse `;` and German dates; map BaFin-Id, Verwaltungsgesellschaft, Land (domicile), Struktur, Umbrella, Fondsart, launch date, ISIN; attach attribution "(c) BaFin / www.bafin.de". Join to BdE rows by LEI/name for DE-domiciled funds.
3. `de_bundesanzeiger_daily` (rewrite): evening job (after 18:00 CET Mon-Fri): GET fondsdata page for cookie, GET the csv link, parse ISO date, German numbers (`11.188,74`), store NAV + offer/bid, ISIN, WKN, provider, currency; no domicile guess other than BaFin join. Optionally test the per-fund "historical price data" page for backfill (UNVERIFIED) and ask datenservice@bundesanzeiger.de for a licence if history is needed.
4. `de_xetra_instruments` (new, optional): download t7-xetr-allTradableInstruments.csv daily; filter Instrument Type ETF/ETN/ETC; fill ISIN, WKN, mnemonic (ticker), MIC.
5. `ch_finma_xlsx` (replace PDF parse): parse afch.xlsx (inline strings; note blank columns D/E; X flags in legal-form and type columns); fields manager=Fondsleitung, custodian=Depotbank, legal form, type -> category, qualified-investor flag -> target_audience; keep PDF as fallback.
6. `ch_six_fqs` (extend): add ProductLine=ET filtered by LegalStructureCountryCode=CH (and FR/DE ETFs for those countries), request FundBloombergTicker, DividendFrequencyCode, FirstTradingDate; store ClosingPrice as exchange price, not NAV; keep status "licence to confirm". Treat Swiss Fund Data as off limits without SIX FI licence.
7. Aggregates (optional QA): Banque de France IVF1 CSV, Bundesbank API, SNB, AFG monthly stats for country totals.

### Inferences
- Expected gain: FR NAV from 90 to most of ~20k live shares; FR manager/category/inception/depositary on ~13k live compartments; DE ISIN +6.6k and NAV ~400/day accumulating; CH manager/custodian/type for ~2,000 funds, ISIN/NAV limited to ~47 + 67 listed.
- Twelve-Data parity for TER, SRI, benchmark, holdings is out of reach with open official data in all three countries; KID PDFs (GECO documents, Swiss Fund Data, Bundesanzeiger) are the only official carriers and require parsing and licensing checks.

### Gaps
- Licences: GECO, Fondsdata automation, SIX fqs, FINMA XLSX not confirmed in writing.
- Not reachable from this host: bundesbank.de/en root, bvi.de, amas.ch, fondsfinder.deka.de; unverified: Euronext ETF list, issuer files, GECO document/KID endpoints, BaFin per-fund share-class pages, "Andere" BaFin letter.
- No official source found for fund holdings in any of the three countries.
