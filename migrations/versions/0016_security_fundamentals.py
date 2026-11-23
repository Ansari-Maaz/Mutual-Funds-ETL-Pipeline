"""Add SEC-XBRL fundamentals and an official trailing P/E per holding.

Forward P/E cannot be populated from an official U.S. source: no SEC filing
publishes analyst earnings estimates.  A *trailing* P/E can be derived entirely
from official facts:

* the N-PORT filed market value and balance give a price per share, and
* the issuer's SEC XBRL ``EarningsPerShareDiluted`` fact gives annual EPS.

``security_fundamentals`` caches the XBRL EPS fact per ticker.  The new
``holding_metrics`` columns keep the ratio and its exact EPS period so the API
and UI can show provenance instead of a bare number.
"""
from alembic import op
import sqlalchemy as sa

revision = "0016_security_fundamentals"
down_revision = "0015_holding_official_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("holding_metrics", sa.Column("trailing_pe", sa.Numeric(18, 8)))
    op.add_column("holding_metrics", sa.Column("trailing_eps", sa.Numeric(18, 8)))
    op.add_column("holding_metrics", sa.Column("eps_period_end", sa.Date()))
    op.add_column("holding_metrics", sa.Column("trailing_pe_basis", sa.Text()))

    op.create_table(
        "security_fundamentals",
        sa.Column("ticker", sa.String(50), primary_key=True),
        sa.Column("cik", sa.String(10)),
        sa.Column("company_name", sa.String(300)),
        sa.Column("eps", sa.Numeric(18, 8)),
        sa.Column("eps_measure", sa.String(40)),
        sa.Column("eps_period_start", sa.Date()),
        sa.Column("eps_period_end", sa.Date()),
        sa.Column("eps_filed", sa.Date()),
        sa.Column("fiscal_year", sa.Integer()),
        sa.Column("source_id", sa.String(100), nullable=False,
                  server_default="sec_xbrl_eps"),
        sa.Column("source_url", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_security_fundamentals_cik", "security_fundamentals", ["cik"])


def downgrade():
    op.drop_index("ix_security_fundamentals_cik", table_name="security_fundamentals")
    op.drop_table("security_fundamentals")
    op.drop_column("holding_metrics", "trailing_pe_basis")
    op.drop_column("holding_metrics", "eps_period_end")
    op.drop_column("holding_metrics", "trailing_eps")
    op.drop_column("holding_metrics", "trailing_pe")
