"""ATR module ORM — global parts catalog + single structural template.

Phase A of the ATR roadmap (see
docs/superpowers/specs/2026-06-25-atr-reference-foundation-design.md).
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class AtrPart(Base):
    """One row per distinct part (by part_number_norm). The full editable catalog."""
    __tablename__ = "atr_part"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    part_number: Mapped[str] = mapped_column(String(60), nullable=False)
    part_number_norm: Mapped[str] = mapped_column(String(40), nullable=False, unique=True)
    supplier_article_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    part_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    drawing_number_issue: Mapped[str | None] = mapped_column(String(60), nullable=True)
    default_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    po_pos: Mapped[str | None] = mapped_column(String(20), nullable=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AtrTemplate(Base):
    """Structural workbook + header defaults, one row per programme: id=1 = A350,
    id=2 = A380."""
    __tablename__ = "atr_template"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    customer: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ac_programme: Mapped[str | None] = mapped_column(String(100), nullable=True)
    work_package: Mapped[str | None] = mapped_column(Text, nullable=True)
    purchaser_spec: Mapped[str | None] = mapped_column(String(200), nullable=True)
    atp: Mapped[str | None] = mapped_column(String(200), nullable=True)
    supplier_spec: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reference_no: Mapped[str | None] = mapped_column(String(200), nullable=True)
    supplier: Mapped[str | None] = mapped_column(String(200), nullable=True)
    customer_spec: Mapped[str | None] = mapped_column(String(100), nullable=True)
    nscm_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ata_chapter: Mapped[str | None] = mapped_column(String(20), nullable=True)
    weighing_equipment: Mapped[str | None] = mapped_column(String(100), nullable=True)
    qa_signer_default: Mapped[str | None] = mapped_column(String(100), nullable=True)
    structure_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    structure_xlsx: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AtrDelivery(Base):
    """One processed Lieferschein (Phase B)."""
    __tablename__ = "atr_delivery"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    lieferschein_nr: Mapped[str | None] = mapped_column(String(40), nullable=True)
    datum: Mapped[date | None] = mapped_column(Date, nullable=True)
    ba_auftrag: Mapped[str | None] = mapped_column(String(40), nullable=True)
    po_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ac_programme: Mapped[str | None] = mapped_column(String(40), nullable=True)
    programme_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    compartment: Mapped[str | None] = mapped_column(String(8), nullable=True)
    msn: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bed_config: Mapped[str | None] = mapped_column(String(8), nullable=True)
    set_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    atr_number: Mapped[str | None] = mapped_column(String(80), nullable=True)
    container_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    weighing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    testing_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    qa_signer: Mapped[str | None] = mapped_column(String(100), nullable=True)
    max_guaranteed_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="draft")
    atr_xlsx: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    atr_pdf: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    label_docx: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    origin: Mapped[str] = mapped_column(String(8), nullable=False, default="upload")
    source_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    output_written_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    items: Mapped[list["AtrDeliveryItem"]] = relationship(
        "AtrDeliveryItem", back_populates="delivery",
        cascade="all, delete-orphan", order_by="AtrDeliveryItem.row_order",
    )


class AtrDeliveryItem(Base):
    """One Lieferschein position within a delivery."""
    __tablename__ = "atr_delivery_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    delivery_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("atr_delivery.id", ondelete="CASCADE"), nullable=False, index=True
    )
    pos: Mapped[int | None] = mapped_column(Integer, nullable=True)
    supplier_article_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    part_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    part_number_norm: Mapped[str | None] = mapped_column(String(40), nullable=True)
    matched_part_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("atr_part.id", ondelete="SET NULL"), nullable=True
    )
    part_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    drawing_number_issue: Mapped[str | None] = mapped_column(String(60), nullable=True)
    category: Mapped[str | None] = mapped_column(String(40), nullable=True)
    qty: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
    po_pos: Mapped[str | None] = mapped_column(String(20), nullable=True)
    match_status: Mapped[str] = mapped_column(String(12), nullable=False, default="unmatched")
    serial_numbers: Mapped[str | None] = mapped_column(Text, nullable=True)
    row_order: Mapped[int] = mapped_column(Integer, nullable=False)

    delivery: Mapped["AtrDelivery"] = relationship("AtrDelivery", back_populates="items")
