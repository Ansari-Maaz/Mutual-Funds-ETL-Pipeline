"""Initial normalized schema."""
from alembic import op
import sqlalchemy as sa

revision="0001_initial"; down_revision=None; branch_labels=None; depends_on=None

def upgrade():
    op.create_table("sources",sa.Column("source_id",sa.String(100),primary_key=True),sa.Column("country_code",sa.String(2),nullable=False),sa.Column("organization",sa.String(200),nullable=False),sa.Column("source_name",sa.String(200),nullable=False),sa.Column("endpoint_url",sa.Text()),sa.Column("verification_status",sa.String(40),nullable=False,server_default="Undiscovered"),sa.Column("integration_status",sa.String(20),nullable=False,server_default="Not Started"),sa.Column("license_status",sa.String(30),nullable=False,server_default="Unknown"))
    op.create_index("ix_sources_country_code","sources",["country_code"])
    op.create_table("funds",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("source_id",sa.String(100),sa.ForeignKey("sources.source_id"),nullable=False),sa.Column("source_fund_id",sa.String(200),nullable=False),sa.Column("name",sa.String(500),nullable=False),sa.Column("domicile_country",sa.String(2)),sa.Column("currency",sa.String(3)),sa.Column("isin",sa.String(12)),sa.Column("retrieved_at",sa.DateTime(timezone=True),server_default=sa.func.now()),sa.UniqueConstraint("source_id","source_fund_id",name="uq_fund_source_native"))
    for col in ("source_id","domicile_country","isin"): op.create_index(f"ix_funds_{col}","funds",[col])
    op.create_table("nav_observations",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("fund_id",sa.Integer(),sa.ForeignKey("funds.id",ondelete="CASCADE"),nullable=False),sa.Column("valuation_date",sa.Date(),nullable=False),sa.Column("nav",sa.Numeric(24,10),nullable=False),sa.Column("currency",sa.String(3),nullable=False),sa.Column("retrieved_at",sa.DateTime(timezone=True),server_default=sa.func.now()),sa.UniqueConstraint("fund_id","valuation_date","currency",name="uq_nav_fund_date_currency"))
    op.create_index("ix_nav_observations_fund_id","nav_observations",["fund_id"]); op.create_index("ix_nav_observations_valuation_date","nav_observations",["valuation_date"])
    op.create_table("etl_runs",sa.Column("id",sa.Integer(),primary_key=True),sa.Column("started_at",sa.DateTime(timezone=True),server_default=sa.func.now()),sa.Column("finished_at",sa.DateTime(timezone=True)),sa.Column("status",sa.String(20),nullable=False,server_default="In Progress"),sa.Column("source_id",sa.String(100),sa.ForeignKey("sources.source_id")),sa.Column("records_extracted",sa.Integer(),nullable=False,server_default="0"),sa.Column("records_loaded",sa.Integer(),nullable=False,server_default="0"),sa.Column("error",sa.Text()))

def downgrade():
    op.drop_table("etl_runs"); op.drop_index("ix_nav_observations_valuation_date",table_name="nav_observations"); op.drop_index("ix_nav_observations_fund_id",table_name="nav_observations"); op.drop_table("nav_observations")
    for col in ("isin","domicile_country","source_id"): op.drop_index(f"ix_funds_{col}",table_name="funds")
    op.drop_table("funds"); op.drop_index("ix_sources_country_code",table_name="sources"); op.drop_table("sources")
