# Mutual fund source research and country coverage

## Scope

The required core markets are United States, Canada, Mexico, United Kingdom, Germany, France, Italy, Switzerland, Netherlands, Denmark, Sweden, Japan, China, South Korea, Australia, Singapore, Hong Kong, Taiwan, Russia and Brazil. Expansion markets are Luxembourg, Ireland, the UAE and South Africa. Spain appears as an additional existing dataset and is not counted toward required coverage.

## Integrated datasets currently in PostgreSQL

Integrated sources include SEC (US), FCA (GB), AMF GECO (FR), FINMA (CH), FI Sweden (SE), CSRC (CN), GSFM (AU), CVM (BR), Central Bank of Ireland (IE), ASISA (ZA), CNMV (ES), BDE open-ended fund lists for DE, IT, NL, DK and LU, the SFC-authorised public-offer product list for HK, Japan's IMAJ/FSA NISA-eligible lists and IMAJ new-fund list, and South Korea's IBK fund-information file. These are partial source-specific datasets, not complete national market coverage. Brazil provides the bulk of NAV observations; Australia contributes one explicitly AUD-labelled observation. The Japan datasets are fund-master snapshots without NAV. The IBK Korean-market list has no NAV or domicile field, so its fund domicile remains null.



## Required markets still missing an imported dataset

| Country | Code | Research status |
|---|---|---|
| Canada | CA | CRA registered-investment listings and public registry/statistics leads found; no validated domestic mutual-fund dataset imported. |
| Mexico | MX | CNBV publishes investment-fund statistics and a national securities register; no class-level fund dataset imported. |
| Singapore | SG | MAS OPERA scheme register identified; bulk extraction and domicile classification not validated. |
| Taiwan | TW | Official dataset documents daily domestic-fund NAV, names, codes and currency, updates daily, and uses Open Government Data License 1.0. The publisher CSV could not be downloaded from this runtime; no rows imported. |
| Russia | RU | Bank of Russia unit-investment-fund register/data showcase identified; downloadable fund-level data not validated. |

## Expansion markets

| Country | Code | Status |
|---|---|---|
| Luxembourg | LU | Imported from the Banco de España country-level fund CSV: 23,955 open-ended records. This is a fund master, with no NAV/currency. |
| Ireland | IE | Central Bank UCITS register integrated as a fund-master snapshot. |
| United Arab Emirates | AE | UAE regulator local-fund register candidate identified; no validated import. |
| South Africa | ZA | ASISA CIS list integrated as a fund-master snapshot. |

## Selected official evidence

- Taiwan: [Government Data Open Platform — daily NAV of securities investment trust funds](https://data.gov.tw/en/datasets/11109). It specifies daily NAV and currency fields, free CSV and Open Government Data License 1.0. Retrieval could not be completed from this runtime.
- Hong Kong: [SFC list of publicly offered investment products](https://www.sfc.hk/en/Regulatory-functions/Products/List-of-publicly-offered-investment-products). The integrated unit-trust/mutual-fund list identifies products authorized for offer in Hong Kong; it does not establish domicile.
- Europe: [Banco de España country lists of non-monetary investment funds](https://www.bde.es/wbe/en/estadisticas/otras-clasificaciones/clasificacion-entidades/listas-instituciones-financieras/listas-fondos-inversion-pais/). The imported DE, IT, NL, DK and LU snapshots contain open-ended fund records but no NAV/currency.
- Netherlands: [AFM collective investment scheme register](https://www.afm.nl/en/sector/registers/vergunningenregisters/beleggingsinstellingen). The downloadable CSV is a mixed register; the domicile column does not show a robust Dutch fund-product universe for this project.
- Italy: [Borsa Italiana open-fund NAV](https://www.borsaitaliana.it/fondi/fondi-aperti/nav/nav.en.htm) describes current and prior-30-day files and explains the NAV reference-date lag. [Open funds listing](https://www.borsaitaliana.it/borsa/fondi-aperti.html) has names and latest NAV, but these records include products not necessarily domiciled in Italy.
- Germany: [Bundesanzeiger Fondsdata](https://www.bundesanzeiger.de/pub/en/fondsdata) offers a free daily CSV price list; because the listing can include funds with non-German ISIN prefixes, this project uses the country-specific Banco de España statistical register for DE instead.
- Japan: IMAJ's [growth-quota non-listed fund list](https://www.imaj.or.jp/find/nisa_growth_productslist/) carries association fund codes and eligibility fields; the FSA's [tsumitate-quota list](https://www.fsa.go.jp/policy/nisa2/products/index.html) adds manager/name rows without native codes. IMAJ's [new-fund sheet](https://www.imaj.or.jp/find/newfunds/index.html) supplies recent launch records. The IMAJ [general search library](https://toushin-lib.fwg.ne.jp/FdsWeb/) is a broader searchable source with NAV data, but prohibits automated scraping, so it is not ingested.
- South Korea: the [data.go.kr IBK fund CSV](https://www.data.go.kr/data/15020770/fileData.do) supplies the products handled by IBK, native product codes, dated performance and fee fields. It is not the full Korean market and has no domicile, currency or NAV; domicile is intentionally null. KOFIA's [One-Click](https://fund.kofia.or.kr/fs/fund/html/fundMain.html) and [electronic disclosure](https://dis.kofia.or.kr/) portals offer lookup, but no bulk feed was verified. The FSC/KRX [listed-securities API](https://www.data.go.kr/data/15094808/openapi.do) is exchange pricing with restrictive rights, not a NAV feed.

## Next work

Prioritize market-specific sources for Canada, Mexico, Japan, South Korea, Singapore, Taiwan, Russia and the UAE. Confirm domicile when using public-offer rather than home-country registers. Do not count source discovery or cross-border distribution as domestic fund integration. Confirm each provider’s reuse terms before redistribution or commercial use.
