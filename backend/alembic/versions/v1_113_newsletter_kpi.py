"""v1.113: Newsletter — KPI-Snapshot je Ausgabe.

``newsletter.kpi_snapshot`` hält den eingefrorenen Stand der Belegschafts-KPIs
für den optionalen „ACM KPIs"-Block einer Ausgabe.

Revision ID: v1_113_newsletter_kpi
Revises: v1_112_newsletter
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "v1_113_newsletter_kpi"
down_revision = "v1_112_newsletter"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "newsletter",
        sa.Column("kpi_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("newsletter", "kpi_snapshot")
