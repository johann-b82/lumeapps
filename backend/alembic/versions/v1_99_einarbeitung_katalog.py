"""v1.99: Einarbeitung als Katalog + Abteilungs-Matrix.

Löst die bisherige Kopplung (einarbeitung_inhalt = abteilung+inhalt+ansprechpartner)
auf: einarbeitung_katalog hält den Inhalt mit Ansprechpartner (abteilungsunabhängig),
einarbeitung_pflicht ordnet Inhalte den Abteilungen zu. Bestand wird übernommen.

Revision ID: v1_99_einarbeitung_katalog
Revises: v1_98_onboarding_extern
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_99_einarbeitung_katalog"
down_revision = "v1_98_onboarding_extern"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "einarbeitung_katalog",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("inhalt", sa.Text(), nullable=False),
        sa.Column("ansprechpartner", sa.Text(), nullable=True),
        sa.Column("reihenfolge", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "erstellt_am",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_table(
        "einarbeitung_pflicht",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("einarbeitung_id", sa.Integer(), nullable=False),
        sa.Column("abteilung", sa.String(length=120), nullable=False),
        sa.ForeignKeyConstraint(
            ["einarbeitung_id"], ["einarbeitung_katalog.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("einarbeitung_id", "abteilung", name="uq_einarbeitung_pflicht"),
    )

    # Bestand übernehmen: je Inhalt (normalisiert) einen Katalogeintrag (erster
    # Ansprechpartner gewinnt), dann die Abteilungs-Zuordnungen.
    op.execute(
        """
        INSERT INTO einarbeitung_katalog (inhalt, ansprechpartner, reihenfolge)
        SELECT DISTINCT ON (lower(trim(inhalt))) inhalt, ansprechpartner, 0
        FROM einarbeitung_inhalt
        ORDER BY lower(trim(inhalt)), id
        """
    )
    op.execute(
        """
        INSERT INTO einarbeitung_pflicht (einarbeitung_id, abteilung)
        SELECT DISTINCT k.id, e.abteilung
        FROM einarbeitung_inhalt e
        JOIN einarbeitung_katalog k
          ON lower(trim(k.inhalt)) = lower(trim(e.inhalt))
        """
    )
    op.drop_table("einarbeitung_inhalt")


def downgrade() -> None:
    op.create_table(
        "einarbeitung_inhalt",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("abteilung", sa.String(length=120), nullable=False),
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
    op.execute(
        """
        INSERT INTO einarbeitung_inhalt (abteilung, ansprechpartner, inhalt, reihenfolge)
        SELECT p.abteilung, k.ansprechpartner, k.inhalt, k.reihenfolge
        FROM einarbeitung_pflicht p
        JOIN einarbeitung_katalog k ON k.id = p.einarbeitung_id
        """
    )
    op.drop_table("einarbeitung_pflicht")
    op.drop_table("einarbeitung_katalog")
