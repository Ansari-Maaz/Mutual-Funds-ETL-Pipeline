"""Enforce one queued/running API ETL job across all API processes."""
from alembic import op

revision = "0007_single_active_api_etl_run"
down_revision = "0006_portfolio_holding_details"
branch_labels = None
depends_on = None


def upgrade():
    # A constant expression makes this a database-wide singleton constraint.
    # It protects multiple API workers, where an in-process Set is insufficient.
    op.execute(
        "CREATE UNIQUE INDEX uq_api_etl_runs_single_active "
        "ON api_etl_runs ((1)) WHERE status IN ('queued', 'running')"
    )


def downgrade():
    op.execute("DROP INDEX uq_api_etl_runs_single_active")
