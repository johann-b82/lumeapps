"""Pydantic v2 schemas for the FAIR drawing-ballooning module (v1.63).

All geometry is normalized to [0, 1] against the drawing's natural page size.
``BalloonIn`` never carries ``number`` — the server assigns it. ``BalloonPatch``
makes every field optional so the editor can move a bubble, edit its value, or
re-page it independently.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class BalloonIn(BaseModel):
    """Payload to create a balloon (server assigns ``number``)."""

    page_no: int = Field(default=1, ge=1)
    region_x: float = Field(ge=0, le=1)
    region_y: float = Field(ge=0, le=1)
    region_w: float = Field(gt=0, le=1)
    region_h: float = Field(gt=0, le=1)
    tail_x: float = Field(ge=0, le=1)
    tail_y: float = Field(ge=0, le=1)
    value_text: str = ""


class BalloonPatch(BaseModel):
    """Partial update — move the bubble/region, edit the value, or re-page."""

    page_no: int | None = Field(default=None, ge=1)
    region_x: float | None = Field(default=None, ge=0, le=1)
    region_y: float | None = Field(default=None, ge=0, le=1)
    region_w: float | None = Field(default=None, gt=0, le=1)
    region_h: float | None = Field(default=None, gt=0, le=1)
    tail_x: float | None = Field(default=None, ge=0, le=1)
    tail_y: float | None = Field(default=None, ge=0, le=1)
    value_text: str | None = None


class BalloonReorder(BaseModel):
    """New balloon order (project balloon ids, in the desired 1..n sequence)."""

    ordered_ids: list[uuid.UUID]


class BalloonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    number: int
    page_no: int
    region_x: float
    region_y: float
    region_w: float
    region_h: float
    tail_x: float
    tail_y: float
    value_text: str


class ProjectOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    part_number: str | None
    customer: str | None
    article_number: str | None
    file_kind: str
    mime_type: str | None
    page_count: int
    rotation: int
    created_at: datetime
    updated_at: datetime


class ProjectDetail(ProjectOut):
    balloons: list[BalloonOut] = Field(default_factory=list)


class ProjectPatch(BaseModel):
    """Rename, set part number / customer / article number, page count, rotation."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    part_number: str | None = Field(default=None, max_length=64)
    customer: str | None = Field(default=None, max_length=255)
    article_number: str | None = Field(default=None, max_length=64)
    page_count: int | None = Field(default=None, ge=1)
    rotation: int | None = Field(default=None, ge=0, le=270)
