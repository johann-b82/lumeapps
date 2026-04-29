"""v1.3 Personio KPI configuration columns on AppSettings

Adds 3 new nullable columns for KPI configuration:
  - personio_sick_leave_type_id: maps to the Personio absence type ID for sick leave
  - personio_production_dept: department name filter for production employee KPIs
  - personio_skill_attr_key: custom attribute key for skill development tracking (KPI #4)

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-04-12
"""
import sqlalchemy as sa
from alembic import op

revision = "d4e5f6a7b8c9"
down_revision = "c3d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("personio_sick_leave_type_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "app_settings",
        sa.Column("personio_production_dept", sa.String(255), nullable=True),
    )
    op.add_column(
        "app_settings",
        sa.Column("personio_skill_attr_key", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "personio_skill_attr_key")
    op.drop_column("app_settings", "personio_production_dept")
    op.drop_column("app_settings", "personio_sick_leave_type_id")
