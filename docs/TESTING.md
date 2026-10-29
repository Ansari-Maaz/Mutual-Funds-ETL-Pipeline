# Testing

Run the focused automated checks from the project root:

```sh
./.venv/bin/python -m pytest
(cd api && npm test)
(cd frontend && npm run build)
```

On 2026-10-29, local checks completed with 17 Python tests, 21 API tests, 1 frontend CSV test, and a successful Vite production build. The Python suite now includes canonical-schema fixture coverage for the Italy, France, Netherlands, Luxembourg Euronext, Allianz Luxembourg, and SIX connectors, plus regression coverage for snapshot refresh, batch deduplication, and GSFM date filtering. The read-only PostgreSQL/API integration check also passed against the local CVM-loaded records. Most API contract tests use a mocked database adapter; they do not replace broader connector/database coverage. Python 3.10+ is supported; this local check used Python 3.14.

For live database verification, install Docker Compose, start PostgreSQL with `docker compose up -d db`, apply migrations with `./.venv/bin/alembic upgrade head`, and start the API before running:

```sh
(cd api && npm run test:integration)
```

The live check validates a previously downloaded official-source manifest, PostgreSQL fund/NAV rows, and the corresponding source, fund-profile, and NAV API responses. It does not refetch providers or mutate source data and does not require the last run report to name the source under test. Do not report the live integration check as passing unless PostgreSQL and the API are running.

The current automated suites remain focused: they do not exercise every connector against provider responses, and the frontend suite does not mount the full React application. Add connector-level fixtures and UI tests when changing those areas.
