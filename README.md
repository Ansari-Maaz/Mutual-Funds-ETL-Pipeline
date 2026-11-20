# FundFlow — Global Mutual Fund ETL Platform

FundFlow collects mutual-fund reference data, NAV observations, and selected portfolio holdings from public and provider sources. Python connectors validate and normalize source data into PostgreSQL. An Express API and React dashboard let users search records, inspect coverage, and monitor ETL runs.

> **Data note:** source coverage varies by provider and market. Fund records are source records, not a deduplicated global count. NAV and holdings appear only when an ingested source publishes them. The repository does not include the local database volume or its records.

<p align="center">
  <a href="https://github.com/Ansari-Maaz/Mutual-Funds-ETL-Pipeline/actions/workflows/quality.yml"><img alt="Quality checks" src="https://github.com/Ansari-Maaz/Mutual-Funds-ETL-Pipeline/actions/workflows/quality.yml/badge.svg"></a>
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white">
  <img alt="PostgreSQL 16" src="https://img.shields.io/badge/PostgreSQL-16-4169E1?logo=postgresql&logoColor=white">
  <img alt="Node.js and Express" src="https://img.shields.io/badge/API-Node.js%20%2B%20Express-339933?logo=nodedotjs&logoColor=white">
  <img alt="React and Vite" src="https://img.shields.io/badge/UI-React%20%2B%20Vite-646CFF?logo=vite&logoColor=white">
</p>

## Demo

<!-- GitHub renders an inline player when this is a GitHub-uploaded video asset URL. -->
<!-- Upload `docs/media/Demo Preview.mp4` in GitHub's README editor and paste its generated URL below. -->
<!-- GITHUB_VIDEO_ASSET_URL -->

> **Local preview:** [`docs/media/Demo Preview.mp4`](docs/media/Demo%20Preview.mp4) (compressed H.264 copy); original: [`docs/media/Demo Video.webm`](docs/media/Demo%20Video.webm). GitHub's inline player requires its generated `https://github.com/user-attachments/assets/...` URL on its own line.

## What the project does

| Feature | What you can do |
| --- | --- |
| Overview | View database health, fund/NAV counts, country coverage, source status, latest runs, and recently retrieved funds. |
| Fund explorer | Search and filter funds; inspect profiles, identifiers, latest NAV, NAV history, and available holdings; export results as CSV. |
| Portfolio holdings | Browse positions by reporting date where a connected source publishes holdings. Optional sourced metrics are stored separately from filed positions. |
| US coverage | Review NAV and holdings coverage, reporting status, profile-field completeness, and provider-level data gaps. |
| Source registry | Search source organizations, ingestion status, record counts, formats, official links, and connectivity-check results. |
| ETL control | Queue all connectors or selected countries and inspect run status, outcomes, process output, and errors. Run controls require an admin API key. |
| API explorer and docs | Send API requests, inspect JSON responses, and use the interactive API reference and OpenAPI specification. |
| Python ETL | Extract, validate, normalize, and upsert supported public/provider data. Run reports, manifests, provenance, and rejects are written under `reports/`. |

Missing source values are left empty; the application does not invent financial data. See [limitations](docs/LIMITATIONS.md) and [source inventory](reports/FundFlow_Data_Source_Inventory_New.csv) for coverage details.

## Quick start

| Need | Version or value |
| --- | --- |
| Docker Compose | Docker Engine with Compose plugin |
| Python | 3.10+ |
| Node.js | 20+ and npm |
| PostgreSQL | Started locally by Docker Compose |
| Dashboard | `http://localhost:5173` |
| API docs | `http://localhost:3001/api/docs` |
| Database | `localhost:5433`, database/user/password `mfetl` |

```bash
git clone https://github.com/Ansari-Maaz/Mutual-Funds-ETL-Pipeline.git
cd Mutual-Funds-ETL-Pipeline
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
docker compose up -d db
alembic upgrade head
python -m app.cli sync-sources
```

Then start each service in its own terminal:

```bash
cd api && cp .env.example .env && npm ci && npm start
```

```bash
cd frontend && npm ci && npm run dev
```

Open `http://localhost:5173`. The schema and source catalogue do not import fund records. To fetch available provider data, run `python -m app.cli run --all`. Some connectors require configuration or may be temporarily unavailable. See the [full local setup guide](#clone-and-run-locally).

## Architecture and data flow

### Application architecture

```mermaid
flowchart LR
  USER[Developer or analyst] --> WEB[React and Vite dashboard]
  WEB --> API[Express REST API]
  API --> DB[(PostgreSQL)]
  CLI[Python CLI or scheduled GitHub Action] --> ETL[Python ETL connectors]
  API -->|authenticated run request| ETL
  ETL --> SRC[Public regulators and provider feeds]
  SRC --> ETL
  ETL --> DB
  ETL --> AUDIT[Run reports, manifests, rejects]
```

### ETL data flow

```mermaid
flowchart TD
  A[Choose connector or source] --> B[Fetch provider data]
  B --> C[Parse and map source fields]
  C --> D{Schema validation}
  D -->|valid| E[Normalize canonical records]
  D -->|invalid| F[Record rejects and errors]
  E --> G[Idempotent PostgreSQL upsert]
  G --> H[Record extracted and loaded counts]
  H --> I[Write run report and manifest]
```

The API serves database records to the dashboard. ETL can run through the CLI, scheduled workflows, or an authenticated API request. See [ETL lifecycle](docs/FUND_FLOW.md), [architecture notes](docs/ARCHITECTURE.md), and [database schema](docs/DATABASE_SCHEMA.md).

## Clone and run locally

### Requirements

- Git
- Docker Engine with Docker Compose
- Python 3.10 or newer
- Node.js 20 or newer and npm
- `psql` (optional; useful for directly browsing PostgreSQL)

| Service | Local address | Purpose |
| --- | --- | --- |
| Dashboard | `http://localhost:5173` | Search, explore, and monitor data |
| API | `http://localhost:3001` | REST API and interactive docs at `/api/docs` |
| PostgreSQL | `localhost:5433` | Local persistent database; credentials are in `.env.example` |

### 1. Clone the repository

```bash
git clone https://github.com/Ansari-Maaz/Mutual-Funds-ETL-Pipeline.git
cd Mutual-Funds-ETL-Pipeline
```

### 2. Configure Python and the database URL

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
cp .env.example .env
```

The defaults in `.env.example` work with the included local database. Set `USER_AGENT` to an application name and a monitored contact email before using SEC connectors. Never commit `.env` or secrets.

### 3. Start PostgreSQL and create the schema

```bash
docker compose up -d db
docker compose ps
alembic upgrade head
python -m app.cli sync-sources
```

PostgreSQL listens on `localhost:5433`; the database, username, and password default to `mfetl`. Compose creates a persistent local volume. `sync-sources` registers the source catalogue; migrations and source registration do **not** import fund/NAV/holdings records.

### 4. Ingest data

Run the registered connectors:

```bash
python -m app.cli inventory
python -m app.cli run --all
```

Or run one provider connector by its source ID:

```bash
python -m app.cli run --source cvm_open_fund_data
```

Some connectors need additional source files, have provider-specific date limits, or may be unavailable when the provider blocks requests. Check `reports/latest_run.md`, `reports/latest_run.json`, source manifests, and reject files after a run. For examples of separate holdings imports, see [US data refresh](docs/US_DATA_REFRESH.md) and [adding a source](docs/ADDING_A_SOURCE.md).

### 5. Start the API

In a second terminal, from the repository root:

```bash
cd api
cp .env.example .env
npm ci
```

Set a new local `ADMIN_API_KEY` in `api/.env`, then start the server:

```bash
npm start
```

The API listens at [http://localhost:3001](http://localhost:3001). It reads `DATABASE_URL` from the root `.env` and the admin key from `api/.env`.

### 6. Start the dashboard

In a third terminal, from the repository root:

```bash
cd frontend
npm ci
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The Vite development server proxies `/api` requests to the local API.

### Stop local services

Stop Node processes with `Ctrl+C`. Stop PostgreSQL and keep its data volume with:

```bash
docker compose down
```

To remove the local database volume and all records in it, run `docker compose down -v`. This is destructive; do not use it if you need the local data.

## Browse the database

Connect with `psql`:

```bash
psql "postgresql://mfetl:mfetl@localhost:5433/mfetl"
```

At the `mfetl=#` prompt, run each command separately:

```text
\dt
\d funds
```

```sql
SELECT COUNT(*) FROM funds;
SELECT id, name, domicile_country, currency, isin FROM funds ORDER BY id LIMIT 20;
SELECT fund_id, valuation_date, nav, currency FROM nav_observations ORDER BY valuation_date DESC LIMIT 20;
```

Tables include `sources`, `funds`, `nav_observations`, `portfolio_holdings`, `holding_metrics`, `fund_profile_snapshots`, `fund_identifiers`, `etl_runs`, `api_etl_runs`, and `api_source_checks`. Alembic also creates `alembic_version` to track migrations.

For a GUI, connect DBeaver or pgAdmin with host `localhost`, port `5433`, database `mfetl`, username `mfetl`, and password `mfetl`. Expand **Schemas → public → Tables**, then use the table’s data view. To export an entire table from `psql`, use `\copy funds TO 'funds.csv' CSV HEADER`; replace `funds` with another table. Large tables can contain millions of rows.

### Current local database snapshot

The persistent database used while this README was updated contained the following records on **2026-11-20**. This is a local database snapshot, not a promise about a fresh clone or a hosted service. A fresh clone starts with an empty data volume; run connectors to populate it.

| Table | Rows on 2026-11-20 |
| --- | ---: |
| `sources` | 77 |
| `funds` | 187,024 |
| `nav_observations` | 1,682,763 |
| `portfolio_holdings` | 14,667,045 |
| `fund_profile_snapshots` | 778,488 |
| `holding_metrics` | 267 |
| `fund_identifiers` | 9,870 |
| `etl_runs` | 387 |
| `api_etl_runs` | 7 |
| `api_source_checks` | 15 |
| `alembic_version` | 1 |

Counts change when ETL runs. The dashboard and `GET /api/v1/stats` read the configured database live. Country-level figures in older files under `reports/` are dated research snapshots; use the dashboard or `GET /api/v1/countries` for current counts.

## Database reference

### Relationship diagram

```mermaid
erDiagram
  SOURCES ||--o{ FUNDS : provides
  SOURCES ||--o{ NAV_OBSERVATIONS : attributes
  FUNDS ||--o{ NAV_OBSERVATIONS : has
  FUNDS ||--o{ PORTFOLIO_HOLDINGS : reports
  PORTFOLIO_HOLDINGS ||--o{ HOLDING_METRICS : enriches
  FUNDS ||--o{ FUND_PROFILE_SNAPSHOTS : snapshots
  SOURCES ||--o{ FUND_PROFILE_SNAPSHOTS : publishes
  FUNDS ||--o{ FUND_IDENTIFIERS : identifies
  SOURCES ||--o{ ETL_RUNS : tracks
  SOURCES ||--o{ API_SOURCE_CHECKS : checks
```

### Table guide

| Table | What it stores | Main relationship |
| --- | --- | --- |
| `sources` | Provider and regulator registry, coverage, integration and license status | One source can provide many funds and runs |
| `funds` | Source-native fund identity and normalized profile fields | Parent for NAV, holdings, profile snapshots and identifiers |
| `nav_observations` | Dated NAV and optional OHLC values | Belongs to a fund; may reference its source |
| `portfolio_holdings` | Filed security positions by fund and report date | Belongs to a fund; may have optional metrics |
| `holding_metrics` | Separately sourced or derived metrics for a holding | Belongs to one portfolio holding |
| `fund_profile_snapshots` | Versioned, source-backed profile datasets | Belongs to a fund and source |
| `fund_identifiers` | LEI, CUSIP, ISIN and other external identifiers | Belongs to a fund |
| `etl_runs` | Python connector run state, counts, source and errors | May reference a source |
| `api_etl_runs` | API-triggered run requests, status and process output | Run request history |
| `api_source_checks` | Source connectivity check outcomes | References a source |
| `alembic_version` | Database migration version | Migration bookkeeping |

For column-level details, see [database schema](docs/DATABASE_SCHEMA.md). To browse live records, follow the commands in [Browse the database](#browse-the-database).

## API quick reference

Base URL: `http://localhost:3001`. Interactive API reference: [http://localhost:3001/api/docs](http://localhost:3001/api/docs). OpenAPI document: [`api/openapi.json`](api/openapi.json).

| Method | Route | Use |
| --- | --- | --- |
| GET | `/health` | API process health |
| GET | `/api/v1/health/database` | Database connectivity |
| GET | `/api/v1/stats` | Live record counts and ETL status |
| GET | `/api/v1/countries` | Country-level source, fund, and NAV counts |
| GET | `/api/v1/sources` | Source catalogue and ingestion counts |
| GET | `/api/v1/funds` | Search and filter fund records |
| GET | `/api/v1/funds/:id` | Fund profile and latest NAV |
| GET | `/api/v1/funds/:id/nav` | NAV history |
| GET | `/api/v1/funds/:id/holdings` | Current or historical holdings |
| GET | `/api/v1/coverage/us` | US data completeness and gaps |
| GET | `/api/v1/etl/runs` | ETL run history |
| POST | `/api/v1/etl/runs` | Start an authenticated ETL run |

ETL controls and source connectivity checks require the `X-API-Key` header. The API returns JSON; a `NOT_FOUND` response at `/` is expected because the API root is not a web page.

## Project structure

```text
.
├── api/                    Express API, routes, services, and API tests
├── app/                    Python CLI and ETL application
│   ├── connectors/         Source-specific country/provider connectors
│   ├── enrichment/         Fund profile and identifier enrichment
│   ├── etl/                Extract, transform, load, and run tracking
│   ├── holdings/           Holdings importers
│   ├── models/             SQLAlchemy database models
│   └── schemas/            Canonical validation schemas
├── config/                 Source catalogue configuration
├── docs/                   Architecture, API, schema, setup, and limitations
│   ├── media/              Demo video
│   └── screenshots/        Dashboard screenshots
├── frontend/               React/Vite dashboard and tests
├── migrations/             Alembic database migrations
├── reports/                Manifests, audit results, samples, and reports
├── research_notes/         Source research and field-gap notes
├── scripts/                Audits, refreshes, imports, and maintenance jobs
├── tests/                  Python test suite
├── docker-compose.yml      Local PostgreSQL service
├── Dockerfile              Python ETL container image
├── pyproject.toml          Python package/tool configuration
└── requirements.txt        Python dependencies
```

## Screenshots

The existing screenshots are retained below.

### Overview

![FundFlow overview dashboard](docs/screenshots/fundflow-overview.png)

### Fund Explorer

![Fund Explorer with country and advanced filters](docs/screenshots/fundflow-fund-explorer.png)

### ETL Control

![ETL control and run history](docs/screenshots/fundflow-etl-control.png)

### API Explorer

![API request explorer](docs/screenshots/fundflow-api-explorer.png)

## GitHub Actions

- [`quality.yml`](.github/workflows/quality.yml) runs Python tests, PostgreSQL integration tests, API tests, and the frontend build for pushes to `main`, pull requests, and manual runs.
- [`etl.yml`](.github/workflows/etl.yml) supports manual and scheduled ETL. It needs repository secrets `DATABASE_URL` and `USER_AGENT`. The SEC user agent should identify the application and include a monitored contact email.
- The SEC money-market and quarterly holdings workflows are scheduled separately because those official datasets publish on monthly and quarterly schedules.

External sources can change, rate-limit, or go offline, so no workflow can guarantee every future ingestion succeeds. The ETL run reports connector-level outcomes; inspect the Actions logs and `reports/latest_run.*` rather than assuming that a green workflow means complete global coverage.

## Checks and troubleshooting

Run the same checks used by the quality workflow:

```bash
python -m pytest -q
(cd api && npm ci && npm test)
(cd frontend && npm ci && npm test && npm run build)
```

Common issues:

- **Connection refused on port 5433:** start PostgreSQL with `docker compose up -d db`, then check `docker compose ps`.
- **API exits on startup:** confirm the root `.env` contains the correct `DATABASE_URL` and PostgreSQL is healthy.
- **Dashboard has no fund records:** schema setup and `sync-sources` only create schema/source rows; run one or more ETL connectors.
- **ETL source fails:** inspect the source’s latest run report. Provider outage, rate limits, missing optional input files, source format changes, or contact/user-agent requirements can affect an individual connector.
- **`psql` runs commands together:** enter `\\dt` on its own line, then enter SQL statements separately.

Additional references: [API](docs/API.md), [architecture](docs/ARCHITECTURE.md), [database schema](docs/DATABASE_SCHEMA.md), [testing](docs/TESTING.md), [data flow](docs/FUND_FLOW.md), and [limitations](docs/LIMITATIONS.md).
