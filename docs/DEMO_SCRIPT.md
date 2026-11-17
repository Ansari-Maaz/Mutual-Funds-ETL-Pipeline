# Demo script

1. Copy `.env.example` to `.env` and set `DATABASE_URL`.
2. Start PostgreSQL with `docker compose up -d db` (host port 5433).
3. Create a virtual environment, install `pip install -r requirements.txt`, then run `alembic upgrade head` and `python -m app.cli sync-sources`.
4. `python -m app.cli inventory` generates the source workbook.
5. `python -m app.cli verify-sources` checks configured official pages and writes JSON/Markdown evidence. Reachability alone does not establish usable fund data.
6. `python -m app.cli run --all` runs available connectors, reports missing local source files as `Skipped`, and writes `reports/latest_run.json` plus the Markdown report when a connector succeeds. Coverage depends on the data snapshot; see the README coverage table.
7. Review `reports/sample_funds.json`, `reports/sample_nav.json`, source-specific manifests and rejected-row logs under `reports/`.

The source inventory includes the official Japan NISA growth and tsumitate fund lists, IMAJ monthly new-fund records, and the South Korean IBK public fund-information CSV, alongside the European fund lists and Hong Kong SFC public-offer list. Japan's lists are tax-quota subsets. IBK records describe funds it handles and do not assert Korean domicile. Canada, Mexico, Singapore, Taiwan and Russia still lack imported country-level datasets.
