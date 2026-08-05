"""v1.103: Bereich-Spalte für den Einarbeitungskatalog.

``einarbeitung_katalog.bereich`` (Freitext, nullable) — erscheint im
Einarbeitungsplan-PDF als „Abteilung". Leer → Fallback auf die Abteilung aus der
Pflicht-Matrix (bisheriges Verhalten).

Revision ID: v1_103_einarbeitung_bereich
Revises: v1_102_personio_writeback
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_103_einarbeitung_bereich"
down_revision = "v1_102_personio_writeback"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "einarbeitung_katalog", sa.Column("bereich", sa.Text(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("einarbeitung_katalog", "bereich")
