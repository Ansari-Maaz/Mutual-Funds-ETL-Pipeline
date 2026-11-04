"""Record whether fund currency is source-reported or a domicile default."""
from alembic import op
import sqlalchemy as sa

revision = "0011_currency_basis"
down_revision = "0010_nav_ohlc"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("funds", sa.Column("currency_basis", sa.String(30), nullable=True))
    op.execute("UPDATE funds SET currency_basis='source_reported' WHERE currency IS NOT NULL")
    op.execute("""
        UPDATE funds
        SET currency = CASE domicile_country
                WHEN 'CH' THEN 'CHF'
                WHEN 'CN' THEN 'CNY'
                WHEN 'DK' THEN 'DKK'
                WHEN 'GB' THEN 'GBP'
                WHEN 'SE' THEN 'SEK'
                WHEN 'ZA' THEN 'ZAR'
                WHEN 'DE' THEN 'EUR'
                WHEN 'ES' THEN 'EUR'
                WHEN 'FR' THEN 'EUR'
                WHEN 'IE' THEN 'EUR'
                WHEN 'IT' THEN 'EUR'
                WHEN 'LU' THEN 'EUR'
                WHEN 'NL' THEN 'EUR'
            END,
            currency_basis='domicile_default'
        WHERE currency IS NULL
          AND domicile_country IN ('CH','CN','DK','GB','SE','ZA','DE','ES','FR','IE','IT','LU','NL')
    """)


def downgrade():
    op.execute("UPDATE funds SET currency=NULL WHERE currency_basis='domicile_default'")
    op.drop_column("funds", "currency_basis")
