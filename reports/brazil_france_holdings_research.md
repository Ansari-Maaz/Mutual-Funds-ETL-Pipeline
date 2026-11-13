# Brazil and France portfolio-holdings research

Generated: 2026-10-27

## Executive result

| Country | Official structured holdings source | Import result |
|---|---|---|
| Brazil | CVM Dados Abertos, Fundos de Investimento, `DOC/CDA` | Supported. The existing `sync-cvm-holdings --month YYYYMM` importer loads public fund/class positions for every locally registered CVM fund that matches the archive identifiers. |
| France | No AMF central structured portfolio-holdings dataset found | Not safely importable as a national all-funds feed. AMF GECO supplies product/share-class identity and documents; portfolio positions are not exposed as a bulk structured dataset. |

## Brazil

### Official sources reviewed

1. **CVM CDA (Composição da Carteira)**
   - Dataset: <https://dados.cvm.gov.br/dataset/fi-doc-cda>
   - Archive pattern used by the importer: `https://dados.cvm.gov.br/dados/FI/DOC/CDA/DADOS/cda_fi_YYYYMM.zip`
   - Format: monthly ZIP archives containing semicolon-delimited CSV files.
   - Coverage: public portfolio-composition records reported by Brazilian investment funds and classes.
   - Key matching fields: CNPJ of fund/class, reporting date, security description, ISIN/ticker where supplied, quantity and market value.
   - Limitations: confidential/omitted positions are not recoverable; field names vary between CDA file groups and reporting periods; the source is a periodic snapshot, not a real-time position feed.

2. **CVM Informe Diário**
   - Dataset: <https://dados.cvm.gov.br/dataset/fi-doc-inf_diario>
   - Use: daily quota value/NAV, net assets and fund/class registry linkage.
   - It is not the portfolio-position dataset, but it supplies the net-asset denominator used to derive portfolio weights when a compatible CDA row reports market value.

3. **CVM fund and class registration data**
   - Catalog: <https://dados.cvm.gov.br/>
   - Use: canonical CNPJ and class identifiers used to associate CDA positions with the normalized `funds` table.

### Existing implementation

`app/holdings/cvm_cda.py` downloads one official monthly CDA archive, matches CNPJ and optional subclass identifiers, stores positions in `portfolio_holdings`, derives a percentage weight only when reported market value and net assets are both present, and marks each matched fund's latest report date.

Run one month:

```bash
python -m app.cli sync-cvm-holdings --month 202609
```

Run additional months to build history. The loader is idempotent for a fund/report-date/holding-index key.

### Data-integrity rules

- No position is invented when a CDA row has no security identifier/name.
- No portfolio weight is asserted when the source has no usable net-asset denominator.
- Rows are labelled `cvm_open_data_cda` and retain the official archive URL.
- Missing/confidential positions remain missing.

## France

### Official sources reviewed

1. **AMF GECO**
   - Product/share-class directory: <https://geco.amf-france.org/liste-des-produits-d-epargne>
   - The public web client exposes product, compartment, share-class and document services. The existing `amf_geco` connector uses the product/compartment export to import active French-domiciled fund identities and ISINs.
   - GECO does not expose a public bulk, structured portfolio-position dataset comparable to CVM CDA or SEC Form N-PORT.

2. **AMF guidance on fund information**
   - <https://www.amf-france.org/fr/ou-trouver-la-valeur-liquidative-dun-opc-0>
   - AMF directs investors to GECO or the management company for product information and valuation information. It does not identify a national holdings download.

3. **Management-company periodic reports**
   - French UCITS/AIF managers may publish annual, semiannual, factsheet or portfolio reports. These are issuer-specific documents, often PDF, with differing layouts, reporting dates and disclosure levels.
   - They are not a single official France-wide source and cannot provide complete “each fund” coverage without a separately maintained issuer-by-issuer inventory and document parser.

4. **Banque de France Webstat IVF1**
   - <https://www.data.gouv.fr/datasets/webstat-ivf1-1>
   - Official aggregate investment-fund statistics; not fund-level security positions.

### Why a France holdings importer is not enabled

The project must preserve source attribution and must not turn a reachable product page or a PDF link into false holdings coverage. Without a central structured AMF feed, a France importer would need to:

1. enumerate each management company and each fund's current report URL;
2. download reports under each issuer's terms;
3. parse heterogeneous PDF/HTML tables;
4. resolve security identifiers and distinguish current positions from transactions or examples; and
5. handle funds that publish no public portfolio schedule.

That process cannot honestly be represented as complete official France coverage. France fund identities remain imported through AMF GECO, while holdings are left `not_checked`/unavailable until an issuer-specific, source-approved adapter is added.

## Recommended next step

Continue Brazil with scheduled monthly CDA imports. For France, add adapters only for named management companies after confirming their official report URLs, reuse terms and table format; do not mark the entire French universe as holdings-complete.
