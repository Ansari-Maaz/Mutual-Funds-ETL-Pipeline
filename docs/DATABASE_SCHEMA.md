# Database schema

- `sources`: source identity plus verification, integration, and licensing statuses.
- `funds`: source-native ID, name, domicile, currency, ISIN; unique per source/native ID.
- `nav_observations`: Decimal NAV by fund/date/currency with an idempotency constraint.
- `etl_runs`: Python CLI run timestamps, state, source, counts, and error text.
- `api_etl_runs`: API-triggered run requests, process output, JSON results, and status.
- `api_source_checks`: API connectivity-check history for registered sources.

Apply with `alembic upgrade head`. Example queries:

The checked submission snapshot contains 24 registered source rows, 162,584 funds, and 252,030 NAV observations. Counts are data-snapshot evidence, not a claim of complete national market coverage. Apply migrations with `alembic upgrade head`; refresh the snapshot with the documented ETL commands.

```sql
SELECT country_code, count(*) FROM sources GROUP BY country_code ORDER BY country_code;
SELECT f.name, n.valuation_date, n.nav, n.currency FROM funds f JOIN nav_observations n ON n.fund_id=f.id WHERE f.id=:fund_id ORDER BY n.valuation_date;
SELECT status, count(*) FROM etl_runs GROUP BY status;
```

```mermaid
erDiagram
  sources ||--o{ funds : provides
  funds ||--o{ nav_observations : has
  sources ||--o{ etl_runs : runs
```
