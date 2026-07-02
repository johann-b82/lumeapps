"""v1.73: FAIR drawing ballooning — fair_projects + fair_balloons

Two tables for the Erstmusterprüfung module. Geometry is stored normalized
(0..1) as NUMERIC(9,6); ``fair_balloons.number`` is server-assigned and kept
contiguous, guarded by a unique ``(project_id, number)`` constraint.

Re-targeted onto the feat/quality-targets head (v1_72) — additive only, creates
two new tables and touches no existing data.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "v1_73_fair"
down_revision = "v1_72_personnel_cost_target"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "fair_projects",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("directus_file_uuid", sa.String(length=64), nullable=False),
        sa.Column("file_kind", sa.String(length=8), nullable=False),
        sa.Column("mime_type", sa.String(length=127), nullable=True),
        sa.Column(
            "page_count", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "file_kind IN ('pdf','image')", name="ck_fair_projects_file_kind"
        ),
    )

    op.create_table(
        "fair_balloons",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("fair_projects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column(
            "page_no", sa.Integer(), nullable=False, server_default=sa.text("1")
        ),
        sa.Column("region_x", sa.Numeric(9, 6), nullable=False),
        sa.Column("region_y", sa.Numeric(9, 6), nullable=False),
        sa.Column("region_w", sa.Numeric(9, 6), nullable=False),
        sa.Column("region_h", sa.Numeric(9, 6), nullable=False),
        sa.Column("tail_x", sa.Numeric(9, 6), nullable=False),
        sa.Column("tail_y", sa.Numeric(9, 6), nullable=False),
        sa.Column(
            "value_text", sa.Text(), nullable=False, server_default=""
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "project_id", "number", name="uq_fair_balloons_project_number"
        ),
    )
    op.create_index(
        "ix_fair_balloons_project", "fair_balloons", ["project_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_fair_balloons_project", table_name="fair_balloons")
    op.drop_table("fair_balloons")
    op.drop_table("fair_projects")
