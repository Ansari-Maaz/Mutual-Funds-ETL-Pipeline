"""Expand filed holdings and keep sourced metrics separately.

This migration only renames/extends existing holdings storage. It never clears
fund, NAV, holdings, or other production records.
"""
from alembic import op
import sqlalchemy as sa

revision = "0006_portfolio_holding_details"
down_revision = "0005_fund_portfolio_holdings"
branch_labels = None
depends_on = None


def upgrade():
    op.rename_table("fund_holdings", "portfolio_holdings")
    op.execute("ALTER INDEX ix_fund_holdings_fund_id RENAME TO ix_portfolio_holdings_fund_id")
    op.execute("ALTER INDEX ix_fund_holdings_report_date RENAME TO ix_portfolio_holdings_reporting_date")
    op.alter_column("portfolio_holdings", "report_date", new_column_name="reporting_date")
    op.alter_column("portfolio_holdings", "allocation_percentage", new_column_name="portfolio_weight")
    op.drop_constraint("uq_fund_holding_report_item", "portfolio_holdings", type_="unique")
    op.create_unique_constraint("uq_fund_holding_report_item", "portfolio_holdings", ["fund_id", "reporting_date", "holding_index"])
    op.alter_column("portfolio_holdings", "accession_number", existing_type=sa.String(25), nullable=True, type_=sa.String(50))
    op.add_column("portfolio_holdings", sa.Column("isin", sa.String(12), nullable=True))
    op.add_column("portfolio_holdings", sa.Column("market_value_currency", sa.String(3), nullable=True))
    op.add_column("portfolio_holdings", sa.Column("data_source", sa.String(100), server_default="sec_edgar_nport", nullable=False))
    op.alter_column("portfolio_holdings", "security_name", existing_type=sa.String(500), nullable=True)
    op.create_table(
        "holding_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("holding_id", sa.Integer(), sa.ForeignKey("portfolio_holdings.id", ondelete="CASCADE"), nullable=False),
        sa.Column("data_source", sa.String(100), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("first_bought_date", sa.Date(), nullable=True),
        sa.Column("portfolio_weight", sa.Numeric(18, 12), nullable=True),
        sa.Column("share_change_percentage", sa.Numeric(18, 12), nullable=True),
        sa.Column("one_year_return", sa.Numeric(18, 12), nullable=True),
        sa.Column("forward_pe", sa.Numeric(18, 8), nullable=True),
        sa.Column("sector", sa.String(200), nullable=True),
        sa.Column("calculation_basis", sa.Text(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("holding_id", "data_source", "as_of_date", name="uq_holding_metric_source_date"),
    )
    op.create_index("ix_holding_metrics_holding_id", "holding_metrics", ["holding_id"])
    op.create_index("ix_holding_metrics_as_of_date", "holding_metrics", ["as_of_date"])


def downgrade():
    raise RuntimeError(
        "This migration adds sourced historical holding metrics. Downgrade is disabled to prevent data loss; "
        "create a reviewed, data-preserving reverse migration if a rollback is required."
    )
