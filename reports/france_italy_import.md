# France and Italy fund imports

## France

The existing `amf_geco` connector imports **28,375** AMF GECO French-domiciled product/share-class identities with ISINs and fund metadata. AMF's public guidance says the NAV is obtained through GECO or directly from the management company; GECO does not expose a free bulk daily NAV feed in the public export used by this ETL. Therefore no NAV values are invented for French rows. See [AMF guidance on finding an OPC NAV](https://www.amf-france.org/fr/ou-trouver-la-valeur-liquidative-dun-opc-0).

Official supporting sources reviewed:

- [AMF GECO](https://geco.amf-france.org/)
- [Banque de France Webstat IVF1](https://www.data.gouv.fr/datasets/webstat-ivf1-1), official aggregate non-monetary fund statistics; it is not a class-level NAV feed.

## Italy

The existing `it_bde_nonmonetary_funds` connector imports **1,326** open-ended Italian fund identities from the official Banco de España country register. A separate `it_borsa_navs` connector now imports **68** validated public daily NAV observations from [Borsa Italiana's open-fund NAV file](https://www.borsaitaliana.it/fondi/fondi-aperti/nav/nav.en.htm). The file provides reference date, ISIN, currency and NAV, but no fund name or category; the ETL stores an ISIN-labelled name and explicitly marks the category as unavailable rather than guessing.

Borsa Italiana states that its reference date is the date the NAV is transmitted and the NAV relates to the second trading day before that date. The existing Italian identity master remains the broader coverage source.


## Switzerland
The new `ch_six_fund_explorer_navs` connector queries the public SIX Fund Explorer JSON endpoint. It filters `ProductLine=IF` rows to Swiss legal domicile (`CH`) and imports the published ISIN, fund name, currency, provider, asset-class subcategory, market date and closing value as NAV. The source returned **47 validated Swiss investment-fund rows and 47 NAV observations** during this run. SIX labels the public explorer data as delayed; its commercial fund-data products cover a broader universe, so this import is a verified public exchange subset rather than a claim that every private Swiss fund is present.

Source: [SIX Fund Explorer](https://www.six-group.com/en/market-data/mutual-funds/fund-explorer.html). FINMA's approved-products list remains the official Swiss fund master, but it does not publish class-level NAV history.

## France NAV enrichment
The new `fr_lacotebleue_navs` connector imports **90** unique French-prefixed ISINs with validated NAV, currency, manager, valuation date and category derived from the published fund name. The source is a public third-party table at [La Cote Bleue](https://actusite.lacotebleue.fr/opcvm/), not an AMF regulator feed. AMF GECO remains the official French identity master; its public guidance directs users to GECO or the management company for individual NAV values and does not provide a free bulk daily NAV file.
