"""v1.92: Einarbeitungsmatrix — Einarbeitungsinhalte je Abteilung.

Stammdaten für den Einarbeitungsbogen: pro Abteilung eine Liste von
Einarbeitungsinhalten mit Ansprechpartner. Der personalisierte Bogen zieht die
Zeilen der Abteilung(en) einer Person und stellt sie in Formblatt-Form dar.

App-gepflegt (kein Excel-Import) — die Tabelle ist die führende Quelle.

Revision ID: v1_92_einarbeitung
Revises: v1_91_onboarding_dokument
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_92_einarbeitung"
down_revision = "v1_91_onboarding_dokument"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "einarbeitung_inhalt",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("abteilung", sa.String(120), nullable=False),
        sa.Column("ansprechpartner", sa.Text(), nullable=True),
        sa.Column("inhalt", sa.Text(), nullable=False),
        sa.Column("reihenfolge", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "erstellt_am",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_einarbeitung_inhalt_abteilung", "einarbeitung_inhalt", ["abteilung"]
    )


def downgrade() -> None:
    op.drop_index("ix_einarbeitung_inhalt_abteilung", table_name="einarbeitung_inhalt")
    op.drop_table("einarbeitung_inhalt")
