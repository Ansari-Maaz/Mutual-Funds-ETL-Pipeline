# Recruiter handoff — Global Mutual Fund ETL

## Files to share

1. **Project source and downloaded data:** `deliverables/MF_ETL_Recruiter_Package.zip` (contains the ETL/API/frontend source, docs, reports, raw snapshots, and provenance manifest; local secrets and dependency folders are excluded).
2. **Project overview:** `README.md`.
3. **Results and import scope:** `reports/SUBMISSION_SUMMARY.md` and `reports/dataset_research.md`.
4. **Source evidence:** `reports/source_data_manifest.md`, `reports/source_catalogue.json`, and `reports/*_dataset_manifest.json`.
5. **Database structure:** `reports/conversation_and_postgresql_schema.md` and `migrations/`.
6. **Data quality / run evidence:** `reports/latest_run.md`, `reports/source_verification.md`, and `reports/global_mutual_fund_source_inventory.xlsx`.
7. **Limitations:** `docs/LIMITATIONS.md`.

The ZIP contains the project source code and all files under `data/raw/`, including the downloaded source snapshots. It excludes `.env` secrets, `.venv`, and `node_modules`; a recruiter can recreate dependencies using the README. A PostgreSQL database dump is not included; the schema migrations are included.

## What the project currently demonstrates

- Python ETL connectors and PostgreSQL storage, with a Node.js REST API and a React dashboard.
- Source provenance, ingestion reports, rejected-row outputs, and reproducible raw input snapshots.
- Imported fund-master datasets for the countries listed in the submission summary. Some imported source lists do not include NAV, and the Hong Kong regulator list reflects products offered there rather than Hong Kong domicile.
- The full requested 20-country coverage is not complete. Canada, Mexico, Japan, South Korea, Singapore, Taiwan and Russia still lack imported datasets; the UAE is also outstanding among expansion markets. Do not present the project as complete coverage of all 20 countries.

## Before sending

- Review the source-data license and commercial-reuse status in the source catalogue; those rights were not cleared for redistribution.
- Replace any machine-specific paths in a recruiter-facing copy if you add a CV or cover letter.
- Keep `.env` and API keys private. They are deliberately absent from the package.
