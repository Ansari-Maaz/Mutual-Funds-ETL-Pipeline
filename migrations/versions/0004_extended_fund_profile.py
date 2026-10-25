"""Add identifiers and source-published fund profile fields."""
from alembic import op
import sqlalchemy as sa

revision = "0004_extended_fund_profile"
down_revision = "0003_fund_profile_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("funds", sa.Column("ticker", sa.String(30)))
    op.add_column("funds", sa.Column("manager", sa.String(300)))
    op.add_column("funds", sa.Column("administrator", sa.String(300)))
    op.add_column("funds", sa.Column("net_assets", sa.Numeric(28, 10)))
    op.add_column("funds", sa.Column("net_assets_date", sa.Date()))
    op.add_column("funds", sa.Column("target_audience", sa.String(200)))
    op.create_index("ix_funds_ticker", "funds", ["ticker"])


def downgrade():
    op.drop_index("ix_funds_ticker", table_name="funds")
    for column in ("target_audience", "net_assets_date", "net_assets", "administrator", "manager", "ticker"):
        op.drop_column("funds", column)
