"""v1.70: Inspection targets on app_settings

Two integer targets for the Qualitätsprüfung view — expected inspections
per day and inspector (Produkte/Tag/Mitarbeiter):
    * target_inspection_large  — default seed 150
    * target_inspection_small  — default seed 400

Same pattern as the audit-findings level thresholds in v1.66.
"""
from alembic import op
import sqlalchemy as sa


revision = "v1_78_inspection_targets"
down_revision = "v1_77_produktion_verzug_target"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("target_inspection_large", sa.Integer(), nullable=True),
    )
    op.add_column(
        "app_settings",
        sa.Column("target_inspection_small", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "target_inspection_small")
    op.drop_column("app_settings", "target_inspection_large")
