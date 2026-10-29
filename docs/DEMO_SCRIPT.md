# Demo script

1. Copy `.env.example` to `.env` and set `DATABASE_URL`.
2. Start PostgreSQL with `docker compose up -d db` (host port 5433).
3. Create a virtual environment, install `pip install -r requirements.txt`, then run `alembic upgrade head` and `python -m app.cli sync-sources`.
4. `python -m app.cli inventory` generates the source workbook.
5. `python -m app.cli verify-sources` checks configured official pages and writes JSON/Markdown evidence. Reachability alone does not establish usable fund data.
6. `python -m app.cli run --all` runs available connectors, reports missing local source files as `Skipped`, and writes `reports/latest_run.json` plus the Markdown report when a connector succeeds. Coverage depends on the data snapshot; see the README coverage table.
7. Review `reports/sample_funds.json`, `reports/sample_nav.json`, source-specific manifests and rejected-row logs under `reports/`.

The source inventory now includes official open-ended fund lists for Germany, Italy, the Netherlands, Denmark and Luxembourg, and the Hong Kong SFC public-offer list. Seven core countries still lack an imported dataset: Canada, Mexico, Japan, South Korea, Singapore, Taiwan and Russia.
