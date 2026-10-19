# Source discovery

The catalogue now has one official regulator or industry-association candidate for each required country. These are researched leads, not proof of a usable mutual-fund dataset. The verifier makes requests to each catalogue page; an HTTP response only establishes reachability, while fund-level usability requires inspecting actual records and fields. Licensing remains separate and generally `Unknown`.

## Candidates and limitations

| Country | Candidate | Discovery finding |
|---|---|---|
| US | SEC Form N-PORT | Structured quarterly filing archives with holdings; not a daily NAV feed. |
| CA | SIMA (formerly IFIC) | Public industry statistics; fund-level NAV source not established. |
| MX | CNBV fund statistical portal | Periodic fund-sector financial and operational series; export format to inspect. |
| GB | FCA Financial Services Register | Free API requires registration and is a firm/person register, not NAV. |
| DE | BaFin investment fund databases | Official fund and prospectus lists; structured access to investigate. |
| FR | AMF GECO | Official collective-investment-scheme database; no programmatic API confirmed. |
| IT | Banca d'Italia supervisory registers | UCITS-related intermediary records and downloadable registers; not a NAV feed. |
| CH | FINMA approved fund lists | Regularly updated downloadable fund lists; no NAV history established. |
| NL | AFM collective-investment register | Official register page advertises CSV/XML export; field scope to inspect. |
| DK | Danish FSA investment-association register | Official PDF register; not NAV data. |
| SE | Finansinspektionen fund holdings | Fund holdings reporting data; special funds excluded, NAV not established. |
| LU | CSSF publication/data portal | Investment-fund publications and statistics; permitted fund-level endpoint to identify. |
| IE | Central Bank of Ireland CIS registers/downloads | Authorised fund lists and monthly fund-data publications, commonly PDF. |
| JP | Investment Management Association of Japan | Recurring investment-trust statistics and fund-search materials; NAV fields need review. |
| CN | CSRC public-fund product index | Dated official XLSX product index; current NAV data feed and reuse remain unconfirmed. |
| KR | KOFIA Fund Information One-Click | Association portal links information from several providers; provenance needs examination. |
| AU | APIR | Large product reference service is subscription-based; no public bulk feed confirmed. |
| SG | MAS OPERA | Public CIS register displays scheme ID, name, status and manager; no NAV history. |
| HK | SFC statistics/product directory | XLS/PDF statistics include aggregate NAV; fund-level price history not established. |
| TW | SITCA fund information | Public fund information section; data fields and reuse rights need review. |
| RU | Bank of Russia unit-fund registers | Official fund registers and web service/API for market-participant data; NAV not established. |
| BR | CVM open data | Official open-data portal documents fund-registration data and an API; NAV requires separate search. |
| AE | UAE Capital Market Authority local funds | Official open-data page for local funds; format and rights need inspection. |
| ZA | ASISA CIS data | Lists funds and advertises current/historical fund prices; licensing and download formats need confirmation. |

## Evidence links

Each row in `reports/source_catalogue.json` has the source page as `evidence_url` and describes the specific limitation. The initial four candidate descriptions and endpoints are also in `config/sources.yaml`. Research used official pages, including [CNBV's investment-fund statistics](https://www.gob.mx/cnbv/acciones-y-programas/informacion-estadistica-fondos-de-inversion), [FINMA's authorised fund lists](https://www.finma.ch/en/finma-public/authorised-institutions-individuals-and-products/), [MAS OPERA's collective-scheme register](https://eservices.mas.gov.sg/opera/Public/CIS/ViewSchemes.aspx), [Hong Kong SFC fund statistics](https://www.sfc.hk/en/Published-resources/Statistics?type=0), [CSRC's public-fund product index](https://www.csrc.gov.cn/csrc/c101900/c1029655/content.shtml), [CVM open data](https://dados.cvm.gov.br/dataset/?_groups_limit=0&_tags_limit=0&groups=fundos-de-investimento&tags=Cadastro+de+Regulados), and [ASISA collective-investment data](https://www.asisa.org.za/statistics/collective-investments-schemes/).

The CLI verification attempt was made from the local runtime on 2026-10-17. DNS resolution failed for the configured pages, so all were recorded as unavailable from this environment. This is not evidence that the publisher's website is generally offline. No source is marked `Usable Fund Data Confirmed`, and no source is integrated. Confirm terms of use before commercial reuse.
