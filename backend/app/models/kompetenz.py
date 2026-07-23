"""Kompetenzen — Qualifikationsmatrix je Bereich (v1.90).

Die Excel-Matrizen sind transponiert: Zeilen = Qualifikationen, Spalten =
Personen, je Person ein Spaltenpaar (Anforderungslevel, Erfüllungsgrad).
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

#: Die vier Fachbereiche. Quality bringt drei Blätter mit (QM, CS, QS).
KOMPETENZ_BEREICHE = ("produktion", "verwaltung", "safety", "quality")

#: Legende der Excel — Anforderungslevel.
ANFORDERUNGSLEVEL = {
    0: "nicht gefordert",
    1: "Grundkenntnisse erforderlich",
    2: "Fachwissen für Zuarbeiten erforderlich",
    3: "gutes Fachwissen, selbstständiges Arbeiten",
    4: "Experte",
}


class KompetenzMatrix(Base):
    """Eine Matrix = ein Blatt einer Bereichsdatei."""

    __tablename__ = "kompetenz_matrix"
    __table_args__ = (UniqueConstraint("bereich", "blatt", name="uq_kompetenz_matrix"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    bereich: Mapped[str] = mapped_column(String(30), nullable=False)
    blatt: Mapped[str] = mapped_column(String(120), nullable=False)
    titel: Mapped[str | None] = mapped_column(Text, nullable=True)
    #: "Stand"-Datum aus der Kopfzeile.
    stand: Mapped[date | None] = mapped_column(Date, nullable=True)
    dateiname: Mapped[str] = mapped_column(Text, nullable=False)
    importiert_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    qualifikationen: Mapped[list["KompetenzQualifikation"]] = relationship(
        "KompetenzQualifikation", back_populates="matrix", cascade="all, delete-orphan"
    )
    personen: Mapped[list["KompetenzPerson"]] = relationship(
        "KompetenzPerson", back_populates="matrix", cascade="all, delete-orphan"
    )


class KompetenzQualifikation(Base):
    """Eine Zeile der Matrix."""

    __tablename__ = "kompetenz_qualifikation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    matrix_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("kompetenz_matrix.id", ondelete="CASCADE"), nullable=False
    )
    nr: Mapped[int | None] = mapped_column(Integer, nullable=True)
    kategorie: Mapped[str | None] = mapped_column(Text, nullable=True)
    bezeichnung: Mapped[str] = mapped_column(Text, nullable=False)
    reihenfolge: Mapped[int] = mapped_column(Integer, nullable=False)

    matrix: Mapped["KompetenzMatrix"] = relationship(
        "KompetenzMatrix", back_populates="qualifikationen"
    )
    bewertungen: Mapped[list["KompetenzBewertung"]] = relationship(
        "KompetenzBewertung", back_populates="qualifikation", cascade="all, delete-orphan"
    )


class KompetenzPerson(Base):
    """Eine Spalte der Matrix.

    ``employee_id`` bleibt NULL, wenn der Name in Personio nicht auffindbar ist
    — Schreibfehler in der Excel oder eine reine "N/A"-Platzhalterspalte.
    """

    __tablename__ = "kompetenz_person"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    matrix_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("kompetenz_matrix.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    employee_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("personio_employees.id", ondelete="SET NULL"), nullable=True
    )
    reihenfolge: Mapped[int] = mapped_column(Integer, nullable=False)

    matrix: Mapped["KompetenzMatrix"] = relationship(
        "KompetenzMatrix", back_populates="personen"
    )
    bewertungen: Mapped[list["KompetenzBewertung"]] = relationship(
        "KompetenzBewertung", back_populates="person", cascade="all, delete-orphan"
    )


class KompetenzBewertung(Base):
    """Eine Zelle: was ist gefordert, wie weit ist es erfüllt."""

    __tablename__ = "kompetenz_bewertung"
    __table_args__ = (
        UniqueConstraint("qualifikation_id", "person_id", name="uq_kompetenz_bewertung"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    qualifikation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("kompetenz_qualifikation.id", ondelete="CASCADE"), nullable=False
    )
    person_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("kompetenz_person.id", ondelete="CASCADE"), nullable=False
    )
    #: 0-4, siehe ANFORDERUNGSLEVEL.
    anforderungslevel: Mapped[int | None] = mapped_column(Integer, nullable=True)
    #: 0-100 %.
    erfuellungsgrad: Mapped[int | None] = mapped_column(Integer, nullable=True)

    qualifikation: Mapped["KompetenzQualifikation"] = relationship(
        "KompetenzQualifikation", back_populates="bewertungen"
    )
    person: Mapped["KompetenzPerson"] = relationship(
        "KompetenzPerson", back_populates="bewertungen"
    )
