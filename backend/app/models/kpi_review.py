"""KPI-Bewertung & Maßnahmen ORM models — v1.107.

Two tables backing the KPI review / continuous-improvement loop:
  - ``kpi_comment``:  a free-text evaluation anchored to a KPI (``kpi_key``),
                      optionally rated red/yellow/green.
  - ``kpi_measure``:  an action derived from the review to improve the value —
                      assigned to a Personio person, planned (due date), and
                      tracked through a status lifecycle.

Reads are viewer-visible (the dashboards are); all writes are admin-gated.
``kpi_key`` is a stable identifier from ``app.services.kpi_registry``.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class KpiComment(Base):
    """One evaluation/comment on a KPI."""

    __tablename__ = "kpi_comment"
    __table_args__ = (
        CheckConstraint(
            "rating IS NULL OR rating IN ('red','yellow','green')",
            name="ck_kpi_comment_rating",
        ),
        Index("ix_kpi_comment_kpi_key", "kpi_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    kpi_key: Mapped[str] = mapped_column(String(64), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional Ampel rating of the KPI at comment time.
    rating: Mapped[str | None] = mapped_column(String(8), nullable=True)
    # Directus user id from the JWT (trusted) + client-supplied display hint.
    author_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    author_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class KpiMeasure(Base):
    """One improvement measure derived from a KPI review."""

    __tablename__ = "kpi_measure"
    __table_args__ = (
        CheckConstraint(
            "status IN ('open','in_progress','done','dropped')",
            name="ck_kpi_measure_status",
        ),
        CheckConstraint(
            "priority IN ('low','medium','high')", name="ck_kpi_measure_priority"
        ),
        Index("ix_kpi_measure_kpi_key", "kpi_key"),
        Index("ix_kpi_measure_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    kpi_key: Mapped[str] = mapped_column(String(64), nullable=False)
    # Optional link to the comment that motivated the measure.
    comment_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("kpi_comment.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    # Assignee resolved from Personio (id + display name snapshot).
    assignee_personio_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    assignee_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[str] = mapped_column(
        String(8), nullable=False, server_default="medium"
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="open"
    )
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    done_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
