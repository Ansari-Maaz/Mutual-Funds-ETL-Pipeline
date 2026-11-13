# UK public FT/Morningstar fund-price import

- **Source:** [Financial Times fund archive](https://markets.ft.markitdigital.com/data/dataarchive/ajax/fetchreport?documentKey=688_UTS~Combined_261024&reportCode=UTS_Combined)
- **Provider:** Financial Times / ICE Data Services (the archive guide says prices are supplied by fund operators/managers/administrators and collated by ICE).
- **Snapshot:** 24 October 2026 archive edition.
- **Imported:** 253 fund/share-class rows and 253 dated price observations.
- **Currency conversion:** FT says prices are in pence unless indicated. GBP bid values were divided by 100; explicitly marked EUR/USD values were retained in their stated currency.
- **Important field meaning:** the table provides a manager-supplied **bid price**. It is stored in `nav_observations.nav` so the existing ETL schema can expose the value consistently, but it is labelled as a quoted fund price and must not be represented as an official regulator NAV. The table has no ISIN, so `isin` remains null.
- **Coverage limitation:** this is a public price table, not the complete FCA-authorised universe. FCA's separate register contains the fund master but no NAV feed. The archive guide states that prices are the most recent supplied by managers and that not all funds update daily.

The ETL preserves source provenance and does not fabricate identifiers or prices for FCA rows absent from the public table.
