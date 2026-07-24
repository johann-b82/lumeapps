"""Einarbeitungsmatrix (v1.92).

Stammdaten für den Einarbeitungsbogen: je Abteilung eine Liste von
Einarbeitungsinhalten mit Ansprechpartner. App-gepflegt — kein Excel-Import.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EinarbeitungInhalt(Base):
    """Eine Zeile der Einarbeitungsmatrix — ein Inhalt für eine Abteilung."""

    __tablename__ = "einarbeitung_inhalt"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: Personio-Abteilungsname; nach ihm wird der Bogen einer Person zusammengestellt.
    abteilung: Mapped[str] = mapped_column(String(120), nullable=False)
    #: Wer die Einarbeitung durchführt — Freitext (Name), leer erlaubt.
    ansprechpartner: Mapped[str | None] = mapped_column(Text, nullable=True)
    inhalt: Mapped[str] = mapped_column(Text, nullable=False)
    reihenfolge: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    erstellt_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
