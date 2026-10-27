"""Store SEC N-PORT portfolio snapshots and fund availability."""
from alembic import op
import sqlalchemy as sa

revision = "0005_fund_portfolio_holdings"
down_revision = "0004_extended_fund_profile"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("funds", sa.Column("sec_series_id", sa.String(10), nullable=True))
    op.add_column("funds", sa.Column("sec_cik", sa.String(10), nullable=True))
    op.add_column("funds", sa.Column("holdings_status", sa.String(20), server_default="not_checked", nullable=False))
    op.add_column("funds", sa.Column("holdings_report_date", sa.Date(), nullable=True))
    op.create_index("ix_funds_sec_series_id", "funds", ["sec_series_id"])
    op.create_table(
        "fund_holdings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fund_id", sa.Integer(), sa.ForeignKey("funds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("accession_number", sa.String(25), nullable=False),
        sa.Column("holding_index", sa.Integer(), nullable=False),
        sa.Column("security_name", sa.String(500), nullable=False),
        sa.Column("ticker", sa.String(50), nullable=True),
        sa.Column("cusip", sa.String(12), nullable=True),
        sa.Column("quantity", sa.Numeric(36, 12), nullable=True),
        sa.Column("market_value", sa.Numeric(36, 12), nullable=True),
        sa.Column("allocation_percentage", sa.Numeric(18, 12), nullable=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("fund_id", "report_date", "accession_number", "holding_index", name="uq_fund_holding_report_item"),
    )
    op.create_index("ix_fund_holdings_fund_id", "fund_holdings", ["fund_id"])
    op.create_index("ix_fund_holdings_report_date", "fund_holdings", ["report_date"])


def downgrade():
    op.drop_table("fund_holdings")
    op.drop_index("ix_funds_sec_series_id", table_name="funds")
    for column in ("holdings_report_date", "holdings_status", "sec_cik", "sec_series_id"):
        op.drop_column("funds", column)
