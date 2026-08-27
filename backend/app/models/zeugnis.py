"""Arbeitszeugnis — Stammdaten, Bewertung und generierter Text (v1.110).

Ein ``Zeugnis`` friert die Stammdaten der Person zum Erstellzeitpunkt ein
(Snapshot), damit ein einmal ausgestelltes Zeugnis nicht durch spätere
Personio-Änderungen kippt. Die Note-je-Dimension steht in ``ZeugnisBewertung``;
den fertigen Fließtext (KI-generiert, danach von HR editierbar) hält
``abschnitte_json``.
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

#: Bewertungs-Dimensionen (Schlüssel, Reihenfolge = Reihenfolge im Zeugnis).
#: ``fuehrung`` nur bei Führungskräften. Benennung/Erklärung zweisprachig in i18n
#: unter ``zeugnisse.dim.*``.
ZEUGNIS_DIMENSIONEN = (
    "fachwissen",
    "auffassungsgabe",
    "arbeitsweise",
    "belastbarkeit",
    "arbeitserfolg",
    "sozialverhalten",
    "fuehrung",
)

#: Zeugnisarten.
ZEUGNIS_ARTEN = (
    "qualifiziert",
    "einfach",
    "zwischenzeugnis",
    "ausbildungszeugnis",
    "praktikumszeugnis",
)

#: Die generierten Abschnitte (Schlüssel des ``abschnitte_json``-Dicts).
ZEUGNIS_ABSCHNITTE = (
    "einleitung",
    "taetigkeitsbeschreibung",
    "leistungsbeurteilung",
    "sozialverhalten",
    "schlussformel",
)


class ZeugnisAussteller(Base):
    """Ausstellendes Unternehmen + Unterzeichner — i. d. R. genau eine Zeile."""

    __tablename__ = "zeugnis_aussteller"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    firma: Mapped[str] = mapped_column(Text, nullable=False)
    standort: Mapped[str | None] = mapped_column(Text, nullable=True)
    unterzeichner1_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    unterzeichner1_titel: Mapped[str | None] = mapped_column(Text, nullable=True)
    unterzeichner2_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    unterzeichner2_titel: Mapped[str | None] = mapped_column(Text, nullable=True)
    aktualisiert_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class Zeugnis(Base):
    """Ein Arbeitszeugnis mit eingefrorenem Stammdaten-Snapshot."""

    __tablename__ = "zeugnis"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: Herkunft der Person — Personio oder Externe (genau eines gesetzt).
    employee_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("personio_employees.id", ondelete="SET NULL"), nullable=True
    )
    extern_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("onboarding_extern.id", ondelete="SET NULL"), nullable=True
    )

    # --- Stammdaten-Snapshot (eingefroren beim Anlegen, danach editierbar) ---
    name: Mapped[str] = mapped_column(Text, nullable=False)
    #: 'm' | 'w' | 'd' — steuert Anrede und grammatische Formen im Text.
    geschlecht: Mapped[str | None] = mapped_column(String(1), nullable=True)
    geburtsdatum: Mapped[date | None] = mapped_column(Date, nullable=True)
    personalnummer: Mapped[str | None] = mapped_column(Text, nullable=True)
    abteilung: Mapped[str | None] = mapped_column(Text, nullable=True)
    taetigkeit: Mapped[str | None] = mapped_column(Text, nullable=True)
    eintritt: Mapped[date | None] = mapped_column(Date, nullable=True)
    austritt: Mapped[date | None] = mapped_column(Date, nullable=True)

    # --- Zeugnis-Metadaten ---
    art: Mapped[str] = mapped_column(String(20), nullable=False, default="qualifiziert")
    anlass: Mapped[str | None] = mapped_column(Text, nullable=True)
    fuehrungskraft: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ausstellungsdatum: Mapped[date | None] = mapped_column(Date, nullable=True)

    # --- HR-Freitexte (Eingang der KI-Generierung) ---
    taetigkeit_stichpunkte: Mapped[str | None] = mapped_column(Text, nullable=True)
    besondere_kompetenzen: Mapped[str | None] = mapped_column(Text, nullable=True)
    besondere_erfolge: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Ergebnis ---
    #: Aus den Einzelnoten berechnete Durchschnittsnote (z. B. 2.0).
    schlussnote: Mapped[Decimal | None] = mapped_column(Numeric(2, 1), nullable=True)
    #: Generierte Abschnitte (siehe ZEUGNIS_ABSCHNITTE); nach Generierung von HR
    #: editierbar. NULL, solange noch nichts generiert wurde.
    abschnitte_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="entwurf")

    erstellt_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    aktualisiert_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    bewertungen: Mapped[list["ZeugnisBewertung"]] = relationship(
        "ZeugnisBewertung", back_populates="zeugnis", cascade="all, delete-orphan"
    )


class ZeugnisVorlage(Base):
    """Benanntes Bewertungs-Profil (Noten je Dimension) zum Wiederverwenden."""

    __tablename__ = "zeugnis_vorlage"
    __table_args__ = (UniqueConstraint("name", name="uq_zeugnis_vorlage_name"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    #: {dimension: note} — Noten 1–4 je Dimension.
    noten: Mapped[dict] = mapped_column(JSONB, nullable=False)
    aktualisiert_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ZeugnisBewertung(Base):
    """Eine Note (1–4, Schulnotenprinzip) je Bewertungsdimension."""

    __tablename__ = "zeugnis_bewertung"
    __table_args__ = (
        UniqueConstraint("zeugnis_id", "dimension", name="uq_zeugnis_bewertung"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    zeugnis_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("zeugnis.id", ondelete="CASCADE"), nullable=False
    )
    dimension: Mapped[str] = mapped_column(String(30), nullable=False)
    #: 1 = sehr gut … 4 = ausreichend.
    note: Mapped[int] = mapped_column(Integer, nullable=False)

    zeugnis: Mapped["Zeugnis"] = relationship("Zeugnis", back_populates="bewertungen")
