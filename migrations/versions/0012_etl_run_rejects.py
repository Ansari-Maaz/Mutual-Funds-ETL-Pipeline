"""Persist rejected-record counts on ETL runs and enforce known status values."""
from alembic import op
import sqlalchemy as sa

revision = "0012_etl_run_rejects"
down_revision = "0011_currency_basis"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("etl_runs", sa.Column("records_rejected", sa.Integer(), nullable=False, server_default="0"))
    # NOT VALID: guards new writes without failing on legacy rows.
    op.execute("ALTER TABLE funds ADD CONSTRAINT ck_funds_holdings_status CHECK "
               "(holdings_status IN ('not_checked','available','unavailable','not_applicable','error','partial')) NOT VALID")


def downgrade():
    op.execute("ALTER TABLE funds DROP CONSTRAINT ck_funds_holdings_status")
    op.drop_column("etl_runs", "records_rejected")
