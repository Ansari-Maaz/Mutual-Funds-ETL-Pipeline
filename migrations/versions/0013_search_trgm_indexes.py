"""Trigram indexes so the API's ILIKE '%q%' fund search can use an index."""
from alembic import op

revision = "0013_search_trgm_indexes"
down_revision = "0012_etl_run_rejects"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE INDEX IF NOT EXISTS ix_funds_name_trgm ON funds USING gin (name gin_trgm_ops)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_funds_ticker_trgm ON funds USING gin (ticker gin_trgm_ops)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS ix_funds_ticker_trgm")
    op.execute("DROP INDEX IF EXISTS ix_funds_name_trgm")
