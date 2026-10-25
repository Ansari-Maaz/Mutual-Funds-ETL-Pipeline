#!/bin/sh
set -eu

if [ -z "${DATABASE_URL:-}" ]; then
  echo "DATABASE_URL must be set to the intended production PostgreSQL database." >&2
  exit 1
fi

echo "Applying forward-only Alembic migrations to the configured database..."
python -m alembic upgrade head

echo "Synchronizing the source catalog (repeatable upserts; no fund/NAV data is deleted)..."
python -m app.cli sync-sources

echo "Production schema and source catalog are initialized. ETL ingestion is a separate explicit step."
