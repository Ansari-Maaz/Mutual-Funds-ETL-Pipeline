# France and Italy fund imports

## France

The existing `amf_geco` connector imports **28,375** AMF GECO French-domiciled product/share-class identities with ISINs and fund metadata. AMF's public guidance says the NAV is obtained through GECO or directly from the management company; GECO does not expose a free bulk daily NAV feed in the public export used by this ETL. Therefore no NAV values are invented for French rows. See [AMF guidance on finding an OPC NAV](https://www.amf-france.org/fr/ou-trouver-la-valeur-liquidative-dun-opc-0).

Official supporting sources reviewed:

- [AMF GECO](https://geco.amf-france.org/)
- [Banque de France Webstat IVF1](https://www.data.gouv.fr/datasets/webstat-ivf1-1), official aggregate non-monetary fund statistics; it is not a class-level NAV feed.

## Italy

The existing `it_bde_nonmonetary_funds` connector imports **1,326** open-ended Italian fund identities from the official Banco de España country register. A separate `it_borsa_navs` connector now imports **68** validated public daily NAV observations from [Borsa Italiana's open-fund NAV file](https://www.borsaitaliana.it/fondi/fondi-aperti/nav/nav.en.htm). The file provides reference date, ISIN, currency and NAV, but no fund name or category; the ETL stores an ISIN-labelled name and explicitly marks the category as unavailable rather than guessing.

Borsa Italiana states that its reference date is the date the NAV is transmitted and the NAV relates to the second trading day before that date. The existing Italian identity master remains the broader coverage source.
