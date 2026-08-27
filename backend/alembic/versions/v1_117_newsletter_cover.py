"""v1.117: Newsletter — Titel-/Rückseitenbild je Ausgabe.

Vollflächige Bilder für die erste (Titel) und letzte (Rückseite) Seite, analog
zum physischen Heft. Je Ausgabe ein Bild (bytea) + MIME.

Revision ID: v1_117_newsletter_cover
Revises: v1_116_atr_template_multi
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_117_newsletter_cover"
down_revision = "v1_116_atr_template_multi"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("newsletter", sa.Column("cover_bild", sa.LargeBinary(), nullable=True))
    op.add_column("newsletter", sa.Column("cover_mime", sa.String(length=64), nullable=True))
    op.add_column("newsletter", sa.Column("rueck_bild", sa.LargeBinary(), nullable=True))
    op.add_column("newsletter", sa.Column("rueck_mime", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("newsletter", "rueck_mime")
    op.drop_column("newsletter", "rueck_bild")
    op.drop_column("newsletter", "cover_mime")
    op.drop_column("newsletter", "cover_bild")
