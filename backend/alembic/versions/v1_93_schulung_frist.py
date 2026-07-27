"""v1.93: Frist je Schulung (Tage nach Eintritt/Zuweisung).

``frist_tage`` sagt, innerhalb wie vieler Tage nach Eintritt bzw. Zuweisung eine
Schulung absolviert sein muss. Getrennt vom Wiederholungs-Turnus
(``turnus``/``turnus_monate``). Speist später die Reminder-/Überfällig-Logik.

Revision ID: v1_93_schulung_frist
Revises: v1_92_einarbeitung
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_93_schulung_frist"
down_revision = "v1_92_einarbeitung"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "schulung_katalog",
        sa.Column("frist_tage", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("schulung_katalog", "frist_tage")
