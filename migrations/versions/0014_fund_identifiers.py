"""Add fund_identifiers: many external identifiers (ISIN, LEI, CUSIP, national codes) per fund."""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0014_fund_identifiers"
down_revision = "0013_search_trgm_indexes"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "fund_identifiers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("fund_id", sa.Integer(), sa.ForeignKey("funds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("id_type", sa.String(20), nullable=False),
        sa.Column("value", sa.String(64), nullable=False),
        sa.Column("source_id", sa.String(100), nullable=False),
        sa.Column("share_class", sa.String(300)),
        sa.Column("currency", sa.String(3)),
        sa.Column("attributes", postgresql.JSONB()),
        sa.Column("source_url", sa.Text()),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("fund_id", "id_type", "value", "source_id", name="uq_fund_identifier"),
    )
    op.create_index("ix_fund_identifiers_fund_id", "fund_identifiers", ["fund_id"])
    op.create_index("ix_fund_identifiers_lookup", "fund_identifiers", ["id_type", "value"])


def downgrade():
    op.drop_index("ix_fund_identifiers_lookup", table_name="fund_identifiers")
    op.drop_index("ix_fund_identifiers_fund_id", table_name="fund_identifiers")
    op.drop_table("fund_identifiers")
