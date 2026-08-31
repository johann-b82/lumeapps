"""v1.123: Zeugnis — editierbare Textbausteine je (Dimension, Note).

``zeugnis_baustein`` hält je Bewertungsdimension und Note (1–4) den fertigen
Fließtext. Der Baukasten liest daraus (Fallback = Code-Defaults ``_BAUSTEINE``),
und die Admin-Verwaltung „Textbausteine" macht sie editierbar. Die Migration
legt die Tabelle an und seedet sie mit den bisherigen Code-Defaults.

Revision ID: v1_123_zeugnis_baustein
Revises: v1_122_schulung_nachweise
"""
from __future__ import annotations

from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "v1_123_zeugnis_baustein"
down_revision = "v1_122_schulung_nachweise"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "zeugnis_baustein",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("dimension", sa.String(length=30), nullable=False),
        sa.Column("note", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("aktualisiert_am", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("dimension", "note", name="uq_zeugnis_baustein"),
    )

    # Seed aus den Code-Defaults (bleiben als Fallback erhalten).
    from app.services.zeugnis_baukasten import _BAUSTEINE

    jetzt = datetime.now(timezone.utc)
    tabelle = sa.table(
        "zeugnis_baustein",
        sa.column("dimension", sa.String),
        sa.column("note", sa.Integer),
        sa.column("text", sa.Text),
        sa.column("aktualisiert_am", sa.DateTime(timezone=True)),
    )
    zeilen = [
        {"dimension": dim, "note": note, "text": text, "aktualisiert_am": jetzt}
        for dim, noten in _BAUSTEINE.items()
        for note, text in noten.items()
    ]
    if zeilen:
        op.bulk_insert(tabelle, zeilen)


def downgrade() -> None:
    op.drop_table("zeugnis_baustein")
