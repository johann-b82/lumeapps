"""v1.66: Quality KPI target columns on app_settings

Stores the four configurable targets the Quality dashboard renders as
ReferenceLines on its charts:
    * target_complaint_rate_customer  — fraction, e.g. 0.02 = 2 %
    * target_complaint_rate_internal  — fraction, e.g. 0.04 = 4 %
    * target_audit_findings_level1    — absolute count per bucket
    * target_audit_findings_level2    — absolute count per bucket

All nullable — NULL hides the target line (same pattern as the HR targets).
"""
from alembic import op
import sqlalchemy as sa


revision = "v1_66_quality_targets"
down_revision = "v1_65_atr_fileserver"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("target_complaint_rate_customer", sa.Numeric(8, 4), nullable=True),
    )
    op.add_column(
        "app_settings",
        sa.Column("target_complaint_rate_internal", sa.Numeric(8, 4), nullable=True),
    )
    op.add_column(
        "app_settings",
        sa.Column("target_audit_findings_level1", sa.Integer(), nullable=True),
    )
    op.add_column(
        "app_settings",
        sa.Column("target_audit_findings_level2", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "target_audit_findings_level2")
    op.drop_column("app_settings", "target_audit_findings_level1")
    op.drop_column("app_settings", "target_complaint_rate_internal")
    op.drop_column("app_settings", "target_complaint_rate_customer")
