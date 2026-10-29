# FundFlow API Reference

This reference uses a consistent endpoint layout: purpose, authentication, parameters, request example, and response shape. Its endpoint-documentation layout follows the clarity of [Twelve Data's dividends reference](https://twelvedata.com/docs/fundamentals/dividends); Twelve Data is not a FundFlow data provider.

## Base URL and conventions

Local API base: `http://localhost:3001`. JSON responses use a `data` property. Errors use `{ "error": { "code": "...", "message": "..." } }`. Dates use ISO 8601. Nullable values remain `null` when a source does not publish them.

Protected operations require `X-API-Key: <ADMIN_API_KEY>`. Never include a real API key in a URL or committed example.

## Health and database

### `GET /health`

Checks that the API process responds and returns its version. It does not check PostgreSQL or data availability.

```bash
curl http://localhost:3001/health
```

```json
{ "status": "ok", "version": "1.0.0" }
```

### `GET /api/v1/health/database`

Checks database connectivity. A successful connection does not imply that tables contain fund data.

### `GET /api/v1/stats`

Returns current database counts for funds, NAV observations, configured countries, registered/integrated sources, and latest ETL run.

## Catalog

### `GET /api/v1/countries`

Returns registry and stored-record counts by country code.

### `GET /api/v1/sources`

Returns source metadata, database counts, latest connectivity check, country scope, and whether the source is runnable through the API.

### `GET /api/v1/sources/{source_id}`

Returns one registered source by its stable identifier, such as `sec_open_end_fund_classes`.

### `POST /api/v1/sources/{source_id}/check`

Performs a rate-limited, administrator-authenticated connectivity check for a registered HTTPS endpoint on its configured official host. It checks connectivity, not source format or successful ingestion. Sources without a URL return HTTP 422.

```bash
curl -X POST http://localhost:3001/api/v1/sources/sec_open_end_fund_classes/check \
  -H 'X-API-Key: <ADMIN_API_KEY>'
```

## Funds and observations

### `GET /api/v1/funds`

Searches stored funds. Parameters:

| Parameter | Meaning |
| --- | --- |
| `page`, `limit` | Pagination; page size is capped at 100 |
| `q` | Name or identifier search |
| `country`, `currency`, `isin` | Fund identity filters |
| `category`, `fund_type`, `status` | Source-provided fund metadata filters |
| `has_nav` | `true`/`false` based on stored NAV observations |
| `holdings_status` | `available`, `unavailable`, or `not_checked` |
| `sort`, `order` | Supported sort key and `asc`/`desc` order |

```bash
curl 'http://localhost:3001/api/v1/funds?country=US&has_nav=true&page=1&limit=25'
```

List results include database-backed funds and pagination metadata; optional values may be null.

### `GET /api/v1/funds/{fund_id}`

Returns one fund profile and its latest stored NAV. Metadata comes from the linked source; missing values remain null.

### `GET /api/v1/funds/{fund_id}/nav`

Returns stored NAV history. Optional query parameters: `from`, `to`, and `limit` (maximum 5,000).

```bash
curl 'http://localhost:3001/api/v1/funds/123/nav?from=2026-01-01&to=2026-06-30&limit=100'
```

### `GET /api/v1/funds/{fund_id}/holdings`

Returns holdings for the latest reporting date or a selected date with `report_date=YYYY-MM-DD`. Optional `limit` is capped at 5,000. Position data and separately attributed financial metrics retain source provenance and may be null.

```bash
curl 'http://localhost:3001/api/v1/funds/123/holdings?report_date=2026-06-30'
```

```json
{ "data": [], "status": "unavailable", "reportDate": null, "reportDates": [], "count": 0 }
```

An empty result means no holdings were stored for that fund/report; it does not represent zero-valued positions.

## ETL runs

### `GET /api/v1/etl/runs`

Lists ETL runs. `limit` is 1–100.

### `GET /api/v1/etl/runs/{run_id}`

Returns a run by API UUID or legacy `python-N` ID, including per-source outcomes and errors.

### `POST /api/v1/etl/runs`

Starts an administrator-protected run. Choose one or more `sourceIds`, `countryCodes`, or `all: true`. Selectable connectors are listed by `GET /api/v1/sources` with `runnable: true`.

```bash
curl -X POST http://localhost:3001/api/v1/etl/runs \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: <ADMIN_API_KEY>' \
  -d '{"sourceIds":["sec_open_end_fund_classes"]}'
```

The accepted response uses HTTP 202 and contains the run ID and selected sources. Query the run detail endpoint for outcomes.
