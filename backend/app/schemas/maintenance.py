"""Pydantic v2 schemas for the Maschinen-Wartung module (v1.82).

``*In`` create payloads, ``*Patch`` all-optional partial updates, ``*Out``
read models (``from_attributes``). ``MachineDetail`` nests a machine's tasks
and files so the detail page loads in a single request.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

IntervalType = Literal["daily", "weekly", "monthly", "quarterly", "interval_weeks"]
MachineStatus = Literal["active", "inactive"]
FileKind = Literal["plan", "archive"]


# ── Machines ────────────────────────────────────────────────────────────


class MachineIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    inventory_no: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=255)
    manufacturer: str | None = Field(default=None, max_length=255)
    model: str | None = Field(default=None, max_length=255)
    responsible: str | None = Field(default=None, max_length=255)
    status: MachineStatus = "active"
    notes: str = ""


class MachinePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    inventory_no: str | None = Field(default=None, max_length=64)
    location: str | None = Field(default=None, max_length=255)
    manufacturer: str | None = Field(default=None, max_length=255)
    model: str | None = Field(default=None, max_length=255)
    responsible: str | None = Field(default=None, max_length=255)
    status: MachineStatus | None = None
    notes: str | None = None


class MachineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    inventory_no: str | None
    location: str | None
    manufacturer: str | None
    model: str | None
    responsible: str | None
    status: str
    notes: str
    created_at: datetime
    updated_at: datetime


# ── Tasks ───────────────────────────────────────────────────────────────


class TaskIn(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    instructions: str = ""
    interval_type: IntervalType
    interval_weeks: int | None = Field(default=None, ge=1, le=520)

    @model_validator(mode="after")
    def _check_interval_weeks(self) -> "TaskIn":
        if self.interval_type == "interval_weeks" and self.interval_weeks is None:
            raise ValueError("interval_weeks is required when interval_type is 'interval_weeks'")
        if self.interval_type != "interval_weeks":
            self.interval_weeks = None
        return self


class TaskPatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    instructions: str | None = None
    interval_type: IntervalType | None = None
    interval_weeks: int | None = Field(default=None, ge=1, le=520)


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    instructions: str
    interval_type: str
    interval_weeks: int | None
    created_at: datetime
    updated_at: datetime


# ── Files ───────────────────────────────────────────────────────────────


class FileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    filename: str
    mime_type: str | None
    file_kind: str
    uploaded_at: datetime


# ── Detail (machine + children) ─────────────────────────────────────────


class MachineDetail(MachineOut):
    tasks: list[TaskOut] = Field(default_factory=list)
    files: list[FileOut] = Field(default_factory=list)
