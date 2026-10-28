# FundFlow API Inventory

Inspected Express routes in `api/src/routes/`, 2026-10-28. Live API was not running during final report generation. Response examples below describe route contracts, not a current uptime claim. JSON errors are routed through middleware.

| Method | Path | Purpose / parameters |
|---|---|---|
| GET | `/health` | Process health and version |
| GET | `/api/v1/health/database` | Database connectivity check |
| GET | `/api/v1/health/etl` | ETL status health |
| GET | `/api/v1/stats` | Aggregate fund/NAV/country/source counts and latest run |
| GET | `/api/v1/countries` | Country rollup: funds, NAV, source counts/status |
| GET | `/api/v1/sources` | Source catalogue and current status metadata |
| GET | `/api/v1/sources/:id` | One source record |
| POST | `/api/v1/sources/:id/check` | Trigger/check source connectivity |
| GET | `/api/v1/funds` | Search/list; pagination, country, currency, q, category, fund type, status, holdings status, ISIN, NAV flag, sort |
| GET | `/api/v1/funds/:id` | Fund detail and source metadata |
| GET | `/api/v1/funds/:id/nav` | NAV history; optional from/to and bounded limit (max 5,000) |
| GET | `/api/v1/funds/:id/holdings` | Holdings by fund; optional report date and bounded limit (max 5,000) |
| GET | `/api/v1/etl/runs` | Run history; limit 1–100 |
| GET | `/api/v1/etl/runs/:id` | One UUID or `python-N` run; invalid IDs rejected |
| POST | `/api/v1/etl/runs` | Start selected/all ETL; admin authentication, validation, rate limit, active-run conflict handling |

The stats endpoint uses SQL `count(*)` over `funds` and `nav_observations`, country count over source registry excluding ES, and registry integration status. It reports actual connected-database values at request time; no dashboard hardcoded totals were found in the endpoint implementation.
