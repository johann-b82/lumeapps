"""v1.119: Newsletter — mehrere Bilder je Eintrag (Puzzle-Raster).

Ein Eintrag kann mehrere Bilder haben, die als Raster-Puzzle angeordnet werden.
``newsletter_eintrag_bild`` speichert je Bild die Bytes + MIME, die Reihenfolge
und die Zellen-Spanne (spalten × zeilen) im 4-Spalten-Raster.

Revision ID: v1_119_newsletter_eintrag_bild
Revises: v1_118_newsletter_rubrik_titel
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_119_newsletter_eintrag_bild"
down_revision = "v1_118_newsletter_rubrik_titel"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "newsletter_eintrag_bild",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "eintrag_id",
            sa.Integer(),
            sa.ForeignKey("newsletter_eintrag.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("bild_data", sa.LargeBinary(), nullable=False),
        sa.Column("bild_mime", sa.String(length=64), nullable=True),
        sa.Column("reihenfolge", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("spalten", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("zeilen", sa.Integer(), nullable=False, server_default="1"),
    )
    op.create_index(
        "ix_newsletter_eintrag_bild_eintrag_id", "newsletter_eintrag_bild", ["eintrag_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_newsletter_eintrag_bild_eintrag_id", table_name="newsletter_eintrag_bild")
    op.drop_table("newsletter_eintrag_bild")
