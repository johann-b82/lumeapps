"""v1.41: sales_contacts + sales_employee_aliases + Settings.personio_sales_dept

Revision ID: v1_41_sales_contacts
Revises: v1_39_sensor_chart_color
Create Date: 2026-05-01

Sales contact log (Kontakte) ingestion + Personio sales-rep mapping.

The Kontakte file's ``Wer`` column is an uppercase surname token
(KARRER, GUENDEL, ...). ``sales_employee_aliases`` binds a token to a
``personio_employees`` row. Canonical (auto-derived) aliases are
managed by the Personio sync hook; manual aliases survive sync ticks.

``Settings.personio_sales_dept`` mirrors ``personio_production_dept``
and gates which Personio employees count as sales reps.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "v1_41_sales_contacts"
down_revision = "v1_39_sensor_chart_color"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sales_contacts",
        sa.Column("id", sa.BigInteger, primary_key=True, autoincrement=True),
        sa.Column("contact_date", sa.Date, nullable=False),
        sa.Column("employee_token", sa.String(length=128), nullable=False),
        sa.Column("contact_type", sa.String(length=32), nullable=True),
        sa.Column("customer_group", sa.String(length=32), nullable=True),
        sa.Column("status", sa.SmallInteger, nullable=False),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("external_id", sa.String(length=64), nullable=True),
        sa.Column("raw", postgresql.JSONB, nullable=True),
        sa.Column(
            "imported_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.CheckConstraint("status IN (0, 1)", name="sales_contacts_status_check"),
    )
    op.create_index("ix_sales_contacts_date", "sales_contacts", ["contact_date"])
    op.create_index("ix_sales_contacts_token", "sales_contacts", ["employee_token"])

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

    op.add_column(
        "app_settings",
        sa.Column("personio_sales_dept", postgresql.JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "personio_sales_dept")
    op.drop_index(
        "ix_sales_employee_aliases_employee", table_name="sales_employee_aliases"
    )
    op.drop_table("sales_employee_aliases")
    op.drop_index("ix_sales_contacts_token", table_name="sales_contacts")
    op.drop_index("ix_sales_contacts_date", table_name="sales_contacts")
    op.drop_table("sales_contacts")
