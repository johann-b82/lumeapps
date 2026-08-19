"""Einarbeitung — Katalog + Abteilungs-Matrix (v1.99, zuvor v1.92).

Der Einarbeitungsinhalt (mit Ansprechpartner) ist jetzt abteilungsunabhängiger
Katalog; eine Matrix legt fest, welche Inhalte für welche Abteilung nötig sind.
App-gepflegt — kein Excel-Import.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
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
from sqlalchemy.dialects.postgresql import JSONB
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


class EinarbeitungDokument(Base):
    """Ein Einarbeitungs-Vorgang: erzeugtes Formular + Lebenszyklus + Scan-Prüfung.

    Anders als der frühere (zustandslose) PDF-Download wird der Einarbeitungsplan
    hier als Vorgang persistiert. ``doc_uid`` steckt als QR-Code auf dem Blatt und
    ordnet einen später hochgeladenen Scan zuverlässig wieder diesem Vorgang zu —
    unabhängig von Name oder Dateiname. ``feld_layout`` hält die (seitenrelativen)
    Rechtecke der Pflichtfelder für die halbautomatische Vollständigkeitsprüfung.

    Der Laufweg steht nicht mehr auf dem Formular, sondern hier: die vier
    Zeitstempel ``erstellt/uebergeben/zurueck/geprueft`` bilden ihn ab.
    """

    __tablename__ = "einarbeitung_dokument"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: Eindeutiger Token im QR-Code; ordnet einen Scan zuverlässig dem Vorgang zu.
    doc_uid: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)

    #: Personio-Mitarbeiter (NULL bei Externen); Name/Stelle/Beginn als Snapshot,
    #: damit der Vorgang unabhängig von späteren Personio-Änderungen dokumentiert bleibt.
    employee_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("personio_employees.id", ondelete="SET NULL"), nullable=True
    )
    mitarbeiter_name: Mapped[str] = mapped_column(Text, nullable=False)
    stelle: Mapped[str | None] = mapped_column(Text, nullable=True)
    beginn: Mapped[date | None] = mapped_column(Date, nullable=True)
    #: Abteilungen, aus denen der Bogen gebaut wurde (Liste von Kürzeln/Namen).
    abteilungen: Mapped[list | None] = mapped_column(JSONB, nullable=True)

    #: Directus-Dateien: erzeugtes Blankoformular bzw. hochgeladener Scan.
    pdf_uuid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    scan_uuid: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Normierte Feld-Rechtecke (0..1) + Labels für die Scan-Prüfung.
    feld_layout: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    #: Lebenszyklus: erstellt -> uebergeben -> zurueck -> geprueft.
    status: Mapped[str] = mapped_column(String(24), nullable=False, server_default="erstellt")
    erstellt_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    uebergeben_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    zurueck_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    geprueft_am: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    #: Ergebnis der halbautomatischen Feld-Prüfung (pro Feld erkannt/leer) und die
    #: Gesamtbewertung; ``vollstaendig`` ist manuell überstimmbar. NULL = noch ungeprüft.
    pruef_ergebnis: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    vollstaendig: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    kommentar: Mapped[str | None] = mapped_column(Text, nullable=True)
