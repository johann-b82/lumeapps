"""v1.44: add sales_records.created_by_user

Revision ID: v1_44_sales_user
Revises: v1_42_drop_sales_aliases
Create Date: 2026-05-02

User feedback: orders/wk/rep KPI was 0,0 because the v1.41/v1.42 Kontakte
bridge (matching `Angebot <order_number>` rows) found no creator for the
existing orders. Switch to the ERP file's own `Benutzer` column.

Existing rows uploaded before v1.44 won't have this field populated; the
KPI returns 0,0 until the Aufträge file is re-uploaded.
"""
from alembic import op
import sqlalchemy as sa


revision = "v1_44_sales_user"
down_revision = "v1_42_drop_sales_aliases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sales_records",
        sa.Column("created_by_user", sa.String(length=100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sales_records", "created_by_user")
