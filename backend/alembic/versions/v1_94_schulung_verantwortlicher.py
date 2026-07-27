"""v1.94: Verantwortlicher je Schulung (Trainer/Vorgesetzter).

``verantwortlicher`` hält den Namen der Person, die die Schulung durchführt bzw.
verantwortet — Datenbasis für Phase 2 (aktive Zuweisung / E-Mail) und füllt das
Trainer-Feld im Schulungsnachweis (Fbl. 68) vor. Freitext, damit auch Externe
eintragbar sind; in der Oberfläche aus den Personio-Mitarbeitern wählbar.

Revision ID: v1_94_schulung_verantwortlicher
Revises: v1_93_schulung_frist
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_94_schulung_verantwortlicher"
down_revision = "v1_93_schulung_frist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "schulung_katalog",
        sa.Column("verantwortlicher", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("schulung_katalog", "verantwortlicher")
