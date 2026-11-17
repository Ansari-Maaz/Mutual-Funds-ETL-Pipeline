> Moved from 'americas.md' on 2026-11-18: these countries are outside the 24-country scope (US CA MX GB DE FR IT CH NL DK SE JP CN KR AU SG HK TW RU BR + LU IE AE ZA). Kept verbatim for possible later expansion.

# Americas outside scope: AR, CL, CO, PE, UY, CR, PA etc.

## 4. Argentina (NEW)

### Takeaway
CAFCI (the industry chamber, the official FCI price/statistics publisher, with CNV as regulator) is the key source. It publishes fund/class pages and daily cuotaparte values and an undocumented JSON backend that community tools use; the government datos.gob.ar offers only aggregate monthly/annual FCI series. NEW to the project.

### Cited Findings
- datos.gob.ar has an FCI dataset from the Subsecretaría de Programación Macroeconómica (annual and monthly CSV, primary source CAFCI), apparently aggregate rather than daily per class. — [datos.gob.ar](https://datos.gob.ar/dataset/sspm-fondos-comunes-inversion) (search snippet; direct fetch returned 404 on the URL I tried)
- CAFCI fund pages use `ficha-fondo.html?q=FUND_ID;CLASS_ID`; community scripts call the "CAFCI API" with fund id and class id; daily data tends to update after 21:00. No documented API, no auth noted. UNOFFICIAL wrapper. — [fedemoglia/cafci-api](https://github.com/fedemoglia/cafci-api)
- CAFCI publishes monthly industry summaries as PDFs, e.g. `https://cafci.org.ar/Publica/Estadistica/Resumenes/Mensual/20230101_Resumen_Industria.pdf`. — [CAFCI](https://cafci.org.ar/Publica/Estadistica/Resumenes/Mensual/20230101_Resumen_Industria.pdf)
- BYMA states FCI cuota-parte values are published daily. — [BYMA Fondos](https://byma.com.ar/productos/productos-financieros/byma-fondos)
- COMMERCIAL/UNOFFICIAL: ArgentinaDatos REST (`/v1/finanzas/fci/rentaVariable/{fecha}`), Alphacast derived CAFCI datasets, Max Capital and Primary API docs. — [ArgentinaDatos](https://argentinadatos.com/docs/operations/get-finanzas-fci-renta-variable-fecha.html), [Alphacast](https://www.alphacast.io/datasets/29744)
- CNV Resolución General 1089/2025 sets new FCI registration and control conditions. — [Boletín Oficial / Argentina.gob.ar](https://www.argentina.gob.ar/normativa/nacional/norma-419594/texto)

UNVERIFIED: the CAFCI backend pattern `https://api.cafci.org.ar/fondo/{fundId}/clase/{classId}/ficha` and list `https://api.cafci.org.ar/fondo?estado=1&include=entidad;depositaria,gerente,tipoRenta,benchmark` returning gerente/depositaria (manager/custodian), benchmark, risk (perfil de riesgo), fees, inception date, patrimonio, and a performance/"cartera" block; plus "planilla diaria" Excel exports under cafci.org.ar/Planilla-diaria. Join key: CAFCI fund ID and class ID (CNV code too); ISINs not confirmed. Approx. fund count ~1,500-2,000 funds / several thousand classes (UNVERIFIED estimate).

### Inferences
- Highest-value new Americas country: daily NAV plus manager, custodian, benchmark, fees in one JSON backend. Terms of use for the undocumented API must be checked before production use.

### Gaps
- Official CAFCI API docs, rate limits, robots and terms not found. Holdings (cartera) availability not confirmed.

## 5. Chile (NEW)

### Takeaway
CMF (regulator) runs a Fondos Mutuos portal with per-fund/series daily cuota values and downloadable daily cartola and a returns/participants report; data comes from administrators' daily reporting under Circular 1850 (2007). Bulk open file not confirmed.

### Cited Findings
- CMF says daily cuota value per fund/series is on its site, with a downloadable daily cartola per fund. Source is the daily info administrators send under Circular N°1.850 (July 2007), via CMF Supervisa (not public). — [CMF Educa: Cuotas de Fondos Mutuos](https://www.cmfchile.cl/educa/621/w3-propertyvalue-504.html), [CMF methodology PDF](https://www.cmfchile.cl/portal/estadisticas/626/articles-91848_document_1.pdf), [ChileAtiende](https://www.chileatiende.gob.cl/fichas/4021-envio-de-informacion-diaria-sobre-valores-de-cuotas-de-fondos-mutuos)
- CMF also has `valores_fondosinversion_activos.php` for fondos de inversión (closed-end). — [CMF](https://www.cmfchile.cl/sitio/estadisticas/valores_fondosinversion_activos.php)
- CMF statistics PDFs for fondos (articles-91848/91849/91850) describe data definitions. — [CMF 91849](https://www.cmfchile.cl/portal/estadisticas/626/articles-91849_document_1.pdf)

UNVERIFIED: fund list with RUN (fund registration number) as join key, series (serie) codes, AGF (manager), and downloadable CSV/Excel "valores cuota" by date; approx. 2,000+ mutual-fund series. Chile also has a Bolsa de Santiago fund page for exchange-listed funds.

### Gaps
- cmfchile.cl unreachable from this host (DNS error); download URLs, formats, history depth and terms unconfirmed.

## 6. Colombia (NEW)

### Takeaway
Superintendencia Financiera (SFC) publishes FIC (fondos de inversión colectiva) daily profitability data (Formato 523, "Informe 77 Rentabilidades", daily from 1 Jan 2016) via a web report generator, plus ficha técnica per fund on manager sites. Open data under SFC licence.

### Cited Findings
- SFC page `/ReporteInformacionFIC/` generates daily F-523 rentabilidades reports only, from 1 Jan 2016, filterable by entity type (fiduciarias, comisionistas de bolsa, SAI) and date range; download formats and direct URLs not stated; some entities not up to date. Pre-2016 history in two linked SFC publications. — [SFC FIC report](https://www.superfinanciera.gov.co/ReporteInformacionFIC/)
- SFC open data licence (Resolution 1519 of 24 Aug 2020); contact iniciativasti@superfinanciera.gov.co. — [SFC licence](https://www.superfinanciera.gov.co/10116019)
- Ficha técnica is the standardized per-fund document (manager sites, monthly). — [Accion FICs deck](https://www.accion.com.co/cmsa/wp-content/uploads/2023/02/PRESENTACION-FICs-ENERO-2023.pdf)
- datos.gov.co catalogue not confirmed to hold an FIC dataset. Search could not confirm.

UNVERIFIED: F-523 includes unit value (valor de la unidad), return by 30/180/365 days, fund/participation-type name and manager NIT; join key is fund code + manager NIT; hundreds of funds, thousands of participation types.

### Gaps
- Exact file format and fields from the generator not confirmed; no portfolio data confirmed.

## 7. Peru, Uruguay, Costa Rica, Panama, others

### Takeaway
No machine-readable official daily NAV feed was confirmed for any of these; coverage is limited to regulator web pages, central-bank aggregates and PDFs.

### Cited Findings
- Peru: BCRPData has monthly/annual mutual-fund series (balances by type, currency, participants) with Excel add-in and API; this is aggregate only. — [BCRP fondos mutuos](https://estadisticas.bcrp.gob.pe/estadisticas/series/anuales/fondos-mutuos-de-inversion). SMV (smv.gob.pe) oversees administrators; a SMV fondos de inversión page exists but a daily valor cuota download was not confirmed. — [SMV](https://www.smv.gob.pe/OrientacionyEducacion/FondosInversion.aspx)
- Uruguay: BCU authorises funds; fund regulations state the administrator makes the daily cuotaparte value available at its offices; no BCU public NAV database found; Bolsa de Valores de Montevideo (bvm.com.uy) hosts fund documents as PDFs. — [BVM](https://bvm.com.uy/repo/arch/rnmv_0.pdf)
- Costa Rica: SUGEVAL (sugeval.fi.cr) and managers' sites hold prospectuses and unit values; no download dataset found. — [explainer PDF](https://files.constantcontact.com/cff9e45c001/fdbb99d1-606b-45ae-a729-137d8d8d1cec.pdf)
- Panama, Bolivia, Ecuador, Dominican Republic, El Salvador, Guatemala, Jamaica, Bahamas, Cayman (CIMA) etc.: not researched in depth; El Salvador SSF has fund norms (NDMC-13) only. UNVERIFIED leads: Cayman/Bahamas/Bermuda regulators publish registered fund lists (Cayman CIMA registers thousands of funds, entity-level, no NAV).

### Gaps
- Panama SMV, Dominican SIMV, Paraguay, Bolivia ASFI, Ecuador, Guatemala: no data found. Peru SMV daily NAV and Costa Rica SUGEVAL file formats unverified.
