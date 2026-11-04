# Fund profile data and source coverage

## Data policy

FundFlow uses the Twelve Data mutual-fund API as a reference for the kinds of fields users may expect from a fund data API. FundFlow does not import Twelve Data values. Its records come from registered country, regulator, exchange, fund-manager, or other documented official sources. Each connector can only populate fields that its source actually publishes. Missing values stay null or are omitted; no performance, risk, rating, expense, yield, or sustainability value is inferred.

Freshness is source-dependent. `retrieved_at` records when FundFlow ingested a value; a source-provided report date is stored separately when available. A recent retrieval timestamp does not mean the underlying source observation is recent.

## FundFlow field groups

| Field group | Examples | FundFlow representation | Availability |
| --- | --- | --- | --- |
| Identity | Name, legal name, provider, country, currency, ISIN, ticker, source-native ID | Core fund profile | Varies by source; source-native ID and name are required for ingestion |
| Classification | Category, fund type, status, target audience | Core fund profile | Only when the publisher provides the value |
| Administration | Manager, administrator, inception date, official profile URL | Core fund profile | Varies by country and source |
| Assets | Net assets and its as-of date | Core fund profile | Only for sources with a dated asset value |
| NAV | NAV value, valuation date, currency, retrieval time | NAV history endpoint | Only for NAV-enabled connectors; some country registers are fund-master-only |
| Holdings | Security identity, quantity, market value, weight, report date, filing source | Holdings endpoint | Only for sources and reporting periods that disclose positions |
| Performance | Period returns and benchmark comparisons | `performance` profile dataset | Not populated unless an official source supplies dated values |
| Risk | Volatility, drawdown, Sharpe-like measures, risk class | `risk` profile dataset | Not populated unless an official source supplies definitions and dates |
| Ratings | Ratings and rating provider/date | `ratings` profile dataset | Not populated unless an official source publishes them |
| Composition | Asset allocation, sector/geography breakdowns | `composition` profile dataset or holdings | Depends on official publication; holdings are not silently converted to allocation figures |
| Purchase information | Minimum investment, dealing frequency, settlement, fees | `purchase_info` profile dataset | Not populated unless an official source provides it |
| Sustainability | SFDR/ESG disclosures and their classification basis | `sustainability` profile dataset | Not populated unless an official source provides it; not mapped to target audience |
| Distributions | Dividend/distribution amounts, dates, type | `dividends` profile dataset | Not populated unless an official source provides a distribution history |

The supplementary groups are stored as versioned JSON snapshots in `fund_profile_snapshots`. Each snapshot has a dataset name, registered source ID, payload, optional source report date, source URL, and database retrieval timestamp. This preserves country-specific fields without pretending that every country has the same schema. The read API is `GET /api/v1/funds/{fund_id}/profile-data`.

NAV observations now have nullable `source_id` and `source_url` columns. An exact-match backfill attributed 49,529 of the existing 50,022 US NAV/price rows to their raw Yahoo Finance or Nasdaq input URLs; 493 remain unattributed. These are third-party daily close/price observations, and the source match does **not** establish equivalence to an issuer-published NAV. FundFlow keeps them marked partial while official NAV identification and history coverage remain incomplete. New ETL rows retain their actual publisher source and URL.

## Current added coverage

### United States — SEC class-level scheme metadata

The SEC series/class master provides the registered series name, class name, SEC series ID, SEC class ID, optional ticker, registrant name and registrant address for its covered open-end share classes. FundFlow now stores those values in the source-linked `summary` profile snapshot, exposing the published class name as `share_class` while preserving the SEC identifiers and registrant address. The registrant is explicitly not treated as the investment adviser or portfolio manager. The SEC file does not publish ISIN, CUSIP, expense ratio, benchmark or launch date; those fields remain unresolved unless a separate issuer source supplies them. See the [SEC series/class information file](https://www.sec.gov/files/investment/data/other/investment-company-series-class-information/investment-company-series-class-2026.csv).

To import the already cached SEC class file into local profile snapshots without making a network request, run `./.venv/bin/python -m app.cli sync-sec-class-profiles --dry-run` first, then omit `--dry-run` to write exact class-ID matches. This command does not overwrite core fund records, NAV observations, or portfolio holdings.

### United States — ISIN evidence from SEC filings

`scripts/backfill_us_isins_from_sec_holdings.py` can reuse already stored SEC N-PORT position disclosures. It requires an exact ticker match, compatible normalized fund/security names, a single consistent CUSIP/ISIN pair, and a valid ISIN check digit; ambiguous or conflicting results are skipped. Preview with `./.venv/bin/python scripts/backfill_us_isins_from_sec_holdings.py` and apply with `./.venv/bin/python scripts/backfill_us_isins_from_sec_holdings.py --apply`. The SEC records describe securities held in portfolios, so the script only accepts the conservative identity checks above. This covers only classes found in the existing filings; it is not a complete ISIN directory. Current identifiers are stored with the filing URL in `fund_profile_snapshots`.

### United States — Vanguard directory and product-profile adapters

The public Vanguard all-products directory is available at `https://advisors.vanguard.com/investments/fund-data/all-products`. `scripts/sync_vanguard_directory.py` validates each product ID and ticker, requires one exact US FundFlow ticker match, and stores provider-reported summary/classification, expense-ratio, NAV-return, and yield snapshots. A local sync matched 390 of the directory's 390 tickers to exactly one US database record and wrote 1,560 snapshots; it filled 389 missing inception dates. SEC legal names were retained rather than replaced with Vanguard display names. Run `./.venv/bin/python scripts/sync_vanguard_directory.py --dry-run` to inspect coverage or omit `--dry-run` to sync. The separate `scripts/sync_vanguard_profiles.py --ticker VFIAX` reader verifies the ticker on Vanguard's detailed product page and stores page-level data. Neither adapter copies values from Twelve Data.

VFIAX's current stored provider-page fields include its CUSIP, category, objective, benchmark, inception date, management style, distribution schedule, reported holdings count, expense ratio, and dated net assets. The provider page publishes numeric `fundNetAssetsData`; FundFlow stores its reported amount and effective date with an explicit note that share-class scope is not asserted. SEC N-PORT AUM is a separate series/fund-level record and is not treated as VFIAX share-class assets. The current provider-page snapshots also include YTD and one-year returns, three-year standard deviation, and a dated dividend-yield value, each with the page's source URL and published effective date. These are point-in-time measures, not full performance or risk histories. The adapters do not yet collect complete Vanguard NAV or distribution histories, complete monthly Vanguard holdings, full fee/waiver history, or the document archive, and they do not infer a named portfolio manager from a management group.

This provider adapter is an initial, explicit-ticker implementation. It is not a claim that all Vanguard funds or the wider US dataset have been enriched. Other provider adapters and automated freshness schedules remain to be built.

Banco de España's official non-monetary fund CSVs include a European code, LEI, fund name, management company, management address, investment policy, and open/closed status. For open-ended records, the Germany, Italy, Netherlands, Luxembourg, and Denmark connectors expose the additional values as a `summary` dataset. These register feeds do **not** provide NAV, currency, performance, risk, ratings, expenses, yield, or distribution history. Fields unavailable in those sources remain unavailable in FundFlow.

Other country connectors continue to map their source-supported values to the core fund, NAV, and holdings schema. The catalogue and each source's official link are listed in `app/catalog.py` and the API's sources endpoint. Country coverage is therefore connector- and source-specific; a global dataset category does not mean worldwide values exist.

## Twelve Data comparison boundary

The comparison script uses Twelve Data's basic `/funds` directory and `/time_series` endpoints. It checks exact ticker identity, directory metadata, and one requested daily series date; it records value types and leaves FundFlow gaps explicit. It does not copy vendor values into FundFlow. The `/mutual_funds/world` full-data endpoint is premium and is not called by default. A configured key alone does not establish entitlement or redistribution rights.

Twelve Data documents fund summary, trailing and annual returns, risk, holdings/composition, purchase information, sustainability, and distribution-related fields. These are reference categories for API design, not a substitute data source for FundFlow. Directory and daily-series parity is still distinct from complete fund-data parity. NAV, exchange-traded close, and market OHLC are not interchangeable. Users should compare only when fund identity/share class, currency, valuation date, and field definition match. Official country publishers may use different NAV schedules, return conventions, rating scales, and report dates.

References:

- [Twelve Data mutual funds documentation](https://twelvedata.com/docs)
- [Twelve Data funds endpoint](https://twelvedata.com/docs#funds)
- [Twelve Data mutual funds service](https://twelvedata.com/mutual-funds)
- [Twelve Data mutual funds service](https://twelvedata.com/mutual-funds)
- [Twelve Data terms](https://twelvedata.com/terms)
- [Vanguard VFIAX official product page](https://advisors.vanguard.com/investments/products/vfiax/)
- [Banco de España fund lists](https://www.bde.es/webbe/en/estadisticas/otras-clasificaciones/clasificacion-entidades/listas-instituciones-financieras/listas-fondos-inversion-pais/)
