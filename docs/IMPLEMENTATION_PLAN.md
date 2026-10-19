# Implementation plan and status

1. Establish a country/source catalog for the 20 core markets and four expansion markets — cataloged.
2. Build Python ETL framework and canonical models — implemented.
3. Add PostgreSQL persistence and Alembic migration — implemented.
4. Add conservative HTTP source verifier and CLI — implemented.
5. Generate Excel inventory and run reports — implemented.
6. Integrate source datasets — 17 connectors currently run. In addition to the original sources, official country-level open-ended fund lists have been imported for Germany, Italy, the Netherlands, Denmark and Luxembourg; SFC-authorised public-offer products are imported for Hong Kong with domicile left null. Spain is additional to requested scope.
7. Add missing country sources — Canada, Mexico, Japan, South Korea, Singapore, Taiwan, Russia and UAE remain unimported.
8. Expand NAV history and confirm provider reuse terms — remaining. Most new European and Hong Kong records are fund-master snapshots without NAV.

See `reports/dataset_research.md`, `reports/latest_run.md` and `docs/LIMITATIONS.md` for current status.
