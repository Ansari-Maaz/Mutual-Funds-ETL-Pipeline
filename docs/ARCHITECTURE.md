# Architecture

The project has three runtime surfaces:

- Python CLI → provider connector → canonical Pydantic validation → SQLAlchemy PostgreSQL upserts.
- Express REST API → parameterized PostgreSQL queries and protected ETL process orchestration.
- React/Vite dashboard → REST API for monitoring, source checks, fund search, NAV history, and ETL control.

Source configuration separates verification, licensing, and integration state. Records retain source IDs. NAV observations are idempotent by fund/date/currency, and API-launched runs are serialized with a PostgreSQL advisory lock.

```mermaid
erDiagram
  SOURCES ||--o{ FUNDS : provides
  FUNDS ||--o{ NAV_OBSERVATIONS : records
  SOURCES ||--o{ ETL_RUNS : audited_by
```

The Python orchestration, API orchestration, and dashboard are implemented. Provider coverage remains intentionally incomplete: the dated local snapshot records 30 integrated source rows, and six target markets have no fund records in that snapshot. See `reports/latest_run.md` and `docs/LIMITATIONS.md` for the evidence-backed coverage boundary.
