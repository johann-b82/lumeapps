"""v1.64: atr_delivery + atr_delivery_item (ATR Phase B)

Revision ID: v1_64_atr_delivery
Revises: v1_63_atr_reference
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "v1_64_atr_delivery"
down_revision = "v1_63_atr_reference"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "atr_delivery",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_filename", sa.String(255), nullable=False),
        sa.Column("lieferschein_nr", sa.String(40), nullable=True),
        sa.Column("datum", sa.Date, nullable=True),
        sa.Column("ba_auftrag", sa.String(40), nullable=True),
        sa.Column("po_number", sa.String(60), nullable=True),
        sa.Column("ac_programme", sa.String(40), nullable=True),
        sa.Column("compartment", sa.String(8), nullable=True),
        sa.Column("msn", sa.String(20), nullable=True),
        sa.Column("bed_config", sa.String(8), nullable=True),
        sa.Column("set_title", sa.String(100), nullable=True),
        sa.Column("atr_number", sa.String(80), nullable=True),
        sa.Column("container_number", sa.String(40), nullable=True),
        sa.Column("weighing_date", sa.Date, nullable=True),
        sa.Column("testing_date", sa.Date, nullable=True),
        sa.Column("qa_signer", sa.String(100), nullable=True),
        sa.Column("max_guaranteed_weight_kg", sa.Numeric(8, 3), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("atr_xlsx", postgresql.BYTEA, nullable=True),
        sa.Column("atr_pdf", postgresql.BYTEA, nullable=True),
        sa.Column("label_docx", postgresql.BYTEA, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "atr_delivery_item",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("delivery_id", sa.Integer,
                  sa.ForeignKey("atr_delivery.id", ondelete="CASCADE"), nullable=False),
        sa.Column("pos", sa.Integer, nullable=True),
        sa.Column("supplier_article_code", sa.String(40), nullable=True),
        sa.Column("part_number", sa.String(60), nullable=True),
        sa.Column("part_number_norm", sa.String(40), nullable=True),
        sa.Column("matched_part_id", sa.Integer,
                  sa.ForeignKey("atr_part.id", ondelete="SET NULL"), nullable=True),
        sa.Column("part_name", sa.String(200), nullable=True),
        sa.Column("drawing_number_issue", sa.String(60), nullable=True),
        sa.Column("category", sa.String(40), nullable=True),
        sa.Column("qty", sa.Integer, nullable=False, server_default="1"),
        sa.Column("weight_kg", sa.Numeric(8, 3), nullable=True),
        sa.Column("po_pos", sa.String(20), nullable=True),
        sa.Column("match_status", sa.String(12), nullable=False, server_default="unmatched"),
        sa.Column("row_order", sa.Integer, nullable=False),
    )
    op.create_index("ix_atr_delivery_item_delivery", "atr_delivery_item", ["delivery_id"])


def downgrade() -> None:
    op.drop_index("ix_atr_delivery_item_delivery", table_name="atr_delivery_item")
    op.drop_table("atr_delivery_item")
    op.drop_table("atr_delivery")
