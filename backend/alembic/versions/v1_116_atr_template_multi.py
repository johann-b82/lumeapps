"""v1.116: ATR — Struktur-Vorlage pro Programm (Singleton-Constraint entfernen).

A380 braucht eine eigene Struktur-Vorlage (id=2). Der bisherige
``CHECK (id = 1)`` erlaubte nur die A350-Vorlage — entfernt, damit je Programm
eine Vorlage abgelegt werden kann.

Revision ID: v1_116_atr_template_multi
Revises: v1_115_atr_a380
"""
from __future__ import annotations

from alembic import op

revision = "v1_116_atr_template_multi"
down_revision = "v1_115_atr_a380"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_atr_template_singleton", "atr_template", type_="check")


def downgrade() -> None:
    op.create_check_constraint("ck_atr_template_singleton", "atr_template", "id = 1")
