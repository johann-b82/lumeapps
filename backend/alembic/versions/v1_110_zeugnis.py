"""v1.110: Arbeitszeugnis — Aussteller, Zeugnis (Snapshot) und Bewertung.

Drei additive Tabellen für die KI-gestützte Arbeitszeugnis-Erstellung. Der
Stammdaten-Snapshot liegt direkt auf ``zeugnis``, die Einzelnoten auf
``zeugnis_bewertung``.

Revision ID: v1_110_zeugnis
Revises: v1_109_kpi_comment_viewed
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "v1_110_zeugnis"
down_revision = "v1_109_kpi_comment_viewed"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "zeugnis_aussteller",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("firma", sa.Text(), nullable=False),
        sa.Column("standort", sa.Text(), nullable=True),
        sa.Column("unterzeichner1_name", sa.Text(), nullable=True),
        sa.Column("unterzeichner1_titel", sa.Text(), nullable=True),
        sa.Column("unterzeichner2_name", sa.Text(), nullable=True),
        sa.Column("unterzeichner2_titel", sa.Text(), nullable=True),
        sa.Column("aktualisiert_am", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "zeugnis",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), nullable=True),
        sa.Column("extern_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("geschlecht", sa.String(length=1), nullable=True),
        sa.Column("geburtsdatum", sa.Date(), nullable=True),
        sa.Column("personalnummer", sa.Text(), nullable=True),
        sa.Column("abteilung", sa.Text(), nullable=True),
        sa.Column("taetigkeit", sa.Text(), nullable=True),
        sa.Column("eintritt", sa.Date(), nullable=True),
        sa.Column("austritt", sa.Date(), nullable=True),
        sa.Column("art", sa.String(length=20), nullable=False, server_default="qualifiziert"),
        sa.Column("anlass", sa.Text(), nullable=True),
        sa.Column("fuehrungskraft", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("ausstellungsdatum", sa.Date(), nullable=True),
        sa.Column("taetigkeit_stichpunkte", sa.Text(), nullable=True),
        sa.Column("besondere_kompetenzen", sa.Text(), nullable=True),
        sa.Column("besondere_erfolge", sa.Text(), nullable=True),
        sa.Column("schlussnote", sa.Numeric(precision=2, scale=1), nullable=True),
        sa.Column("abschnitte_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="entwurf"),
        sa.Column("erstellt_am", sa.DateTime(timezone=True), nullable=False),
        sa.Column("aktualisiert_am", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["employee_id"], ["personio_employees.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["extern_id"], ["onboarding_extern.id"], ondelete="SET NULL"
        ),
    )
    op.create_index("ix_zeugnis_employee", "zeugnis", ["employee_id"])

    op.create_table(
        "zeugnis_bewertung",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("zeugnis_id", sa.Integer(), nullable=False),
        sa.Column("dimension", sa.String(length=30), nullable=False),
        sa.Column("note", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["zeugnis_id"], ["zeugnis.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("zeugnis_id", "dimension", name="uq_zeugnis_bewertung"),
    )


def downgrade() -> None:
    op.drop_table("zeugnis_bewertung")
    op.drop_index("ix_zeugnis_employee", table_name="zeugnis")
    op.drop_table("zeugnis")
    op.drop_table("zeugnis_aussteller")
