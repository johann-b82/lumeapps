"""v1.115: ATR A380 — Seriennummern je Position + Programm-Erkennungsbegründung.

``atr_delivery_item.serial_numbers`` speichert die Seriennummern einer Position
(A380: je Stück eine, kommagetrennt). ``atr_delivery.programme_reason`` hält die
Begründung der automatischen A350/A380-Erkennung (Nachvollziehbarkeit).

Revision ID: v1_115_atr_a380
Revises: v1_114_newsletter_order
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_115_atr_a380"
down_revision = "v1_114_newsletter_order"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("atr_delivery_item", sa.Column("serial_numbers", sa.Text(), nullable=True))
    op.add_column("atr_delivery", sa.Column("programme_reason", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("atr_delivery", "programme_reason")
    op.drop_column("atr_delivery_item", "serial_numbers")
