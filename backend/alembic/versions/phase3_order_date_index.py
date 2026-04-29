"""phase3 order_date index

Revision ID: a1b2c3d4e5f6
Revises: d7547428d885
Create Date: 2026-04-11
"""
from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "d7547428d885"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_sales_records_order_date",
        "sales_records",
        ["order_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_sales_records_order_date", table_name="sales_records")
