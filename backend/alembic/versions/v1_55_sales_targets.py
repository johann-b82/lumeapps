"""v1.55: app_settings sales target columns

Adds 4 nullable target columns to ``app_settings`` so the new Sales
Settings page can drive the dashed reference lines on the
Vertriebsaktivität card (Erstkontakte, Interessenten, Besuche,
Angebote €) without hardcoded constants in the frontend.

NULL means "no target set" — the chart falls back to a baked-in default
when the value is null, mirroring the existing HR target_* pattern.
"""
from alembic import op
import sqlalchemy as sa


revision = "v1_55_sales_targets"
down_revision = "v1_54_auftraege"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("target_sales_erstkontakte", sa.Numeric(8, 2), nullable=True),
    )
    op.add_column(
        "app_settings",
        sa.Column("target_sales_interessenten", sa.Numeric(8, 2), nullable=True),
    )
    op.add_column(
        "app_settings",
        sa.Column("target_sales_besuche", sa.Numeric(8, 2), nullable=True),
    )
    op.add_column(
        "app_settings",
        sa.Column("target_sales_angebote_eur", sa.Numeric(15, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "target_sales_angebote_eur")
    op.drop_column("app_settings", "target_sales_besuche")
    op.drop_column("app_settings", "target_sales_interessenten")
    op.drop_column("app_settings", "target_sales_erstkontakte")
