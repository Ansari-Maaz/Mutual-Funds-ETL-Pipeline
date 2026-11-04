"""Add source-backed historical profile data groups."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_fund_profile_snapshots"
down_revision = "0007_single_active_api_etl_run"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "fund_profile_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fund_id", sa.Integer(), sa.ForeignKey("funds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_id", sa.String(100), sa.ForeignKey("sources.source_id"), nullable=False),
        sa.Column("dataset", sa.String(40), nullable=False),
        sa.Column("source_report_date", sa.Date(), nullable=True),
        sa.Column("snapshot_key", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("fund_id", "source_id", "snapshot_key", name="uq_fund_profile_source_snapshot"),
    )
    op.create_index("ix_fund_profile_snapshots_fund_id", "fund_profile_snapshots", ["fund_id"])
    op.create_index("ix_fund_profile_snapshots_source_id", "fund_profile_snapshots", ["source_id"])
    op.create_index("ix_fund_profile_snapshots_dataset", "fund_profile_snapshots", ["dataset"])
    op.create_index("ix_fund_profile_snapshots_source_report_date", "fund_profile_snapshots", ["source_report_date"])


def downgrade():
    op.drop_index("ix_fund_profile_snapshots_source_report_date", table_name="fund_profile_snapshots")
    op.drop_index("ix_fund_profile_snapshots_dataset", table_name="fund_profile_snapshots")
    op.drop_index("ix_fund_profile_snapshots_source_id", table_name="fund_profile_snapshots")
    op.drop_index("ix_fund_profile_snapshots_fund_id", table_name="fund_profile_snapshots")
    op.drop_table("fund_profile_snapshots")
