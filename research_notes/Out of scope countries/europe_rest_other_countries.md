> Moved from 'europe_rest.md' on 2026-11-18: these countries are outside the 24-country scope (US CA MX GB DE FR IT CH NL DK SE JP CN KR AU SG HK TW RU BR + LU IE AE ZA). Kept verbatim for possible later expansion.

# Rest of Europe outside scope: ES TR NO PL HU CZ RO GR PT (and others)

**Spain — CNMV (extend existing)**
- URL: https://www.cnmv.es/portal/Publicaciones/descarga-informacion-individual?ejercicio=2026 (year parameter back to at least 2013). Monthly files: NAV (valores liquidativos), net assets, unitholder counts; XML — [CNMV page](https://www.cnmv.es/portal/Publicaciones/descarga-informacion-individual?ejercicio=2026)
- Quarterly files: fees, returns, portfolio composition for funds and SICAVs; XML, from Circular 4/2008 public reports — [CNMV search result summary](https://www.cnmv.es/portal/publicaciones/descarga-informacion-individual.aspx?ejercicio=2019)
- Download links are opaque tokens `https://www.cnmv.es/webservices/verdocumento/ver?e=<token>`, so the index page must be scraped each period; 2026 page showed Jan-Aug monthly files only — [CNMV page](https://www.cnmv.es/portal/Publicaciones/descarga-informacion-individual?ejercicio=2026)
- Reuse terms not stated on page; a "Nota legal" and a "Periodicidad y breve descripción de los ficheros" PDF are linked (not read) — same page.
- Join key: ISIN (class level) / CNMV registration number. Currency missing in NAV file per catalog.py; infer from register or ISIN-based class data. Scrape-index + bulk XML.

**Turkey — TEFAS / Takasbank (NEW)**
- TEFAS is operated via Takasbank/MKK platform — [MKK](https://www.mkk.com.tr/en/depository-services/markets-and-platforms/turkey-electronic-fund-trading-platform-tefas); Takasbank publishes a full fund list as Excel export (endpoint named ExcelExportTefasFundsTradingInvestmentPlatform) per search summary — [search summary of wrapper code](https://glama.ai/mcp/servers/@saidsurucu/borsa-mcp/blob/728c8332f33398b82fe218e3607af09513a486ed/providers/tefas_provider.py).
- Per tefas-crawler README: legacy fundturkey.com.tr/api/DB/BindHistory* endpoints were retired; current JSON API under tefas.gov.tr/api/funds/...; per-fund price only, look-back enum 1/3/6/12/36/60 months (max 5 years); returns date, price, code, title; market cap, share count, investor count, allocation history no longer returned; fund kinds YAT (securities funds), EMK (pension), BYF (ETF) — [tefas-crawler](https://github.com/burakyilmaz321/tefas-crawler). Third-party wrapper, exact routes not shown.
- Older tools noted a 90-day max per request window — [search summary](https://rdrr.io/github/can-taslicukur/tefasr/man/historical_information.html).
- tefas.gov.tr/en/about-us returned an access-rejected (WAF) page to our fetcher — bot blocking likely; terms of use not retrieved.
- Scale: UNVERIFIED but widely quoted ~2,000+ funds (YAT+EMK+BYF). Join key: TEFAS fund code (3-letter); ISIN via Takasbank list/KAP (UNVERIFIED).

**Norway (NEW)**
- Oslo Børs Mutual Fund Feed (Euronext Connect technical spec, issue 2.1.8) defines NAV and refers to VFF; this is a licensed data feed, not open — [spec PDF](https://connect2.euronext.com/sites/default/files/documentation/data/Oslo%20B%C3%B8rs%20Mutual%20Fund%20Feed%20Technical%20Specification%20-%20Issue%202.1.8.pdf)
- SSB publishes only aggregated fund statistics (tables), not per-fund NAV — [SSB](https://www.ssb.no/en/bank-og-finansmarked/verdipapirmarkeder/statistikk/verdipapirfond); some managers (e.g. KLP) publish NAV xls — [KLP](https://www.klp.no/virksomhet/fond/nav-verdier). Finanstilsynet publishes aggregated management-company statistics — [Finanstilsynet](https://prod.finanstilsynet.no/analyser-og-statistikk/statistikk-for-forvaltningsselskap-og-aif-forvaltere).
- No free official bulk Norwegian NAV source confirmed.

**Poland (NEW)**
- KNF "WANJU" report (net asset value per unit) is a CSV submitted by TFIs, ISO currency codes — a reporting spec, not a public download — [KNF instruction](https://www.knf.gov.pl/knf/pl/komponenty/img/Raport_o_aktywach_netto_FIO_i_SFIO-WANJU-instrukcja_wypelniania_74970.pdf)
- Analizy.pl hosts fund financial statements by fund code/date (commercial portal, UNOFFICIAL) — e.g. https://dokumenty.analizy.pl/pobierz/fi/AXA05/RP/2025-06-30
- No official open NAV dataset found (IZFiA / NBP not confirmed).

**Hungary (NEW)**
- BAMOSZ download portlet: user enters ISINs, picks delimiter and fields, gets CSV; includes price and NAV-derived values — [BAMOSZ](https://bamosz.hu/en/letoltesek). Association (semi-official). Date range, fund count, terms unconfirmed. MNB daily-price download not found.

**Czechia (NEW)**
- CNB publishes "Seznam investičních fondů v ČR" list and fund statistics under monetary and financial statistics; ARAD time-series system and "Otevřená data" exist — [CNB list](https://www.cnb.cz/cs/cnb-news/kalendar/Seznam-investicnich-fondu-v-CR), [CNB methodology](https://CNB.cz/docs/ARADY/MET_LIST/if_stav_cs.pdf). No NAV found; AKAT not confirmed.

**Romania (NEW)**
- ASF maintains a public register of SAI/funds; AAF publishes monthly communiqués with fund-level net assets, net subscriptions, 12-month return (96 local open-end funds in Feb 2025 per release) — [AAF communiqué](https://www.sfin.ro/wp-content/uploads/2026/03/AAF-Comunicat-lunar-februarie-2025.pdf). Daily VUAN source not confirmed.

**Greece (NEW)**
- HFAMA (ethe.org.gr) publishes fund classification PDF; no NAV download found; managers publish daily prices (e.g. Delos) — [HFAMA](https://ethe.org.gr/?lang=en), [classification](https://data.ethe.org.gr/files/pdf/Mutual%20Fund%20Classification_en.pdf), [NBG AM prices](https://www.nbgam.gr/scripts/en/prices-mf.asp). EUROFIDAI sells historical NAV (commercial) — [EUROFIDAI](https://www.eurofidai.org/product/mutual-funds-over-counter).

**Portugal**
- CMVM statistics URL guess returned 404; no verified source.
