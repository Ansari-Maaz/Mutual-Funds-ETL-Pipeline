"""Index legacy individual N-PORT holdings by filing accession.

Rows written by ``sync-sec-holdings`` predate the Item C.4 columns and are
backfilled from the cached SEC submission text.  A partial index keeps that
join off the 85-million-row sequential scan; bulk-importer rows are excluded
because they already carry every filed field.
"""
from alembic import op
import sqlalchemy as sa

revision = "0017_nport_individual_accession"
down_revision = "0016_security_fundamentals"
branch_labels = None
depends_on = None


def upgrade():
    op.create_index(
        "ix_portfolio_holdings_individual_accession",
        "portfolio_holdings",
        ["accession_number", "holding_index"],
        postgresql_where=sa.text("data_source = 'sec_edgar_nport'"),
    )


def downgrade():
    op.drop_index("ix_portfolio_holdings_individual_accession",
                  table_name="portfolio_holdings")
