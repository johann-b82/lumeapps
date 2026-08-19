"""v1.107: KPI-Bewertung & Maßnahmen.

Zwei Tabellen für den KVP-Kreislauf auf KPIs:
  - ``kpi_comment``: Bewertung/Kommentar je KPI (``kpi_key``), optional Ampel.
  - ``kpi_measure``: abgeleitete Maßnahme (Verantwortlicher aus Personio,
                     Fälligkeit, Priorität, Status-Lebenszyklus).

Revision ID: v1_107_kpi_review
Revises: v1_107_feedback_viewed
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "v1_107_kpi_review"
# Hinter feedback_viewed verankert (statt direkt hinter v1_106), damit die Live-
# Linie — die bereits auf v1_107_feedback_viewed steht — vorwärts auf den main-
# Head migrieren kann, ohne einen Downgrade zu benötigen. Prod↔main-Versöhnung.
down_revision = "v1_107_feedback_viewed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kpi_comment",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("kpi_key", sa.String(64), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("rating", sa.String(8), nullable=True),
        sa.Column("author_id", UUID(as_uuid=True), nullable=True),
        sa.Column("author_name", sa.String(255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "rating IS NULL OR rating IN ('red','yellow','green')",
            name="ck_kpi_comment_rating",
        ),
    )
    op.create_index("ix_kpi_comment_kpi_key", "kpi_comment", ["kpi_key"])

    op.create_table(
        "kpi_measure",
        sa.Column(
            "id", UUID(as_uuid=True), primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("kpi_key", sa.String(64), nullable=False),
        sa.Column(
            "comment_id", UUID(as_uuid=True),
            sa.ForeignKey("kpi_comment.id", ondelete="SET NULL"), nullable=True,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("assignee_personio_id", sa.String(64), nullable=True),
        sa.Column("assignee_name", sa.String(255), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("priority", sa.String(8), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("created_by_id", UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('open','in_progress','done','dropped')",
            name="ck_kpi_measure_status",
        ),
        sa.CheckConstraint(
            "priority IN ('low','medium','high')", name="ck_kpi_measure_priority"
        ),
    )
    op.create_index("ix_kpi_measure_kpi_key", "kpi_measure", ["kpi_key"])
    op.create_index("ix_kpi_measure_status", "kpi_measure", ["status"])


def downgrade() -> None:
    op.drop_index("ix_kpi_measure_status", table_name="kpi_measure")
    op.drop_index("ix_kpi_measure_kpi_key", table_name="kpi_measure")
    op.drop_table("kpi_measure")
    op.drop_index("ix_kpi_comment_kpi_key", table_name="kpi_comment")
    op.drop_table("kpi_comment")
