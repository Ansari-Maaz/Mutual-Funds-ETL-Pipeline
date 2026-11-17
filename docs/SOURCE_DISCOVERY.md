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
| JP | Investment Management Association of Japan and Financial Services Agency | IMAJ and FSA publish downloadable current eligibility lists with fund names and managers; IMAJ also publishes monthly new-fund sheets. These are curated subsets, not a full national register. The IMAJ broad fund-search library provides NAV lookup but expressly prohibits automated scraping. |
| CN | CSRC public-fund product index | Dated official XLSX product index; current NAV data feed and reuse remain unconfirmed. |
| KR | IBK through data.go.kr; KOFIA | IBK's public CSV has fund codes, names, managers, risk/return and fee fields for products it handles; it is not an exhaustive Korea-domiciled register and gives no domicile, currency or NAV. KOFIA's One-Click and DIS portals support search, but a verified bulk feed was not found. |
| AU | APIR | Large product reference service is subscription-based; no public bulk feed confirmed. |
| SG | MAS OPERA | Public CIS register displays scheme ID, name, status and manager; no NAV history. |
| HK | SFC statistics/product directory | XLS/PDF statistics include aggregate NAV; fund-level price history not established. |
| TW | SITCA fund information | Public fund information section; data fields and reuse rights need review. |
| RU | Bank of Russia unit-fund registers | Official fund registers and web service/API for market-participant data; NAV not established. |
| BR | CVM open data | Official open-data portal documents fund-registration data and an API; NAV requires separate search. |
| AE | UAE Capital Market Authority local funds | Official open-data page for local funds; format and rights need inspection. |
| ZA | ASISA CIS data | Lists funds and advertises current/historical fund prices; licensing and download formats need confirmation. |

## Evidence links

Each row in `reports/source_catalogue.json` has the source page as `evidence_url` and describes the specific limitation. The initial candidate descriptions and endpoints are also in `config/sources.yaml`. Research used official pages, including [CNBV's investment-fund statistics](https://www.gob.mx/cnbv/acciones-y-programas/informacion-estadistica-fondos-de-inversion), [FINMA's authorised fund lists](https://www.finma.ch/en/finma-public/authorised-institutions-individuals-and-products/), [MAS OPERA's collective-scheme register](https://eservices.mas.gov.sg/opera/Public/CIS/ViewSchemes.aspx), [Hong Kong SFC fund statistics](https://www.sfc.hk/en/Published-resources/Statistics?type=0), [CSRC's public-fund product index](https://www.csrc.gov.cn/csrc/c101900/c1029655/content.shtml), [CVM open data](https://dados.cvm.gov.br/dataset/?_groups_limit=0&_tags_limit=0&groups=fundos-de-investimento&tags=Cadastro+de+Regulados), and [ASISA collective-investment data](https://www.asisa.org.za/statistics/collective-investments-schemes/).

## Japan and South Korea source findings

Japan has two current structured official lists suitable for fund-master ingestion: IMAJ's [NISA growth-quota list of non-listed investment trusts](https://www.imaj.or.jp/find/nisa_growth_productslist/) and the FSA's [NISA tsumitate-quota disclosure lists](https://www.fsa.go.jp/policy/nisa2/products/index.html). The IMAJ XLSX includes its association fund code and a flag indicating tsumitate-quota eligibility; the FSA XLSX includes the fund name and manager but no native code. These lists overlap and only cover funds eligible for the respective tax-advantaged investment quotas. IMAJ's [monthly new-fund sheets](https://www.imaj.or.jp/find/newfunds/index.html) add a changing, recent-launch subset. The [Investment Trust General Search Library](https://toushin-lib.fwg.ne.jp/FdsWeb/) offers much broader domestic fund and NAV lookups, but its terms prohibit automated scraping; it is catalogued without an automated importer. IMAJ aggregate statistical spreadsheets are not fund-level data.

South Korea's [data.go.kr IBK fund-information dataset](https://www.data.go.kr/data/15020770/fileData.do) is a public annual CSV. Its 2025-12-31 edition lists 1,132 products handled by IBK and supplies a fund code, manager, fund type, risk grade, cumulative period returns and fee fields. It does not supply domicile, currency or NAV; these rows are marked as Korean-market distribution data with domicile left null. The [KOFIA One-Click portal](https://fund.kofia.or.kr/fs/fund/html/fundMain.html) is an aggregator and disclaims validating the linked providers' information. KOFIA's [electronic disclosure service](https://dis.kofia.or.kr/) provides individual fund and reference-price search, but a complete public bulk feed was not verified. The FSC/KRX [listed-securities API](https://www.data.go.kr/data/15094808/openapi.do) provides exchange prices rather than mutual-fund NAV and has non-commercial/no-derivatives rights, so it is not imported.

The local availability of these portals can vary with network access. On 2026-11-06, the IMAJ and FSA snapshots and the IBK public CSV were downloaded and successfully imported. The automated FSA importer excludes ETFs and reads the non-ETF investment-trust sheets. The three Japanese lists overlap; counts are source rows, not unique products across the market. Confirm terms of use before commercial reuse.
