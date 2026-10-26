# UK NAV gap research

The UK FCA register contains 3,975 authorised/approved fund records, but it is a regulatory authorisation register and does not publish a daily NAV field. The FCA import now stores its manager, scheme type, product type and status as fund metadata.

The public FundsLibrary unit-price table was inspected and imported. It supplied 33 usable NAV observations with Investment Association sectors and GBP prices. Those records are retained under `uk_fundslibrary_unit_prices`.

The remaining FCA records still have no NAV observation in the database. A comprehensive free UK feed was not found. FE fundinfo documents broad UK pricing/NAV coverage, but access is subscription/API-key controlled; its public developer portal requires an authorised account and subscription key. Morningstar’s public UK comparison page explains that prices are updated daily, but it does not expose an unauthenticated bulk download. Direct manager price pages are fragmented and cannot be reliably joined to FCA PRNs because the FCA CSV does not contain ISINs or SEDOLs.

No NAV values were invented or copied from unrelated share classes. To complete the remaining 3,975 funds, obtain a licensed FE fundinfo/Morningstar/LSEG feed or provide manager-level files containing an identifier (ISIN/SEDOL), NAV, currency and valuation date.

## Uploaded FE fundinfo OpenAPI specification

`Fa-prod-PubliFundApiEuwDev.yaml` is useful for a future authenticated integration. It exposes share-class, fund, subfund and promoter endpoints containing ISIN, currency, lifecycle status, fund type, price frequency, NAV delivery time, price basis and price type. It also exposes an authorised-account `/shareclass` universe endpoint.

The specification does **not** contain a price/NAV-history endpoint or a bulk NAV field. It requires an `Ocp-Apim-Subscription-Key` header (or `subscription-key` query parameter), and its servers are the FE fundinfo development environment. Therefore it can improve UK identity/category/currency mapping after an API key is supplied, but it cannot by itself fill the missing NAV observations.

