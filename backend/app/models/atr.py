"""ATR module ORM — global parts catalog + single structural template.

Phase A of the ATR roadmap (see
docs/superpowers/specs/2026-06-25-atr-reference-foundation-design.md).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import BYTEA
from sqlalchemy.orm import Mapped, mapped_column

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
    """Singleton (id=1): editable header-block defaults + the stored structural workbook."""
    __tablename__ = "atr_template"
    __table_args__ = (
        CheckConstraint("id = 1", name="ck_atr_template_singleton"),
    )

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
