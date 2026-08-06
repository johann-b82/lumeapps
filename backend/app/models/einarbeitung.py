"""Einarbeitung — Katalog + Abteilungs-Matrix (v1.99, zuvor v1.92).

Der Einarbeitungsinhalt (mit Ansprechpartner) ist jetzt abteilungsunabhängiger
Katalog; eine Matrix legt fest, welche Inhalte für welche Abteilung nötig sind.
App-gepflegt — kein Excel-Import.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EinarbeitungKatalog(Base):
    """Ein Einarbeitungsinhalt mit Ansprechpartner — abteilungsunabhängig."""

    __tablename__ = "einarbeitung_katalog"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    inhalt: Mapped[str] = mapped_column(Text, nullable=False)
    #: Wer die Einarbeitung durchführt — Freitext (Name), auch Externe.
    ansprechpartner: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Bereich/Abteilung dieser Einarbeitung (v1.103) — Freitext; erscheint im
    #: PDF als „Abteilung". Leer → Fallback auf die Abteilung aus der Pflicht-Matrix.
    bereich: Mapped[str | None] = mapped_column(Text, nullable=True)
    reihenfolge: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    erstellt_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EinarbeitungPflicht(Base):
    """Matrix: dieser Einarbeitungsinhalt ist für diese Abteilung nötig."""

    __tablename__ = "einarbeitung_pflicht"
    __table_args__ = (
        UniqueConstraint("einarbeitung_id", "abteilung", name="uq_einarbeitung_pflicht"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    einarbeitung_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("einarbeitung_katalog.id", ondelete="CASCADE"), nullable=False
    )
    abteilung: Mapped[str] = mapped_column(String(120), nullable=False)
