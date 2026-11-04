"""Store OHLC values and their interpretation on NAV observations."""
from alembic import op
import sqlalchemy as sa

revision = "0010_nav_ohlc"
down_revision = "0009_nav_source_provenance"
branch_labels = None
depends_on = None


def upgrade():
    for column in ("open", "high", "low", "close"):
        op.add_column("nav_observations", sa.Column(column, sa.Numeric(24, 10), nullable=True))
    op.add_column("nav_observations", sa.Column("ohlc_basis", sa.String(40), nullable=True))


def downgrade():
    op.drop_column("nav_observations", "ohlc_basis")
    for column in ("close", "low", "high", "open"):
        op.drop_column("nav_observations", column)
