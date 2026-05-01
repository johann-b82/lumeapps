"""v1.42: drop sales_employee_aliases + app_settings.personio_sales_dept

Revision ID: v1_42_drop_sales_aliases
Revises: v1_41_sales_contacts
Create Date: 2026-05-01

User feedback after v1.41 shipped: the Personio-driven sales-rep
mapping was overkill. Sales reps are now identified directly by the
``Wer`` token from the Kontakte file — no Personio binding, no alias
table, no sync hook. v1.41's ``sales_employee_aliases`` and
``app_settings.personio_sales_dept`` are dropped.

The ``sales_contacts`` table itself stays — it's still the source of
truth for the four KPI charts. Only the rep-attribution layer is
removed.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "v1_42_drop_sales_aliases"
down_revision = "v1_41_sales_contacts"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index(
        "ix_sales_employee_aliases_employee", table_name="sales_employee_aliases"
    )
    op.drop_table("sales_employee_aliases")
    op.drop_column("app_settings", "personio_sales_dept")


def downgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("personio_sales_dept", postgresql.JSONB, nullable=True),
    )
    op.create_table(
        "sales_employee_aliases",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column(
            "personio_employee_id",
            sa.Integer,
            sa.ForeignKey("personio_employees.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "employee_token", sa.String(length=128), nullable=False, unique=True
        ),
        sa.Column(
            "is_canonical", sa.Boolean, nullable=False, server_default=sa.false()
        ),
    )
    op.create_index(
        "ix_sales_employee_aliases_employee",
        "sales_employee_aliases",
        ["personio_employee_id"],
    )
