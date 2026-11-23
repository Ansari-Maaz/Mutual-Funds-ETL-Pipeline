"""Store every official N-PORT holding field plus identifier and SIC crosswalks.

The N-PORT DERA holding file publishes more than the name/quantity/value columns
FundFlow imported first.  These columns keep the filed asset category, issuer
type, country, unit, restriction flag, fair-value level and derivative category.

Two derived crosswalks are added as first-class tables so the enrichment is
reproducible and auditable:

* ``security_identifier_map`` — CUSIP -> ticker/ISIN evidence reported by N-PORT
  filers.  A fund only reports an identifier when it knows it, so the map is
  built from the whole filing population rather than from one holding row.
* ``security_industry`` — ticker -> EDGAR CIK -> SEC SIC code.  SIC is the only
  official issuer industry classification published by the SEC.
"""
from alembic import op
import sqlalchemy as sa

revision = "0015_holding_official_fields"
down_revision = "0014_fund_identifiers"
branch_labels = None
depends_on = None


HOLDING_COLUMNS = (
    ("unit", sa.String(4)),
    ("issuer_lei", sa.String(20)),
    ("issuer_type", sa.String(16)),
    ("asset_category", sa.String(16)),
    ("investment_country", sa.String(3)),
    ("is_restricted", sa.Boolean()),
    ("fair_value_level", sa.SmallInteger()),
    ("derivative_category", sa.String(8)),
    ("payoff_profile", sa.String(200)),
    ("exchange_rate", sa.Numeric(24, 10)),
)


def upgrade():
    for name, type_ in HOLDING_COLUMNS:
        op.add_column("portfolio_holdings", sa.Column(name, type_, nullable=True))
    op.create_index("ix_portfolio_holdings_cusip", "portfolio_holdings", ["cusip"])
    op.create_index("ix_portfolio_holdings_fund_date", "portfolio_holdings", ["fund_id", "reporting_date"])

    op.create_table(
        "security_identifier_map",
        sa.Column("cusip", sa.String(12), primary_key=True),
        sa.Column("ticker", sa.String(50)),
        sa.Column("isin", sa.String(12)),
        sa.Column("ticker_votes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("isin_votes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("evidence_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latest_report_date", sa.Date()),
        sa.Column("source_id", sa.String(100), nullable=False,
                  server_default="sec_nport_identifiers"),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_security_identifier_map_ticker", "security_identifier_map", ["ticker"])
    op.create_index("ix_security_identifier_map_isin", "security_identifier_map", ["isin"])

    op.create_table(
        "security_industry",
        sa.Column("ticker", sa.String(50), primary_key=True),
        sa.Column("cik", sa.String(10)),
        sa.Column("company_name", sa.String(300)),
        sa.Column("sic", sa.String(4)),
        sa.Column("sic_description", sa.String(300)),
        sa.Column("sector", sa.String(200)),
        sa.Column("exchange", sa.String(80)),
        sa.Column("source_id", sa.String(100), nullable=False,
                  server_default="sec_edgar_sic"),
        sa.Column("source_url", sa.Text()),
        sa.Column("updated_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_security_industry_sic", "security_industry", ["sic"])


def downgrade():
    op.drop_index("ix_security_industry_sic", table_name="security_industry")
    op.drop_table("security_industry")
    op.drop_index("ix_security_identifier_map_isin", table_name="security_identifier_map")
    op.drop_index("ix_security_identifier_map_ticker", table_name="security_identifier_map")
    op.drop_table("security_identifier_map")
    for name, _ in reversed(HOLDING_COLUMNS):
        op.drop_column("portfolio_holdings", name)
