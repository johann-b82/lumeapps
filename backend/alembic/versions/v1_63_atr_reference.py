"""v1.63: atr_part + atr_template (ATR reference foundation, Phase A)

Revision ID: v1_63_atr_reference
Revises: v1_62_tippspiel
Create Date: 2026-06-25
"""
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "v1_63_atr_reference"
down_revision = "v1_62_tippspiel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "atr_part",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("part_number", sa.String(length=60), nullable=False),
        sa.Column("part_number_norm", sa.String(length=40), nullable=False),
        sa.Column("supplier_article_code", sa.String(length=40), nullable=True),
        sa.Column("part_name", sa.String(length=200), nullable=True),
        sa.Column("drawing_number_issue", sa.String(length=60), nullable=True),
        sa.Column("default_weight_kg", sa.Numeric(8, 3), nullable=True),
        sa.Column("qty", sa.Integer, nullable=False, server_default="1"),
        sa.Column("category", sa.String(length=40), nullable=True),
        sa.Column("po_pos", sa.String(length=20), nullable=True),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index(
        "ix_atr_part_norm", "atr_part", ["part_number_norm"], unique=True
    )

    op.create_table(
        "atr_template",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("customer", sa.String(length=200), nullable=True),
        sa.Column("ac_programme", sa.String(length=100), nullable=True),
        sa.Column("work_package", sa.Text, nullable=True),
        sa.Column("purchaser_spec", sa.String(length=200), nullable=True),
        sa.Column("atp", sa.String(length=200), nullable=True),
        sa.Column("supplier_spec", sa.String(length=200), nullable=True),
        sa.Column("reference_no", sa.String(length=200), nullable=True),
        sa.Column("supplier", sa.String(length=200), nullable=True),
        sa.Column("customer_spec", sa.String(length=100), nullable=True),
        sa.Column("nscm_code", sa.String(length=40), nullable=True),
        sa.Column("ata_chapter", sa.String(length=20), nullable=True),
        sa.Column("weighing_equipment", sa.String(length=100), nullable=True),
        sa.Column("qa_signer_default", sa.String(length=100), nullable=True),
        sa.Column("structure_filename", sa.String(length=255), nullable=True),
        sa.Column("structure_xlsx", postgresql.BYTEA, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_atr_template_singleton"),
    )
    # Seed the singleton row (all-null defaults).
    op.execute(
        sa.text(
            "INSERT INTO atr_template (id, updated_at) VALUES (1, :ts)"
        ).bindparams(ts=datetime.now(timezone.utc))
    )


def downgrade() -> None:
    op.drop_table("atr_template")
    op.drop_index("ix_atr_part_norm", table_name="atr_part")
    op.drop_table("atr_part")
