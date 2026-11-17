# Official public fund data sources: Americas excluding the US (Nov 2026)

Method note: about 17 tool calls. Search snippets were summarised by the search tool, not raw. dados.cvm.gov.br returned HTTP 403 / Cloudflare "Sorry, you have been blocked" to both WebFetch and curl from this host (IP 103.171.50.128), so CVM directory listings and the data dictionaries could NOT be opened directly (this is itself a finding for the ETL: CVM needs a browser-like UA/cookie or a different egress IP). cmfchile.cl and cnbv.gob.mx fetches failed (DNS / TLS certificate error). Anything marked UNVERIFIED comes from my background knowledge, not from a fetched page; the report writer should treat it as a lead to check, not a fact.

Already integrated (read from /media/asim/4_TB_1/MFAPI/MF ETL PIPELINE/app/catalog.py and app/connectors/):
- BR: `cvm_open_fund_data` (inf_diario + registry; the catalog text says CDA holdings are imported via `sync-cvm-holdings`, but the DB snapshot shows 0 BR holdings, so the CDA import has not landed in the DB or is not matched).
- CA: `scotia_canada_daily_nav` (373 rows only).
- MX: `bmv_mexico_funds` (5,151 series) and `cnbv_fund_statistics` (registered as aggregate stats only, "granular format needs checking").
- No connector or catalog row exists for AR, CL, CO, PE, UY, CR, PA or any other Americas country (catalog country list for the Americas is US, CA, MX, BR).

## 1. Brazil: CVM sources to fill NAV, holdings, ISIN, inception gaps

### Takeaway
CVM open data (ODbL) is the right and sufficient official source for Brazil: registry (with inception date, manager, administrator, custodian, class), daily NAV, monthly portfolio (CDA, with per-position ISIN/CUSIP/SELIC codes), monthly profile, and the essential-information sheet (lâmina, with fees and risk). ISIN at fund level is not a CVM registry field in anything I could confirm; Brazilian fund quotas rarely have ISINs, so ISIN is realistically available only at holding level (CDA) and via B3/ANBIMA for a subset.

### Cited Findings
- Registry dataset `fi-cad`: file registro_fundo_classe.zip contains registro_fundo.csv, registro_classe.csv, registro_subclasse.csv (post Resolução CVM 175). registro_fundo also includes funds not yet adapted to RCVM 175. registro_classe has ID_Registro_Fundo, ID_Registro_Classe, CNPJ_Classe, Codigo_CVM. CNPJ remains the main identifier; subclasses get a CVM code. — [CVM dataset resource](https://dados.cvm.gov.br/dataset/fi-cad/resource/0fa5380d-7ff6-4aac-b000-80f38a9087f1), [CVM novidades](https://dados.cvm.gov.br/pages/novidades)
- Breaking change: a 26/01/2026 notice says TP_FUNDO became TP_FUNDO_CLASSE and CNPJ_FUNDO became CNPJ_FUNDO_CLASSE in all files (this can silently break a connector keyed on CNPJ_FUNDO). The notices conflict about whether the registro_fundo_classe URL or a contingency URL registro_fundo_classe_.zip is current. — [CVM novidades](https://dados.cvm.gov.br/pages/novidades)
- CDA (portfolio composition): dataset `fi-doc-cda`, monthly ZIPs, URL pattern `https://dados.cvm.gov.br/dados/FI/DOC/CDA/DADOS/cda_fi_202605.zip`; blocks follow the CDA XML (Bloco 1 Selic government bonds, Bloco 2 fund quotas, Bloco 3 swaps, further blocks for other asset types; I could not confirm BLC_4-8 contents). Confidential positions are shown consolidated in cda_fi_CONFID_AAAAMM.csv. M-1..M-3 files are refreshed daily for resubmissions; history from 01/2021 in the refreshed set, plus files from 2005. — [CVM CDA dataset](https://dados.cvm.gov.br/dataset/fi-doc-cda) (via search summary), [CVM CDA May 2026 resource](https://dados.cvm.gov.br/dataset/fi-doc-cda/resource/11481741-919c-4652-b937-d3e7b625f59f)
- File rename from 15/11/2025: notices say files will be renamed to cda_fie_AAAAMM.csv / cda_fie_CONFID_AAAAMM.csv; index funds (FIIM) from 06/2018 are in cda_fiim_AAAAMM.csv, and FIDC/FIAGRO were added to cda_fiim files. A connector hard-coded to cda_fi_BLC_* may miss these. Verify the exact current names against the ZIP contents. — [CVM CDA dataset](https://dados.cvm.gov.br/dataset/fi-doc-cda)
- Lâmina (essential information sheet): dataset `fi-doc-lamina`, ODbL, monthly ZIP e.g. `https://dados.cvm.gov.br/dados/FI/DOC/LAMINA/DADOS/lamina_fi_202604.zip`; the listing covers Aug 2025 onward; a data dictionary exists. Directory /dados/FI/DOC/ also contains INF_DIARIO/, CDA/. — [CVM lâmina dataset](https://dados.cvm.gov.br/dataset/fi-doc-lamina), [Lâmina Apr/2026 resource](https://dados.cvm.gov.br/dataset/fi-doc-lamina/resource/2baa27d8-2cfc-4fe1-beb5-f9f89c374f14)
- CVM base inventory PDF lists all open datasets. — [Inventário de bases CVM](https://dados.cvm.gov.br/misc/InventarioBasesCVM.pdf)
- Date caveat: search results show page dates inconsistent with Nov 2026 (items labelled Aug/Sep 2026), so check which months really exist.

UNVERIFIED (background knowledge, could not fetch): `inf_diario_fi_AAAAMM.zip` under /dados/FI/DOC/INF_DIARIO/DADOS/ (fields DT_COMPTC, VL_QUOTA, VL_PATRIM_LIQ, CAPTC_DIA, RESG_DIA, NR_COTST; monthly, history back to 2000, plus a HIST/ folder of yearly files); `perfil_mensal_fi_AAAAMM.csv` under /dados/FI/DOC/PERFIL_MENSAL/DADOS/ (investor-type breakdown, liquidity, VaR, stress, leverage, derivatives); legacy `cad_fi.csv` under /dados/FI/CAD/DADOS/ (DT_REG, DT_CONST, DT_INI_ATIV, ADMIN, GESTOR, CUSTODIANTE, CLASSE, CLASSE_ANBIMA, TAXA_ADM, TAXA_PERF, BENCHMARK-like field DS_BENCH/ INDEX), which carries inception and fee fields; this explains why the DB has many BR rows without inception date (the new registro_* files use DT_REGISTRO / DT_CONSTITUICAO fields, UNVERIFIED names). CVM also exposes join key CNPJ_FUNDO_CLASSE across inf_diario, cda, perfil, lâmina.
- Join key: CNPJ (14 digits) for fund/class; CVM code (CD_CVM / Codigo_CVM) secondary; ISIN only on CDA holding rows (field CD_ISIN) and some Selic/B3 codes (CD_SELIC, CD_ATIVO).
- Fund count: DB has 37,875 BR funds; registry holds more incl. cancelled. NAV missing for about 12,000 is expected: many are cancelled/FIDC/FIP/FII-type or not daily-reporting; do not treat as a data gap until filtered by situation (SIT = EM FUNCIONAMENTO NORMAL).
- Licensing: ODbL per CVM catalogue; no authentication. Robots/terms: not retrievable (blocked).

### Other Brazil official/semi-official sources (UNVERIFIED unless noted)
- ANBIMA (official industry association, but data feeds mostly paid/registration-gated): fund classification, ISIN-like "código ANBIMA", and fund pages at data.anbima.com.br. The ANBIMA public API requires credentials. Treat as restricted.
- B3 publishes ISIN for listed FII/ETF/FIDC; B3 ISIN file via the instruments consolidated file (public CSV/ZIP). UNVERIFIED.

### Inferences
- The zero-holdings state of BR is probably a pipeline problem (CNPJ rename to CNPJ_FUNDO_CLASSE, cda_fi to cda_fie rename, or class-vs-fund CNPJ mismatch under RCVM 175), because the official CDA exists and is already referenced in catalog.py. Also the Cloudflare block seen here may affect the ETL host.
- Fund-level ISIN for BR is unlikely to be fillable from official sources except for listed vehicles.

### Gaps
- Could not open any CVM listing, data dictionary or CSV header (403 Cloudflare). Exact column names for registro_*, BLC_*, perfil_mensal and lâmina are therefore unconfirmed; row counts unknown.
- Could not confirm BLC_4-8 mapping or whether holdings carry CNPJ of the investee fund.

## 2. Mexico: CNBV / BMV / Condusef / AMIB / price vendors

### Takeaway
Mexico has official regulatory reports (CNBV "CUFI" series R13/R14/R24 incl. B-1422 prices and C-1331 portfolio valuation) but I found no public bulk download of them; public per-fund data is exposed through the CNBV "Buscador de Sociedades de Inversión" and the BMV fund pages, and the monthly/weekly portfolio composition file is published per fund by operators/BMV. Valmer is a price vendor (commercial), not an official publisher.

### Cited Findings
- CNBV Buscador de Sociedades de Inversión shows fund characteristics, portfolio composition, fees and expenses, historical return and value-at-risk, with a comparator showing sector distribution for up to four funds. No download link or terms confirmed (page fetch failed on TLS). — [CNBV buscador](https://www.cnbv.gob.mx/SECTORES-SUPERVISADOS/SOCIEDADES-DE-INVERSION/Buscador-de-Sociedades-de-Inversi%C3%B3n/Paginas/Buscador-de-Sociedades-de-Inversion.aspx)
- CNBV sector menu has "Información Estadística" and "Bases de Datos" entries; contents unconfirmed. — [CNBV Descripción del Sector](https://www.cnbv.gob.mx/SECTORES-SUPERVISADOS/SOCIEDADES-DE-INVERSION/Paginas/Descripci%C3%B3n-del-Sector.aspx)
- BMV fund page shows weekly and monthly "Composición de la Cartera" downloadable per fund. — [BMV Fondos](https://www.bmv.com.mx/es/Grupo_BMV/fondos)
- Regulatory report specs (CUFI): R14 B-1422 "Precios y operaciones de compra-venta de acciones de fondos de inversión"; R13 C-1331 portfolio valuation; R24 "Reportes de información al público" (IP-IN, monthly for equity and debt funds). These are filings to CNBV, public availability not confirmed. — [B-1422 spec](https://www.gob.mx/cms/uploads/attachment/file/311561/FI_R14_B-1422_Precios_y_operaciones_de_compra-venta_de_acciones_de_fondos_de_inversi_n__VA-AC__Vigencia_desde_201804_Actualizaci_n_26_Marzo_2018.pdf), [R24 spec](https://www.gob.mx/cms/uploads/attachment/file/766853/FI_R24_Reportes_de_informaci_n_al_p_blico_Vigencia_202201-actual_Actualizaci_n_10_octubre_2022.pdf), [Carteras de Valores spec](https://www.gob.mx/cms/uploads/attachment/file/174445/DCGEF_y_AI_R03_J-0311_SI__Carteras_de_Valores__201612.pdf)
- Valmer appears as price provider in fund documents and publishes benchmark index constituents on valmer.com.mx; no public price dataset confirmed. Roles of PiP and AMIB as price publishers not confirmed. — [Actinver DICI](https://portal.actinver.com/documents/d/actinver/dici_valor-2)
- Operator-published monthly prospectus/DICI PDFs (Actinver, BBVA, Monex) carry the fund's benchmark, risk rating, fees, custodian/distributor; PDFs only. — [Monex prospectus](https://www.monex.com.mx/portal/download/fondos2/Nvo%20Prosp_gen_rv%20Jun%2026%20GBMCRE.pdf)
- Existing BMV connector: 5,151 series, ISIN not in BMV JSON per catalog, but DB shows isin on 5,151 (so ISIN is somehow filled, likely from a mapping; verify).

### Inferences
- Realistic Mexico gap-fillers: (a) CNBV buscador JSON/HTML backend (needs devtools inspection; terms unknown), (b) BMV per-fund composition files, (c) operator sites. All are scraping-grade rather than bulk-open-data.

### Gaps
- No confirmed CNBV open-data CSV for series-level NAV, holdings, administrator or inception. Condusef (consumer regulator) and AMIB had no confirmed fund data in my searches. Fund counts and licence terms unconfirmed.

## 3. Canada

### Takeaway
There is no free official bulk API for Canadian fund data. SEDAR+ (CSA) holds Fund Facts and filings per fund but bulk delivery is a paid CSA Data Delivery Service; commercial aggregators (Fundata, QuoteMedia, TMX) are the usual route. Official free data is per-manager (like the Scotia workbook already integrated).

### Cited Findings
- CSA describes a paid Data Delivery Service giving access to SEDAR+ public company and investment-fund filings and disclosure data; pricing/terms not found. — [CSA](https://www.securities-administrators.ca/2025-02-sedar-updates)
- No documented public SEDAR+ developer API (claim from a third-party listing, secondary). — [parse.bot listing](https://www.parse.bot/marketplace/da9daab6-7d21-4c5e-a432-fddea32946fa/sedarplus-ca-api)
- Fund Facts are filed per fund on SEDAR+. — [CSA guide](https://systems.securities-administrators.ca/sedar_experience-guides_investment-fund-filings)
- COMMERCIAL (not official): Fundata aggregates Fund Facts from manufacturers/SEDAR with an API; QuoteMedia and TMX Infoservices offer fund/filing data. — [Fundata](https://www.fundata.com/fund-facts), [QuoteMedia](https://brochures.quotemedia.com/pdfs/Fund-Research.pdf), [TMX](https://tmxinfoservices.com/corporate-and-reference-data/corporate-disclosure)

UNVERIFIED leads: IFIC publishes only industry aggregates (monthly assets/sales) not fund-level data; major banks/managers (RBC GAM, TD, BMO, CIBC, Fidelity Canada, Mackenzie, Manulife, Dynamic) publish daily price downloads (CSV/XLS) and quarterly top-10 holdings / full portfolio disclosure, plus Fund Facts PDFs. Canadian ETFs list holdings daily as CSV on issuer sites (iShares Canada, BMO ETFs, Horizons). Identifiers: fund codes (e.g. RBF460), ISIN for ETFs, CIFSC category (CIFSC is a not-for-profit committee, classification published by Fundata/Morningstar). Individual manager URLs were not fetched.

### Inferences
- Best path to grow CA from 373 funds: add several manager-official daily-price files (same pattern as Scotia) and ETF issuer holdings CSVs; treat SEDAR+ as manual-only.

### Gaps
- No confirmed URLs for other managers' downloads; no confirmed licence for CSA DDS; no verified IFIC fund-level data.

## 8. NEW vs already integrated, and Twelve Data overlap

### Takeaway
Only BR/CA/MX are integrated. New candidates in priority order: Argentina (CAFCI), Chile (CMF), Colombia (SFC F-523), then Peru/Uruguay/Costa Rica (weak). Overlap with Twelve Data mutual-fund fields is highest for Brazil CVM and Argentina CAFCI.

### Cited Findings and mapping (field coverage is as documented above; Twelve Data comparison is based on the field list in the assignment, not on Twelve Data docs which I did not fetch)
- BR CVM: price (VL_QUOTA), AUM (VL_PATRIM_LIQ), holdings with ISIN/CUSIP (CDA), manager/admin/custodian, fees and risk (lâmina), distributions not confirmed. No sector allocation (derivable from CDA blocks).
- MX CNBV/BMV: price, classification, composition by sector, fees, VaR/risk; manager from BMV (operator).
- AR CAFCI (unverified details): price, manager, custodian, benchmark, risk profile, fees, AUM, performance.
- CL CMF: price per series, AGF; performance report.
- CO SFC F-523: unit value, returns, manager.
- CA SEDAR+ / manager sites: Fund Facts (fees, risk rating, top 10 holdings, performance); official bulk not free.

### Inferences
- ISIN, ticker and sector allocation will remain mostly Twelve-Data-only for Americas funds; official LatAm sources key on national codes (CNPJ, CAFCI IDs, RUN, SFC codes), not ISIN.

### Gaps
- No Twelve Data documentation was consulted; overlap statements are structural, not tested.

## Recommended verification checklist (for the human/ETL owner)
1. From a browser or allowed IP, open https://dados.cvm.gov.br/dados/FI/DOC/CDA/DADOS/ and an inf_diario ZIP; record real file names, headers (CNPJ_FUNDO_CLASSE vs CNPJ_FUNDO, cda_fie vs cda_fi) and diff against the connector.
2. Inspect network calls on cafci.org.ar fund pages and CMF fondos mutuos portal to document actual endpoints and terms.
3. Request CSA Data Delivery Service pricing for SEDAR+.
4. Check cnbv.gob.mx "Bases de Datos" for downloadable files.
