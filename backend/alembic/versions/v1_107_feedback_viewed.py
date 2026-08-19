"""v1.107 (Live-Linie): page_feedback.viewed_at — gesehen-Status für den Zähler.

Neue Spalte ``viewed_at`` (nullable). NULL = noch nicht angesehen; der
Feedback-Zähler oben rechts zählt die ungesehenen Meldungen. Wird gesetzt,
sobald ein Admin ein Feedback ansieht.

Revision ID: v1_107_feedback_viewed
Revises: v1_106_stock_article_prices
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_107_feedback_viewed"
down_revision = "v1_106_stock_article_prices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "page_feedback",
        sa.Column("viewed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("page_feedback", "viewed_at")
