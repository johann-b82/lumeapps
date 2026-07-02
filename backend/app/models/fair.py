"""FAIR (Erstmusterprüfung / First Article Inspection) ORM models — v1.63.

Two tables backing the drawing-ballooning module:
  - ``fair_projects``: one uploaded drawing (PDF or image), stored in Directus.
  - ``fair_balloons``:  one numbered bubble-arrow per inspected feature.

Coordinates are stored NORMALIZED (0..1) relative to the drawing's natural page
size, plus a ``page_no``, so balloons are resolution- and zoom-independent. The
arrow TIP is the CENTER of ``region`` (derived on the client, never stored);
``tail`` is the bubble end placed by the user's follow-up click. ``number`` is
server-assigned and kept contiguous (renumbered on delete).
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

# Normalized coordinate column: exact to 6 decimals, materialised as a Python
# float (asdecimal=False) so Pydantic serialises plain JSON numbers.
_Coord = Numeric(9, 6, asdecimal=False)


class FairProject(Base):
    """One uploaded drawing plus its balloons."""

    __tablename__ = "fair_projects"
    __table_args__ = (
        CheckConstraint(
            "file_kind IN ('pdf','image')", name="ck_fair_projects_file_kind"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    part_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    customer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    article_number: Mapped[str | None] = mapped_column(String(64), nullable=True)
    directus_file_uuid: Mapped[str] = mapped_column(String(64), nullable=False)
    file_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(127), nullable=True)
    page_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    rotation: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    balloons: Mapped[list["FairBalloon"]] = relationship(
        "FairBalloon",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="FairBalloon.number",
    )


class FairBalloon(Base):
    """One numbered bubble-arrow: region (tip = its centre) + tail + read value."""

    __tablename__ = "fair_balloons"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "number", name="uq_fair_balloons_project_number"
        ),
        Index("ix_fair_balloons_project", "project_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("fair_projects.id", ondelete="CASCADE"),
        nullable=False,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    page_no: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    region_x: Mapped[float] = mapped_column(_Coord, nullable=False)
    region_y: Mapped[float] = mapped_column(_Coord, nullable=False)
    region_w: Mapped[float] = mapped_column(_Coord, nullable=False)
    region_h: Mapped[float] = mapped_column(_Coord, nullable=False)
    tail_x: Mapped[float] = mapped_column(_Coord, nullable=False)
    tail_y: Mapped[float] = mapped_column(_Coord, nullable=False)
    value_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped["FairProject"] = relationship(
        "FairProject", back_populates="balloons"
    )
