"""Pydantic v2 DTOs for ATR deliveries (Phase B)."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.services.atr_format import normalize_po_pos


class AtrDeliveryItemRead(BaseModel):
    id: int
    pos: int | None
    supplier_article_code: str | None
    part_number: str | None
    part_number_norm: str | None
    matched_part_id: int | None
    part_name: str | None
    drawing_number_issue: str | None
    category: str | None
    qty: int
    weight_kg: Decimal | None
    po_pos: str | None
    match_status: str
    row_order: int
    model_config = {"from_attributes": True}


class AtrDeliveryItemUpdate(BaseModel):
    weight_kg: Decimal | None = None
    po_pos: str | None = Field(default=None, max_length=20)
    part_name: str | None = Field(default=None, max_length=200)
    drawing_number_issue: str | None = Field(default=None, max_length=60)
    category: str | None = Field(default=None, max_length=40)

    @field_validator("po_pos")
    @classmethod
    def _norm_po_pos(cls, v: str | None) -> str | None:
        return normalize_po_pos(v)


class AtrDeliveryRead(BaseModel):
    id: int
    source_filename: str
    lieferschein_nr: str | None
    datum: date | None
    ba_auftrag: str | None
    po_number: str | None
    ac_programme: str | None
    compartment: str | None
    msn: str | None
    bed_config: str | None
    set_title: str | None
    atr_number: str | None
    container_number: str | None
    weighing_date: date | None
    testing_date: date | None
    qa_signer: str | None
    max_guaranteed_weight_kg: Decimal | None
    status: str
    origin: str
    source_path: str | None
    output_written_at: datetime | None
    created_at: datetime
    updated_at: datetime
    items: list[AtrDeliveryItemRead]
    model_config = {"from_attributes": True}


class AtrDeliverySummary(BaseModel):
    id: int
    source_filename: str
    ba_auftrag: str | None
    compartment: str | None
    atr_number: str | None
    msn: str | None
    status: str
    created_at: datetime
    model_config = {"from_attributes": True}


class AtrDeliveryUpdate(BaseModel):
    po_number: str | None = Field(default=None, max_length=60)
    set_title: str | None = Field(default=None, max_length=100)
    atr_number: str | None = Field(default=None, max_length=80)
    container_number: str | None = Field(default=None, max_length=40)
    weighing_date: date | None = None
    testing_date: date | None = None
    qa_signer: str | None = Field(default=None, max_length=100)
    max_guaranteed_weight_kg: Decimal | None = None


class AtrGenerateManifest(BaseModel):
    delivery_id: int
    files: list[Literal["atr_xlsx", "atr_pdf", "label_docx"]]
    pdf_available: bool
    unmatched_count: int
    warnings: list[str]
