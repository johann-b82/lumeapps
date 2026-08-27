"""v1.120: Zeugnis — Bewertungs-Vorlagen (Profile).

``zeugnis_vorlage`` speichert benannte Bewertungs-Profile: je Vorlage die Noten
je Dimension als JSONB ({dimension: note}). Damit lässt sich ein Notenprofil
(z. B. „sehr gut") mit einem Klick auf neue Zeugnisse anwenden.

Revision ID: v1_120_zeugnis_vorlage
Revises: v1_119_newsletter_eintrag_bild
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "v1_120_zeugnis_vorlage"
down_revision = "v1_119_newsletter_eintrag_bild"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "zeugnis_vorlage",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("noten", JSONB(), nullable=False),
        sa.Column("aktualisiert_am", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("name", name="uq_zeugnis_vorlage_name"),
    )


def downgrade() -> None:
    op.drop_table("zeugnis_vorlage")
