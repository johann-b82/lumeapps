"""Schulungs-Modul ORM — Katalog, Teilnahmen, Import-Protokoll.

Bildet die bisherige ``Schulungsübersicht.xlsx`` ab (Migration
``v1_86_schulungen``). Die Excel führt je Bereich eine transponierte Matrix:
Spalten sind Mitarbeiter, Zeilen sind Schulungen mit je drei Werten
(Initial / aktuell / nächste Fälligkeit).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

#: Bereiche, wie sie die Excel als Arbeitsblätter führt.
SCHULUNG_BEREICHE = ("betrieblich", "Produktion", "Verwaltung")

#: Ebenen der Anforderungsmatrix — feine Excel-Kürzel bzw. grobe Personio-Abteilung.
PFLICHT_EBENEN = ("kuerzel", "personio")


class SchulungKatalog(Base):
    """Eine Schulung des Katalogs, eindeutig je (Bereich, Name)."""

    __tablename__ = "schulung_katalog"
    __table_args__ = (
        UniqueConstraint("bereich", "name", name="uq_schulung_katalog_bereich_name"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bereich: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    #: Originaltext aus der Excel, z. B. "alle 2 Jahre (und bei Bedarf)".
    turnus: Mapped[str | None] = mapped_column(String(80), nullable=True)
    #: Daraus abgeleitete Periode in Monaten; NULL wenn nicht berechenbar
    #: ("bei Bedarf", "alle 3 - 5 Jahre").
    turnus_monate: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    aktiv: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    teilnahmen: Mapped[list["SchulungTeilnahme"]] = relationship(
        "SchulungTeilnahme",
        back_populates="schulung",
        cascade="all, delete-orphan",
    )


class SchulungPflicht(Base):
    """Anforderungsmatrix: diese Schulung ist für diese Abteilung Pflicht.

    ``ebene`` unterscheidet die feinen Excel-Kürzel (``kuerzel``, z. B. NÄH) von
    den groben Personio-Abteilungen (``personio``, z. B. Production). Die
    Abteilung ist bewusst Text — die Wertelisten stammen aus Fremdsystemen.
    """

    __tablename__ = "schulung_pflicht"
    __table_args__ = (
        CheckConstraint("ebene IN ('kuerzel','personio')", name="ck_schulung_pflicht_ebene"),
        UniqueConstraint("schulung_id", "ebene", "abteilung", name="uq_schulung_pflicht_regel"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schulung_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("schulung_katalog.id", ondelete="CASCADE"), nullable=False
    )
    ebene: Mapped[str] = mapped_column(String(20), nullable=False)
    abteilung: Mapped[str] = mapped_column(String(80), nullable=False)


class SchulungRolle(Base):
    """Zuordnung Personio-Position → Abteilungskürzel.

    Brücke für Neueintritte: Personio liefert nur die grobe Abteilung, die
    Anforderungsmatrix arbeitet zusätzlich auf den feinen Excel-Kürzeln.
    Gematcht wird auf ``position_norm`` (klein, Whitespace zusammengefasst),
    weil die Positionen in Personio uneinheitlich geschrieben sind.
    """

    __tablename__ = "schulung_rolle"
    __table_args__ = (
        UniqueConstraint("position_norm", name="uq_schulung_rolle_position"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    position: Mapped[str] = mapped_column(Text, nullable=False)
    position_norm: Mapped[str] = mapped_column(String(200), nullable=False)
    abteilung_kuerzel: Mapped[str] = mapped_column(String(30), nullable=False)


class SchulungImport(Base):
    """Protokoll eines Excel-Imports — je Lauf eine Zeile."""

    __tablename__ = "schulung_import"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dateiname: Mapped[str] = mapped_column(Text, nullable=False)
    importiert_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    schulungen_gesamt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    teilnahmen_gesamt: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Zeilen ohne Personio-Treffer (Personalnummer nicht gepflegt / Austritt).
    nicht_zugeordnet: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notiz: Mapped[str | None] = mapped_column(Text, nullable=True)


class SchulungTeilnahme(Base):
    """Schulungsstand einer Person: Initial, aktuell, nächste Fälligkeit.

    ``employee_id`` ist bewusst nullable — die Excel identifiziert über die
    Personalnummer, die in Personio nur teilweise gepflegt ist. Zeilen ohne
    Treffer bleiben mit Personalnummer und Name erhalten statt verworfen zu
    werden.
    """

    __tablename__ = "schulung_teilnahme"
    # Eindeutigkeit über zwei partielle Indizes (Migration v1_89), je einen pro
    # Identitätsart — Personalnummer (Excel-Historie) bzw. Personio-ID.

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    schulung_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("schulung_katalog.id", ondelete="CASCADE"), nullable=False
    )
    employee_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("personio_employees.id", ondelete="SET NULL"), nullable=True
    )
    #: Schlüssel der Excel-Historie; für rein aus Personio angelegte Zeilen NULL.
    personalnummer: Mapped[str | None] = mapped_column(String(30), nullable=True)
    mitarbeiter_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: Abteilungskürzel der Excel (NÄH, CUT, WVK …) — eigenes Schema, nicht
    #: identisch mit Personios ``department``.
    abteilung_kuerzel: Mapped[str | None] = mapped_column(String(30), nullable=True)
    initial_datum: Mapped[date | None] = mapped_column(Date, nullable=True)
    aktuell_datum: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: Quartalsangabe der Excel, unverändert ("Q3/2025").
    naechste_faellig: Mapped[str | None] = mapped_column(String(30), nullable=True)
    #: Berechnet aus aktuell_datum + turnus_monate, sofern bekannt.
    naechste_faellig_am: Mapped[date | None] = mapped_column(Date, nullable=True)
    import_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("schulung_import.id", ondelete="SET NULL"), nullable=True
    )

    schulung: Mapped["SchulungKatalog"] = relationship(
        "SchulungKatalog", back_populates="teilnahmen"
    )
