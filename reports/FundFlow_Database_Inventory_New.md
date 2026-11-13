# FundFlow Database Inventory

Evidence: SQLAlchemy models and Alembic migrations inspected 2026-10-28. PostgreSQL direct connection was unavailable during report generation; DB-size and row-count values are prior read-only query results, not freshly rechecked. Current recorded migration head: `0006_portfolio_holding_details`.

| Table | Primary key | Core fields | Foreign keys / uniqueness |
|---|---|---|---|
| `sources` | `source_id varchar(100)` | country_code, organization, source_name, endpoint_url, verification_status, integration_status, license_status | Country-code index |
| `funds` | `id integer` | source_fund_id, name, domicile_country, currency, ISIN, legal_name, provider, category, fund_type, inception_date, status, official_url, ticker, manager, administrator, net_assets/date, target_audience, retrieved_at, SEC series/CIK, holdings_status/report_date | `source_id → sources`; unique `(source_id, source_fund_id)`; indexes on source, domicile, ISIN, provider, category, status, ticker |
| `nav_observations` | `id integer` | fund_id, valuation_date, NAV, currency, retrieved_at | `fund_id → funds ON DELETE CASCADE`; unique `(fund_id, valuation_date, currency)`; fund/date indexes |
| `portfolio_holdings` | `id integer` | fund_id, reporting_date, accession_number, holding_index, security_name, ticker, ISIN, CUSIP, quantity, market_value, market_value_currency, portfolio_weight, data_source, source_url, retrieved_at | `fund_id → funds ON DELETE CASCADE`; unique `(fund_id, reporting_date, holding_index)`; fund/date indexes |
| `holding_metrics` | `id integer` | holding_id, data_source, source_url, as_of_date, first_bought_date, portfolio_weight, share_change_percentage, one_year_return, forward_pe, sector, calculation_basis, retrieved_at | `holding_id → portfolio_holdings ON DELETE CASCADE`; unique `(holding_id, data_source, as_of_date)`; holding/date indexes |
| `etl_runs` | `id integer` | started_at, finished_at, status, source_id, records_extracted, records_loaded, error | nullable `source_id → sources` |
| `api_etl_runs` | UUID | request/run timestamps, status, sources, results, exit/error details | API migration-defined |
| `api_source_checks` | migration-defined | source check state, timestamps, response details | source-linked check history |
| `alembic_version` | migration-defined | current revision | Alembic-managed |

`funds`, `nav_observations`, and `portfolio_holdings` are factual source records. Optional vendor/derived financial metrics are in the separate `holding_metrics` table, with provider, source URL, as-of date, and calculation basis.
