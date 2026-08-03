"""v1.101: Schulungsteilnahme für externe (Nicht-Personio-)Mitarbeiter.

``schulung_teilnahme.extern_id`` verweist optional auf ``onboarding_extern`` —
so lassen sich Schulungen auch manuell gepflegten Personen zuweisen und als
durchgeführt eintragen. Personio-Zeilen behalten ``employee_id``/Personalnummer.

Revision ID: v1_101_teilnahme_extern
Revises: v1_100_schulung_unterlagen
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_101_teilnahme_extern"
down_revision = "v1_100_schulung_unterlagen"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "schulung_teilnahme", sa.Column("extern_id", sa.Integer(), nullable=True)
    )
    op.create_foreign_key(
        "fk_schulung_teilnahme_extern",
        "schulung_teilnahme",
        "onboarding_extern",
        ["extern_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_schulung_teilnahme_extern", "schulung_teilnahme", ["extern_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_schulung_teilnahme_extern", table_name="schulung_teilnahme")
    op.drop_constraint(
        "fk_schulung_teilnahme_extern", "schulung_teilnahme", type_="foreignkey"
    )
    op.drop_column("schulung_teilnahme", "extern_id")
