"""Maschinen-Wartung (machine maintenance) ORM models — v1.82.

Three tables backing the maintenance module:
  - ``machines``:           one physical machine / asset (master data).
  - ``maintenance_tasks``:  one recurring maintenance task with an interval.
  - ``maintenance_files``:  an uploaded plan (reference) or an archived,
                            signed KW sheet, stored in Directus.

The interval drives how the printable "Wartungsnachweis" sheet groups tasks:
daily tasks land on a day-grid month sheet, everything else on a KW (calendar
week) half-year sheet. ``interval_weeks`` is only meaningful (and required)
when ``interval_type = 'interval_weeks'`` — a custom "every N weeks" cadence.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base


class Machine(Base):
    """One machine / asset plus its maintenance tasks and uploaded files."""

    __tablename__ = "machines"
    __table_args__ = (
        CheckConstraint(
            "status IN ('active','inactive')", name="ck_machines_status"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    inventory_no: Mapped[str | None] = mapped_column(String(64), nullable=True)
    location: Mapped[str | None] = mapped_column(String(255), nullable=True)
    manufacturer: Mapped[str | None] = mapped_column(String(255), nullable=True)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    responsible: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="active"
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False, server_default="")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    tasks: Mapped[list["MaintenanceTask"]] = relationship(
        "MaintenanceTask",
        back_populates="machine",
        cascade="all, delete-orphan",
        order_by="MaintenanceTask.created_at",
    )
    files: Mapped[list["MaintenanceFile"]] = relationship(
        "MaintenanceFile",
        back_populates="machine",
        cascade="all, delete-orphan",
        order_by="MaintenanceFile.uploaded_at.desc()",
    )


class MaintenanceTask(Base):
    """One recurring maintenance task belonging to a machine."""

    __tablename__ = "maintenance_tasks"
    __table_args__ = (
        CheckConstraint(
            "interval_type IN ('daily','weekly','monthly','quarterly','interval_weeks')",
            name="ck_maintenance_tasks_interval_type",
        ),
        CheckConstraint(
            "interval_type <> 'interval_weeks' "
            "OR (interval_weeks IS NOT NULL AND interval_weeks >= 1)",
            name="ck_maintenance_tasks_interval_weeks",
        ),
        Index("ix_maintenance_tasks_machine", "machine_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    machine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    instructions: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    interval_type: Mapped[str] = mapped_column(String(16), nullable=False)
    # Only used when interval_type == 'interval_weeks' (every N weeks).
    interval_weeks: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    machine: Mapped["Machine"] = relationship("Machine", back_populates="tasks")


class MaintenanceFile(Base):
    """An uploaded maintenance document stored in Directus.

    ``file_kind`` is 'plan' for a reference/manufacturer maintenance plan, or
    'archive' for a scanned-back, signed KW sheet kept for the record.
    """

    __tablename__ = "maintenance_files"
    __table_args__ = (
        CheckConstraint(
            "file_kind IN ('plan','archive')", name="ck_maintenance_files_file_kind"
        ),
        Index("ix_maintenance_files_machine", "machine_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    machine_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("machines.id", ondelete="CASCADE"),
        nullable=False,
    )
    directus_file_uuid: Mapped[str] = mapped_column(String(64), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str | None] = mapped_column(String(127), nullable=True)
    file_kind: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default="plan"
    )

    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    machine: Mapped["Machine"] = relationship("Machine", back_populates="files")
