# Germany fund and NAV import

## Sources

- [Deutsche Bundesbank investment-fund statistics](https://www.bundesbank.de/de/statistiken/geld-und-kapitalmaerkte/-/investmentfondsstatistik-804052): official monthly aggregate/open-ended-fund statistics and downloadable CSV time series. It is not a class-level daily NAV feed.
- [Bundesanzeiger Fondsdata](https://www.bundesanzeiger.de/pub/en/fondsdata): Federal Gazette platform with free fund-price records showing fund name, provider, ISIN/WKN, date, offer price, bid price, currency and NAV. The platform says current prices are updated daily and price lists can be downloaded free after publication.
- [Banco de España German fund list](https://www.bde.es/webbe/en/estadisticas/otras-clasificaciones/clasificacion-entidades/listas-instituciones-financieras/listas-fondos-inversion-pais/lista-if-de.html): official open-ended non-monetary fund master used by the existing Germany connector.

## Imported

- `de_bde_nonmonetary_funds`: **6,400** open-ended German fund identities; no NAV is present in that source.
- `de_bundesanzeiger_navs`: **248** validated fund/share-class records and **248** NAV observations from the free public Federal Gazette search results. Rows include ISIN, provider, category, currency, valuation date and NAV.
- Categories are transparent name-based subcategories: Equity, Fixed income, Money market, Real estate, Mixed allocation, Commodities, Index/ETF, or Other.

The Federal Gazette result set contains funds published in the German market, including foreign-domiciled funds. `domicile_country` is set to `DE` only when the ISIN begins with `DE`; other domiciles remain null rather than being guessed. Dates vary by fund because the public search returns each fund's latest available published price, not one universal valuation date.
