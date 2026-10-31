# Testing

Run the automated checks from the project root:

```sh
./.venv/bin/python -m pytest -q
(cd api && npm test)
(cd frontend && npm test && npm run build)
```

GitHub Actions runs these three suites for pull requests and pushes to `main`. The ETL workflow remains a separate scheduled/manual job because it writes to the configured database.

## Verification on 2026-10-31

The current working tree passed 21 Python tests, 22 API tests, all 4 frontend test files, and a Vite production build. Python bytecode compilation and `git diff --check` also passed. The API test suite binds a local ephemeral HTTP server and uses mocked database adapters; no production connection was made. A read-only integration check against local PostgreSQL passed for CVM fund and NAV records. No live production connection or ETL run was made.

On 2026-10-29, local checks completed with 18 Python tests, 21 API tests, 1 frontend CSV test, and a successful Vite production build. The Python suite includes canonical-schema fixture coverage for the Italy, France, Netherlands, Luxembourg Euronext, Allianz Luxembourg, and SIX connectors, regression coverage for snapshot refresh and batch deduplication, GSFM date filtering, and persistence of failed ETL attempts for unregistered sources. The read-only PostgreSQL/API integration check also passed against the local CVM-loaded records. Most API contract tests use a mocked database adapter; they do not replace broader connector/database coverage. Python 3.10+ is supported; this local check used Python 3.14.

For live database verification, install Docker Compose, start PostgreSQL with `docker compose up -d db`, apply migrations with `./.venv/bin/alembic upgrade head`, and start the API before running:

```sh
(cd api && npm run test:integration)
```

The live check validates a previously downloaded official-source manifest, PostgreSQL fund/NAV rows, and the corresponding source, fund-profile, and NAV API responses. It does not refetch providers or mutate source data and does not require the last run report to name the source under test. Do not report the live integration check as passing unless PostgreSQL and the API are running.

The automated suites exercise representative connectors, ingestion failure and deduplication paths, API contracts, frontend formatting/request helpers, and checks that JSX component names are imported or declared. They do not exercise every connector against live provider responses, and the frontend suite does not mount the full React application. Keep adding fixture tests as connectors and UI behavior change.
