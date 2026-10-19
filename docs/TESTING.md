# Testing

Run the focused automated checks from the project root:

```sh
./.venv/bin/python -m pytest
(cd api && npm test)
(cd frontend && npm run build)
```

The current checked result is 7 Python tests, 15 API tests, and a successful Vite production build. Python 3.10+ is supported; the local verification environment currently uses Python 3.14.

For live database verification, install Docker Compose, start PostgreSQL with `docker compose up -d db`, apply migrations with `./.venv/bin/alembic upgrade head`, and start the API before running:

```sh
(cd api && npm run test:integration)
```

The live check validates a previously downloaded official-source manifest, PostgreSQL fund/NAV rows, and the corresponding API responses. It does not refetch providers or mutate source data. Do not report the live integration check as passing unless PostgreSQL and the API are running.
