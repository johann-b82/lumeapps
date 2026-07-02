"""Pydantic v2 DTOs for the ATR module (Phase A)."""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class AtrPartRead(BaseModel):
    id: int
    part_number: str
    part_number_norm: str
    supplier_article_code: str | None
    part_name: str | None
    drawing_number_issue: str | None
    default_weight_kg: Decimal | None
    qty: int
    category: str | None
    po_pos: str | None
    source_filename: str
    imported_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class AtrPartCreate(BaseModel):
    part_number: str = Field(..., max_length=60)
    supplier_article_code: str | None = Field(default=None, max_length=40)
    part_name: str | None = Field(default=None, max_length=200)
    drawing_number_issue: str | None = Field(default=None, max_length=60)
    default_weight_kg: Decimal | None = None
    qty: int = 1
    category: str | None = Field(default=None, max_length=40)
    po_pos: str | None = Field(default=None, max_length=20)


class AtrPartUpdate(BaseModel):
    part_number: str | None = Field(default=None, max_length=60)
    supplier_article_code: str | None = Field(default=None, max_length=40)
    part_name: str | None = Field(default=None, max_length=200)
    drawing_number_issue: str | None = Field(default=None, max_length=60)
    default_weight_kg: Decimal | None = None
    qty: int | None = None
    category: str | None = Field(default=None, max_length=40)
    po_pos: str | None = Field(default=None, max_length=20)


class AtrTemplateRead(BaseModel):
    id: int
    customer: str | None
    ac_programme: str | None
    work_package: str | None
    purchaser_spec: str | None
    atp: str | None
    supplier_spec: str | None
    reference_no: str | None
    supplier: str | None
    customer_spec: str | None
    nscm_code: str | None
    ata_chapter: str | None
    weighing_equipment: str | None
    qa_signer_default: str | None
    structure_filename: str | None
    has_structure: bool
    updated_at: datetime
    model_config = {"from_attributes": True}


class AtrTemplateUpdate(BaseModel):
    customer: str | None = Field(default=None, max_length=200)
    ac_programme: str | None = Field(default=None, max_length=100)
    work_package: str | None = None
    purchaser_spec: str | None = Field(default=None, max_length=200)
    atp: str | None = Field(default=None, max_length=200)
    supplier_spec: str | None = Field(default=None, max_length=200)
    reference_no: str | None = Field(default=None, max_length=200)
    supplier: str | None = Field(default=None, max_length=200)
    customer_spec: str | None = Field(default=None, max_length=100)
    nscm_code: str | None = Field(default=None, max_length=40)
    ata_chapter: str | None = Field(default=None, max_length=20)
    weighing_equipment: str | None = Field(default=None, max_length=100)
    qa_signer_default: str | None = Field(default=None, max_length=100)


class AtrImportPartPreview(BaseModel):
    part_number: str
    part_number_norm: str
    supplier_article_code: str | None
    part_name: str | None
    drawing_number_issue: str | None
    default_weight_kg: Decimal | None
    qty: int
    category: str | None
    status: Literal["new", "updated", "unchanged"]


class AtrImportPreview(BaseModel):
    source_filename: str
    header: dict
    parts: list[AtrImportPartPreview]
    new_count: int
    updated_count: int
    unchanged_count: int
    warnings: list[str]


class AtrImportResult(BaseModel):
    source_filename: str
    created: int
    updated: int
    template_updated: bool
    structure_set: bool
    warnings: list[str]
