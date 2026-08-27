"""Newsletter — vierteljährliche Ausgabe mit sechs festen Rubriken (v1.112).

Eine ``Newsletter``-Ausgabe (Jahr + Quartal) bündelt mehrere ``NewsletterEintrag``
je Rubrik. Der Inhalt ist **Markdown** (sicher via react-markdown gerendert),
plus optional ein Bild (bytea) je Eintrag. Dieselbe Ausgabe wird online gerendert
und als PDF exportiert.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

#: Die sechs festen Rubriken (Schlüssel; Anzeigetitel via i18n newsletter.rubrik.*).
#: Reihenfolge = Reihenfolge im Newsletter.
NEWSLETTER_RUBRIKEN = (
    "arash",
    "aschkan",
    "intern",
    "rueckblick",
    "menschen",
    "neuigkeiten",
)

NEWSLETTER_STATUS = ("entwurf", "veroeffentlicht")


class Newsletter(Base):
    """Eine Ausgabe — genau eine je (Jahr, Quartal)."""

    __tablename__ = "newsletter"
    __table_args__ = (
        UniqueConstraint("jahr", "quartal", name="uq_newsletter_ausgabe"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    jahr: Mapped[int] = mapped_column(Integer, nullable=False)
    #: 1–4.
    quartal: Mapped[int] = mapped_column(Integer, nullable=False)
    titel: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="entwurf")
    #: Eingefrorener Stand der Belegschafts-KPIs (v1.113) — beim Einfügen aus dem
    #: HR-Aggregat kopiert, damit eine Archiv-Ausgabe stabil bleibt. NULL = ohne
    #: KPI-Block.
    kpi_snapshot: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    #: Reihenfolge der Blöcke im Newsletter (v1.114) — Liste aus Rubrik-Schlüsseln
    #: + "kpi", per Drag&Drop sortierbar. NULL = Standardreihenfolge.
    block_reihenfolge: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    #: Vollflächiges Titel-/Rückseitenbild (v1.117) — je Ausgabe eins, inline
    #: serviert; NULL = Text-/Verlaufs-Platzhalter.
    cover_bild: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    cover_mime: Mapped[str | None] = mapped_column(String(64), nullable=True)
    rueck_bild: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    rueck_mime: Mapped[str | None] = mapped_column(String(64), nullable=True)
    #: Überschriebene Abschnitts-Titel (v1.118) — {block_key: titel} je Rubrik
    #: oder "kpi"; fehlt ein Key, gilt der i18n-Standardname.
    rubrik_titel: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    erstellt_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    aktualisiert_am: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    eintraege: Mapped[list["NewsletterEintrag"]] = relationship(
        "NewsletterEintrag",
        back_populates="newsletter",
        cascade="all, delete-orphan",
        order_by="NewsletterEintrag.rubrik, NewsletterEintrag.reihenfolge",
    )


class NewsletterEintrag(Base):
    """Ein Eintrag unter einer Rubrik: Untertitel + Markdown-Inhalt + optional Bild."""

    __tablename__ = "newsletter_eintrag"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    newsletter_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("newsletter.id", ondelete="CASCADE"), nullable=False
    )
    #: Eine der NEWSLETTER_RUBRIKEN.
    rubrik: Mapped[str] = mapped_column(String(20), nullable=False)
    untertitel: Mapped[str] = mapped_column(Text, nullable=False)
    #: Markdown (react-markdown rendert es; kein rohes HTML).
    inhalt_md: Mapped[str] = mapped_column(Text, nullable=False, default="")
    #: Optionales Bild je Eintrag (Rasterformat), inline serviert.
    bild_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    bild_mime: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reihenfolge: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    newsletter: Mapped["Newsletter"] = relationship("Newsletter", back_populates="eintraege")
    #: Mehrere Bilder (Puzzle-Raster), nach Reihenfolge sortiert.
    bilder: Mapped[list["NewsletterEintragBild"]] = relationship(
        "NewsletterEintragBild",
        back_populates="eintrag",
        cascade="all, delete-orphan",
        order_by="NewsletterEintragBild.reihenfolge",
    )


class NewsletterEintragBild(Base):
    """Ein Bild eines Eintrags im Puzzle-Raster (bytea + Zellen-Spanne)."""

    __tablename__ = "newsletter_eintrag_bild"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    eintrag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("newsletter_eintrag.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bild_data: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    bild_mime: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reihenfolge: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    #: Zellen-Spanne im 4-Spalten-Raster (1–4 Spalten, 1–2 Zeilen).
    spalten: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    zeilen: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    eintrag: Mapped["NewsletterEintrag"] = relationship("NewsletterEintrag", back_populates="bilder")
