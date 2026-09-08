"""v1.125: Qualitätsprüfung — dritte Soll-Linie „Gesamt".

Fügt ``app_settings.target_inspection_total`` hinzu — der Zielwert für die neue
„Gesamt"-Qualitätsprüfung (Teile pro Person und Tag). NULL = keine Soll-Linie
(gleiche Konvention wie ``target_inspection_large`` / ``_small``).

Revision ID: v1_125_inspection_total_target
Revises: v1_124_zeugnis_aussteller_hr
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_125_inspection_total_target"
down_revision = "v1_124_zeugnis_aussteller_hr"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "app_settings",
        sa.Column("target_inspection_total", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "target_inspection_total")
