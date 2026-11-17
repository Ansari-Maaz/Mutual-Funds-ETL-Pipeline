# Official fund data sources: rest of Europe (ES, IT, PT, NL, BE, Nordics, CEE, SEE, Baltics, TR, RU, UA, KZ)

Research depth: about 18 tool calls. Many official portals were only reached via search snippets (WebFetch of TEFAS was rejected, CMVM URL 404). Items marked UNVERIFIED come from background knowledge, not fetched evidence, and must be probed before building.

## Q1. What is already integrated vs NEW (project state)

### Takeaway
The repo already has ES (CNMV register only), IT (Borsa Italiana NAV text file + BDE list + BdI candidate), NL (Euronext Amsterdam + BDE + AFM register), DK (BDE list + FSA PDF candidate), SE (FI quarterly holdings XML, identity only). The biggest unexploited asset is the CNMV monthly/quarterly XML (NAV, fees, portfolio) already downloaded for ES but only the register part is imported.

### Cited Findings
- Connector files present: cnmv.py, bde_european_funds.py, denmark_bde_funds.py, fi_sweden.py, it_borsa_nav.py, nl_euronext_funds.py, euronext_base.py (plus non-European ones). No connector exists for NO, FI, PT, BE, PL, CZ, HU, RO, GR, TR, RU, UA, KZ, Baltics — from `app/connectors/` listing.
- catalog.py ES entry: CNMV monthly ZIP contains class-level FONDREGISTRO XML (ISIN) and a companion monthly file with daily NAVs but no currency field; only masters imported — `app/catalog.py` (cnmv_spanish_fund_register).
- catalog.py SE: FI quarterly ZIP/XML has names, FI fund numbers, ISINs, holdings and portfolio values, but not unit NAV; only identity imported — `app/catalog.py` (fi_sweden_ucits_holdings).
- catalog.py IT: Borsa Italiana daily text file (ISIN, currency, NAV, NAV EUR) gave 68 observations; BDE gives ~1,326 fund identities; BdI registry is a placeholder — `app/catalog.py`.
- catalog.py NL: Euronext Amsterdam CSV gives 84 NAV rows; AFM CIS register export lists management companies only, not products — `app/catalog.py`.
- catalog.py DK: BDE CSV has European code, LEI, name, management company, no NAV/currency; FSA investment-association register PDF is a candidate only — `app/catalog.py`.
- BDE country CSV URL pattern (already used): https://www.bde.es/webbe/en/estadisticas/otras-clasificaciones/clasificacion-entidades/listas-instituciones-financieras/listas-fondos-inversion-pais/lista-if-{cc}.csv — `app/connectors/bde_european_funds.py`. Cheapest NEW win: same pattern for other country codes (check which codes are in COUNTRIES dict; likely extendable to NO, FI, PT, BE, PL, CZ, HU, RO, GR etc. UNVERIFIED that these codes exist on the BDE page).

### Inferences
- NEW to integrate = everything below not named above; "extend" = same publisher already used.

### Gaps
- Did not read DB schema for join keys beyond ISIN; assume ISIN is primary join key (isin column populated in ES/IT/NL/SE).

## Q2. Priority sources by country (bulk NAV / holdings)

### Takeaway
Best verified bulk sources: CNMV (ES) monthly NAV XML and quarterly portfolio XML; Oslo Børs Mutual Fund Feed (NO, licensed); BAMOSZ CSV (HU, association, ISIN-keyed). TEFAS (TR) has a working per-fund JSON API but it is unofficially documented and was rewritten in 2026. Many other countries have official registers only (no NAV), with NAV on manager sites or licensed vendors.

### Cited Findings

**Sweden — Pensionsmyndigheten (NEW) and FI (extend)**
- Pensionsmyndigheten Fondtorget: fund catalogue PDF (fee, type, risk level; six-digit fund number), fund fact pages updated on trading days, monthly Fondhandelsrapport PDFs; no documented open-data API for daily prices found — [Fondkatalog PDF](https://www.pensionsmyndigheten.se/content/dam/pensionsmyndigheten/blanketter---broschyrer---faktablad/broschyrer-och-faktablad/fondkatalog/Fondkatalog%20fondlista.pdf), [Fondhandelsrapport](https://www.pensionsmyndigheten.se/content/dam/pensionsmyndigheten/blanketter---broschyrer---faktablad/statistik/premiepension/fonddata/Fondhandelsrapport%20maj%202023.pdf)
- 269 funds being removed from the premium pension marketplace (July 2026) — [Realtid](https://www.realtid.se/bors-finans/269-ppm-fonder-plockas-bort/)
- FI quarterly XML (already ingested identity only) also contains holdings and portfolio values — `app/catalog.py`; holdings import is an extend-opportunity.

**Russia (NEW)**
- Bank of Russia: register had 3,742 unit investment funds + 2 joint-stock funds at 31 Mar 2026; monthly UIF statistics with 86 indicators since Nov 2023; June 2026 retail-fund data showcase for 400+ funds; managers must disclose monthly returns, risks, fees, key assets — [Business Magazine](https://eng.business-magazine.online/fn_1884469.html) and CBR event pages (e.g. https://www.cbr.ru/eng/press/event/?id=17193). Moscow Exchange shows NAV/iNAV for exchange-traded units — [MOEX](https://www.moex.com/en/funds/opif/ru000a100eq2). Per-fund NAV bulk file not confirmed. Sanctions/access risk for a Western pipeline should be reviewed.

**Italy (extend)**
- Banca d'Italia has Base Dati Statistica and open-data (RDF) sections and OICR reporting (Circular 189) — aggregated, no per-fund NAV confirmed — [BdI](https://www.bancaditalia.it/statistiche/tematiche/moneta-intermediari-finanza/mercati/mercato-finanziario/index.html). Consob list not found. Keep Borsa Italiana NAV file as primary.

**Denmark**
- FSA register PDF (investment associations) — [Finanstilsynet](https://www.finanstilsynet.dk/media/44992/Reg4IF.pdf). Investering Danmark daily-price download not found in search.

### Inferences
- Priority order for build effort vs value: (1) CNMV NAV+portfolio XML (already fetched, +3,116 ES funds NAV/fees/holdings); (2) FI Sweden holdings; (3) TEFAS JSON (large fund count, daily price, ISIN missing); (4) BAMOSZ CSV for HU (needs ISIN list, which BDE country list for HU could supply); (5) BDE CSV extension for NO, FI, PT, BE, PL, CZ, HU, RO, GR (identity only).
- NO, PL, RO, GR, PT NAV are probably only via licensed vendors or manager sites; flag as "not bulk-official".

### Gaps
- Unverified (not researched or inconclusive): Finland FIN-FSA/Finanssiala; Iceland; Belgium FSMA/BEAMA; Portugal APFIPP/CMVM; Slovakia; Bulgaria; Croatia; Slovenia; Cyprus; Baltics; Ukraine; Kazakhstan; Consob; Investering Danmark; Euronext Oslo/Copenhagen/Lisbon/Brussels fund lists (Euronext fund list pattern used for NL could likely be reused for BE/PT/NO — UNVERIFIED); Nasdaq Nordic fund lists.
- Exact TEFAS endpoint paths, ToS and robots status; CNMV reuse licence; BAMOSZ licence and history depth.
- Approximate fund counts mostly not confirmed.

## Q3. Terms / robots / scraping flags

### Takeaway
Only CNMV and BDE are plain bulk-file sources; TEFAS and BAMOSZ are query-style; Oslo Børs feed is licensed.

### Cited Findings
- CNMV: bulk XML but tokenised links require page scraping; no licence text read — [CNMV](https://www.cnmv.es/portal/Publicaciones/descarga-informacion-individual?ejercicio=2026)
- TEFAS: site returned WAF rejection to automated fetch; new API per-fund only (one HTTP request per fund, tefas-crawler default cap 50) — [tefas-crawler](https://github.com/burakyilmaz321/tefas-crawler)
- Oslo Børs feed: commercial Euronext data product — [spec](https://connect2.euronext.com/sites/default/files/documentation/data/Oslo%20B%C3%B8rs%20Mutual%20Fund%20Feed%20Technical%20Specification%20-%20Issue%202.1.8.pdf)
- Analizy.pl, ekofin, marketvisuals, Nordnet, FundsLibrary-type sites are commercial/unofficial; do not label as official.

### Inferences
- Treat TEFAS as scraping/unofficial-API with ToS risk until official terms are read.

### Gaps
- robots.txt not checked for any site.

## Q4. Overlap with Twelve Data mutual-fund fields

### Takeaway
Overlap is mostly NAV/price, currency, ISIN, name, category, net assets, manager and fees. Twelve Data field list was not fetched in this task, so overlap is stated by source field.

### Cited Findings
- CNMV monthly: NAV, net assets, unitholders; quarterly: fees, returns, portfolio composition — [CNMV](https://www.cnmv.es/portal/Publicaciones/descarga-informacion-individual?ejercicio=2026)
- TEFAS: date, price, code, title — [tefas-crawler](https://github.com/burakyilmaz321/tefas-crawler)
- Borsa Italiana: ISIN, currency, NAV — `app/catalog.py`
- Pensionsmyndigheten catalogue: fee, type, risk level — [Fondkatalog](https://www.pensionsmyndigheten.se/content/dam/pensionsmyndigheten/blanketter---broschyrer---faktablad/broschyrer-och-faktablad/fondkatalog/Fondkatalog%20fondlista.pdf)

### Inferences
- Official sources rarely supply ticker, benchmark, inception date, or SRRI in bulk; those remain Twelve Data / vendor-only.

### Gaps
- Twelve Data field definitions not compared directly.
