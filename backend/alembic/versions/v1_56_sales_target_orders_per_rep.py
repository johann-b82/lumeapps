"""v1.56: app_settings.target_sales_orders_per_rep_eur

Adds the 5th sales target — the €/week/rep goal for the orders
distribution KPI tile. NULL means "no target set" — the frontend shows
no target subtitle when null.
"""
from alembic import op
import sqlalchemy as sa


revision = "v1_56_sales_target_orep"
down_revision = "v1_55_sales_targets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("target_sales_orders_per_rep_eur", sa.Numeric(15, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "target_sales_orders_per_rep_eur")
