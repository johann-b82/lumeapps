"""Pydantic v2 schemas for the KPI-Bewertung/Maßnahmen module (v1.107)."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Rating = Literal["red", "yellow", "green"]
Priority = Literal["low", "medium", "high"]
MeasureStatus = Literal["open", "in_progress", "done", "dropped"]


class KpiRegistryItem(BaseModel):
    key: str
    domain: str


# ── Comments ─────────────────────────────────────────────────────────────
class KpiCommentCreate(BaseModel):
    kpi_key: str
    body: str = Field(min_length=1, max_length=5000)
    rating: Rating | None = None
    author_name: str | None = None


class KpiCommentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kpi_key: str
    body: str
    rating: Rating | None
    author_id: uuid.UUID | None
    author_name: str | None
    created_at: datetime


# ── Measures ─────────────────────────────────────────────────────────────
class KpiMeasureCreate(BaseModel):
    kpi_key: str
    comment_id: uuid.UUID | None = None
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    assignee_personio_id: str | None = None
    assignee_name: str | None = None
    due_date: date | None = None
    priority: Priority = "medium"


class KpiMeasureUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    assignee_personio_id: str | None = None
    assignee_name: str | None = None
    due_date: date | None = None
    priority: Priority | None = None
    status: MeasureStatus | None = None


class KpiMeasureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    kpi_key: str
    comment_id: uuid.UUID | None
    title: str
    description: str
    assignee_personio_id: str | None
    assignee_name: str | None
    due_date: date | None
    priority: Priority
    status: MeasureStatus
    created_by_id: uuid.UUID | None
    created_at: datetime
    done_at: datetime | None


class KpiSummaryItem(BaseModel):
    """Per-KPI roll-up for the hub overview."""

    kpi_key: str
    domain: str
    comment_count: int
    open_measure_count: int
    last_rating: Rating | None = None
