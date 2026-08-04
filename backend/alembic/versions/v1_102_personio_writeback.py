"""v1.102: Personio-Rückschreiben (inert) — Schalter + Dokumentenkategorie.

Zwei Konfigurationsspalten auf ``app_settings``:
* ``personio_writeback_enabled`` — Master-Schalter (Default FALSE, also inert).
* ``personio_writeback_kategorie_id`` — Personio-Dokumentenkategorie, in die
  Schulungs-/Kompetenznachweise ins Mitarbeiterprofil hochgeladen werden.

Der eigentliche Push bleibt No-Op, bis der Schalter an ist UND die Personio-App
Schreib-Scopes (Dokumente) besitzt.

Revision ID: v1_102_personio_writeback
Revises: v1_101_teilnahme_extern
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_102_personio_writeback"
down_revision = "v1_101_teilnahme_extern"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column(
            "personio_writeback_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column("personio_writeback_kategorie_id", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "personio_writeback_kategorie_id")
    op.drop_column("app_settings", "personio_writeback_enabled")
