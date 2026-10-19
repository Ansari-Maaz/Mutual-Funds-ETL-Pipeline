"""Persist API orchestration and source connectivity history."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_api_operations"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "api_etl_runs",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("source_ids", postgresql.JSONB(), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("stdout", sa.Text(), nullable=False, server_default=""),
        sa.Column("stderr", sa.Text(), nullable=False, server_default=""),
        sa.Column("exit_code", sa.Integer()),
        sa.Column("results", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("error", sa.Text()),
    )
    op.create_index("ix_api_etl_runs_requested_at", "api_etl_runs", ["requested_at"])
    op.create_table(
        "api_source_checks",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("source_id", sa.String(100), sa.ForeignKey("sources.source_id"), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("http_status", sa.Integer()),
        sa.Column("response_time_ms", sa.Integer()),
        sa.Column("error", sa.Text()),
    )
    op.create_index("ix_api_source_checks_source_id_checked_at", "api_source_checks", ["source_id", "checked_at"])


def downgrade():
    op.drop_index("ix_api_source_checks_source_id_checked_at", table_name="api_source_checks")
    op.drop_table("api_source_checks")
    op.drop_index("ix_api_etl_runs_requested_at", table_name="api_etl_runs")
    op.drop_table("api_etl_runs")
