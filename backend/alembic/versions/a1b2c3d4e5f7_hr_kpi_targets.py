"""Add HR KPI target value columns to app_settings

Revision ID: a1b2c3d4e5f7
Revises: f1a2b3c4d5e6
Create Date: 2026-04-12
"""
import sqlalchemy as sa
from alembic import op

revision = "a1b2c3d4e5f7"
down_revision = "f1a2b3c4d5e6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_settings", sa.Column("target_overtime_ratio", sa.Numeric(8, 4), nullable=True))
    op.add_column("app_settings", sa.Column("target_sick_leave_ratio", sa.Numeric(8, 4), nullable=True))
    op.add_column("app_settings", sa.Column("target_fluctuation", sa.Numeric(8, 4), nullable=True))
    op.add_column("app_settings", sa.Column("target_revenue_per_employee", sa.Numeric(15, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("app_settings", "target_revenue_per_employee")
    op.drop_column("app_settings", "target_fluctuation")
    op.drop_column("app_settings", "target_sick_leave_ratio")
    op.drop_column("app_settings", "target_overtime_ratio")
