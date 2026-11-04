"""Record source provenance for each NAV observation."""
from alembic import op
import sqlalchemy as sa

revision = "0009_nav_source_provenance"
down_revision = "0008_fund_profile_snapshots"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("nav_observations", sa.Column("source_id", sa.String(100), nullable=True))
    op.create_foreign_key(
        "fk_nav_observations_source_id_sources",
        "nav_observations", "sources", ["source_id"], ["source_id"],
    )
    op.create_index("ix_nav_observations_source_id", "nav_observations", ["source_id"])
    op.add_column("nav_observations", sa.Column("source_url", sa.Text(), nullable=True))


def downgrade():
    op.drop_column("nav_observations", "source_url")
    op.drop_index("ix_nav_observations_source_id", table_name="nav_observations")
    op.drop_constraint("fk_nav_observations_source_id_sources", "nav_observations", type_="foreignkey")
    op.drop_column("nav_observations", "source_id")
