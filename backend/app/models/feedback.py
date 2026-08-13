"""Seiten-Feedback ORM model — v1.105.

One table ``page_feedback`` backing the global feedback widget. Every
authenticated user can create a row (from any intranet page); reading,
resolving and deleting are admin-only. The screenshot lives inline as
``bytea`` (same pattern as ``app_settings.logo_data``) — no external file
store, keeping the feature self-contained.
"""
import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Index, String, Text
from sqlalchemy.dialects.postgresql import BYTEA, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class PageFeedback(Base):
    """One feedback/problem report submitted from an intranet page."""

    __tablename__ = "page_feedback"
    __table_args__ = (
        CheckConstraint(
            "status IN ('new','resolved')", name="ck_page_feedback_status"
        ),
        Index("ix_page_feedback_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Directus user id from the JWT (trusted). Nullable defensively.
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    # Client-supplied display hint — the real email is not carried in the JWT.
    reporter_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    page_url: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    screenshot_data: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    screenshot_mime: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    viewport: Mapped[str | None] = mapped_column(String(32), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="new"
    )
