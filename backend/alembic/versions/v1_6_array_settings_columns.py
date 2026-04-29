"""v1.6 Convert 3 Personio config columns to JSONB arrays

Converts scalar columns to JSONB arrays with NULL-safe CASE expressions:
  - personio_sick_leave_type_id: Integer -> JSONB (array of ints)
  - personio_production_dept: String(255) -> JSONB (array of strings)
  - personio_skill_attr_key: String(255) -> JSONB (array of strings)

Existing non-NULL values are wrapped in single-element arrays.
NULL values remain NULL (not [null]) — per D-02.

Revision ID: e5f6a7b8c9d0
Revises: 7022a1dfd988
Create Date: 2026-04-12
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "e5f6a7b8c9d0"
down_revision = "7022a1dfd988"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "app_settings",
        "personio_sick_leave_type_id",
        type_=JSONB(),
        postgresql_using=(
            "CASE WHEN personio_sick_leave_type_id IS NULL THEN NULL "
            "ELSE jsonb_build_array(personio_sick_leave_type_id) END"
        ),
        existing_type=sa.Integer(),
        nullable=True,
    )
    op.alter_column(
        "app_settings",
        "personio_production_dept",
        type_=JSONB(),
        postgresql_using=(
            "CASE WHEN personio_production_dept IS NULL THEN NULL "
            "ELSE jsonb_build_array(personio_production_dept) END"
        ),
        existing_type=sa.String(255),
        nullable=True,
    )
    op.alter_column(
        "app_settings",
        "personio_skill_attr_key",
        type_=JSONB(),
        postgresql_using=(
            "CASE WHEN personio_skill_attr_key IS NULL THEN NULL "
            "ELSE jsonb_build_array(personio_skill_attr_key) END"
        ),
        existing_type=sa.String(255),
        nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "app_settings",
        "personio_sick_leave_type_id",
        type_=sa.Integer(),
        postgresql_using="(personio_sick_leave_type_id->0)::int",
        existing_type=JSONB(),
        nullable=True,
    )
    op.alter_column(
        "app_settings",
        "personio_production_dept",
        type_=sa.String(255),
        postgresql_using="personio_production_dept->>0",
        existing_type=JSONB(),
        nullable=True,
    )
    op.alter_column(
        "app_settings",
        "personio_skill_attr_key",
        type_=sa.String(255),
        postgresql_using="personio_skill_attr_key->>0",
        existing_type=JSONB(),
        nullable=True,
    )
