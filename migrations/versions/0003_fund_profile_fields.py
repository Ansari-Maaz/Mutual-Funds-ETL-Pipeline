"""Add source-backed fund profile fields."""
from alembic import op
import sqlalchemy as sa

revision = "0003_fund_profile_fields"
down_revision = "0002_api_operations"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("funds", sa.Column("legal_name", sa.String(500)))
    op.add_column("funds", sa.Column("provider", sa.String(300)))
    op.add_column("funds", sa.Column("category", sa.String(200)))
    op.add_column("funds", sa.Column("fund_type", sa.String(100)))
    op.add_column("funds", sa.Column("inception_date", sa.Date()))
    op.add_column("funds", sa.Column("status", sa.String(30)))
    op.add_column("funds", sa.Column("official_url", sa.Text()))
    op.create_index("ix_funds_provider", "funds", ["provider"])
    op.create_index("ix_funds_category", "funds", ["category"])
    op.create_index("ix_funds_status", "funds", ["status"])


def downgrade():
    op.drop_index("ix_funds_status", table_name="funds")
    op.drop_index("ix_funds_category", table_name="funds")
    op.drop_index("ix_funds_provider", table_name="funds")
    for column in ("official_url", "status", "inception_date", "fund_type", "category", "provider", "legal_name"):
        op.drop_column("funds", column)
