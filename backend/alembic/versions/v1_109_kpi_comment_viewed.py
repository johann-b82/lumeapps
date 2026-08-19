"""v1.109: kpi_comment.viewed_at — gesehen-Status für den Bubble-Zähler.

NULL = die Bubble wurde von einem Admin noch nicht angesehen (zählt im Badge
oben rechts). Wird gesetzt, sobald ein Admin die Bubble anklickt.

Revision ID: v1_109_kpi_comment_viewed
Revises: v1_107_einarbeitung_dokument
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_109_kpi_comment_viewed"
down_revision = "v1_107_einarbeitung_dokument"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "kpi_comment",
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("kpi_comment", "viewed_at")
