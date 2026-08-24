"""v1.114: Newsletter — Block-Reihenfolge (Rubriken + KPI) je Ausgabe.

``newsletter.block_reihenfolge`` hält die per Drag&Drop gesetzte Reihenfolge der
Blöcke (Rubrik-Schlüssel + "kpi"). NULL = Standardreihenfolge.

Revision ID: v1_114_newsletter_order
Revises: v1_113_newsletter_kpi
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "v1_114_newsletter_order"
down_revision = "v1_113_newsletter_kpi"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "newsletter",
        sa.Column("block_reihenfolge", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("newsletter", "block_reihenfolge")
