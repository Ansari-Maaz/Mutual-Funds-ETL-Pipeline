# Implementation plan and status

1. Establish a country/source catalog for the 20 core markets and four expansion markets — cataloged.
2. Build Python ETL framework and canonical models — implemented.
3. Add PostgreSQL persistence and Alembic migration — implemented.
4. Add conservative HTTP source verifier and CLI — implemented.
5. Generate Excel inventory and run reports — implemented.
6. Integrate source datasets — the saved local snapshot dated 2026-10-28 records 51 source rows and 30 sources marked integrated. It includes fund and NAV rows for France, Italy, the Netherlands, Luxembourg and Denmark; actual coverage varies by feed.
7. Add missing country sources — consult the current [coverage evidence](../reports/FundFlow_Country_Coverage_New.csv) and [limitations](LIMITATIONS.md); the snapshot has fund records in 18 of the 24 target markets. This dated snapshot does not establish current live or production coverage.
8. Expand NAV history and confirm provider reuse terms — ongoing. Several connected registers remain fund-master-only. Raw file snapshots are reproducible only where an upstream downloadable export is available.

See `reports/dataset_research.md`, `reports/latest_run.md` and `docs/LIMITATIONS.md` for current status.
