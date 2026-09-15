"""Produktions-Priorisierung ORM models — v1.126.

Eigenständiges Modul: alle Tabellen tragen das Präfix ``prio_`` und hängen an
keiner anderen Tabelle, damit es sich später herauslösen lässt.

  - ``prio_artikel``          Artikelstamm (Apollo AswStm) — nur Namen/Typ.
  - ``prio_plan_position``    Ressourcenplan (Apollo) einstufig je Artikel:
                              Halbzeug-/Artikel-Komponenten und RES-Arbeitsgänge
                              in Positionsreihenfolge. Material/Werkzeug entfällt.
  - ``prio_auftrag_position`` offene Auftragspositionen (AswKpf) = BA-Positionen.
  - ``prio_liste`` / ``prio_liste_eintrag``
                              importierte Prioritätslisten (z. B. Diehl) mit Rang
                              und Termin je BA-Position.
  - ``prio_manuell``          die per Drag & Drop gespeicherte Reihenfolge.
  - ``prio_import``           Stand des letzten Stammdaten-Imports je Quelle.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.database import Base


class PrioArtikel(Base):
    __tablename__ = "prio_artikel"

    artikelnr: Mapped[str] = mapped_column(String(64), primary_key=True)
    typ: Mapped[str] = mapped_column(String(8), nullable=False)
    bezeichnung: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bezeichnung2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    einheit: Mapped[str | None] = mapped_column(String(16), nullable=True)


class PrioPlanPosition(Base):
    __tablename__ = "prio_plan_position"
    __table_args__ = (Index("ix_prio_plan_position_artikel", "artikelnr", "pos"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    artikelnr: Mapped[str] = mapped_column(String(64), nullable=False)
    pos: Mapped[int] = mapped_column(Integer, nullable=False)
    #: HLB/ART = Komponente (``ref`` = Artikelnr), RES = Arbeitsgang (``ref`` = Ressource)
    typ: Mapped[str] = mapped_column(String(8), nullable=False)
    ref: Mapped[str] = mapped_column(String(64), nullable=False)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    menge: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    einheit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    kostenstelle: Mapped[str | None] = mapped_column(String(16), nullable=True)
    ruestzeit: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)
    operativzeit: Mapped[Decimal | None] = mapped_column(Numeric(14, 4), nullable=True)


class PrioAuftragPosition(Base):
    __tablename__ = "prio_auftrag_position"

    vorgang_nr: Mapped[str] = mapped_column(String(32), primary_key=True)
    pos: Mapped[int] = mapped_column(Integer, primary_key=True)
    upos: Mapped[int] = mapped_column(Integer, primary_key=True)
    artikelnr: Mapped[str | None] = mapped_column(String(64), nullable=True)
    bezeichnung: Mapped[str | None] = mapped_column(String(255), nullable=True)
    menge: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    einheit: Mapped[str | None] = mapped_column(String(16), nullable=True)
    lieferdatum: Mapped[date | None] = mapped_column(Date, nullable=True)
    kunde_nr: Mapped[str | None] = mapped_column(String(32), nullable=True)
    kunde: Mapped[str | None] = mapped_column(String(255), nullable=True)
    fremdnr: Mapped[str | None] = mapped_column(String(64), nullable=True)
    pos_typ_2: Mapped[str | None] = mapped_column(String(16), nullable=True)
    status: Mapped[str | None] = mapped_column(String(8), nullable=True)
    gesperrt: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")


class PrioListe(Base):
    __tablename__ = "prio_liste"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    typ: Mapped[str] = mapped_column(String(32), nullable=False)
    #: Stand der Liste — die jüngste Liste gewinnt bei Überschneidungen.
    stand: Mapped[date] = mapped_column(Date, nullable=False)
    dateiname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    importiert_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PrioListeEintrag(Base):
    __tablename__ = "prio_liste_eintrag"
    __table_args__ = (
        UniqueConstraint("liste_id", "vorgang_nr", "pos", "upos", name="uq_prio_liste_eintrag"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    liste_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("prio_liste.id", ondelete="CASCADE"), nullable=False
    )
    vorgang_nr: Mapped[str] = mapped_column(String(32), nullable=False)
    pos: Mapped[int] = mapped_column(Integer, nullable=False)
    upos: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    rang: Mapped[int | None] = mapped_column(Integer, nullable=True)
    termin: Mapped[date | None] = mapped_column(Date, nullable=True)
    kommentar: Mapped[str | None] = mapped_column(Text, nullable=True)
    extern_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)


class PrioManuell(Base):
    __tablename__ = "prio_manuell"

    vorgang_nr: Mapped[str] = mapped_column(String(32), primary_key=True)
    pos: Mapped[int] = mapped_column(Integer, primary_key=True)
    upos: Mapped[int] = mapped_column(Integer, primary_key=True)
    reihenfolge: Mapped[int] = mapped_column(Integer, nullable=False)


class PrioImport(Base):
    __tablename__ = "prio_import"

    quelle: Mapped[str] = mapped_column(String(32), primary_key=True)
    dateiname: Mapped[str | None] = mapped_column(String(255), nullable=True)
    zeilen: Mapped[int] = mapped_column(Integer, nullable=False)
    warnungen: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    importiert_am: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
