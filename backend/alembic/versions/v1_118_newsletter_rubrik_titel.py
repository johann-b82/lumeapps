"""v1.118: Newsletter — überschreibbare Abschnitts-Titel je Ausgabe.

``newsletter.rubrik_titel`` (JSONB) hält pro Block-Schlüssel (Rubrik oder "kpi")
einen frei gewählten Anzeigetitel. Fehlt ein Eintrag, gilt der i18n-Standardname.

Revision ID: v1_118_newsletter_rubrik_titel
Revises: v1_117_newsletter_cover
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "v1_118_newsletter_rubrik_titel"
down_revision = "v1_117_newsletter_cover"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("newsletter", sa.Column("rubrik_titel", JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column("newsletter", "rubrik_titel")
