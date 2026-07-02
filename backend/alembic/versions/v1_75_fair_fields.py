"""v1.75: FAIR — add fair_projects.customer, article_number, rotation

Additive, nullable customer/article_number columns + a rotation column (default
0) so a drawing reopens in the last-used orientation. No data change.
"""
from alembic import op
import sqlalchemy as sa


revision = "v1_75_fair_fields"
down_revision = "v1_74_fair_partnumber"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "fair_projects", sa.Column("customer", sa.String(length=255), nullable=True)
    )
    op.add_column(
        "fair_projects",
        sa.Column("article_number", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "fair_projects",
        sa.Column(
            "rotation", sa.Integer(), nullable=False, server_default=sa.text("0")
        ),
    )


def downgrade() -> None:
    op.drop_column("fair_projects", "rotation")
    op.drop_column("fair_projects", "article_number")
    op.drop_column("fair_projects", "customer")
