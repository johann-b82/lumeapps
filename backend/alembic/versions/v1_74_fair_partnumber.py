"""v1.74: FAIR — add fair_projects.part_number

Additive, nullable column for the drawing's part number (P/N). No data change.
"""
from alembic import op
import sqlalchemy as sa


revision = "v1_74_fair_partnumber"
down_revision = "v1_73_fair"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fair_projects",
        sa.Column("part_number", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("fair_projects", "part_number")
