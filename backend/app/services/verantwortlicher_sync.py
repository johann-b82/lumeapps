"""Verantwortlicher/Ansprechpartner je Schulungs-Name teilen.

Dieselbe Schulung existiert im Katalog getrennt je Bereich und zusätzlich als
Einarbeitung. Die verantwortliche Person soll je NAME überall gleich sein: einmal
gesetzt, erscheint sie auf allen gleichnamigen Schulungen (alle Bereiche) und der
gleichnamigen Einarbeitung. Abgleich case-insensitiv über den getrimmten Namen.
"""
from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EinarbeitungKatalog, SchulungKatalog


async def sync_person_nach_name(
    db: AsyncSession, name: str, person: str | None
) -> None:
    """Setzt ``person`` auf allen gleichnamigen Schulungen und Einarbeitungen.

    Schreibt NICHT committet — der Aufrufer committet (idempotent, überschreibt
    auch die auslösende Zeile mit demselben Wert).
    """
    ziel = (name or "").strip().lower()
    if not ziel:
        return
    await db.execute(
        update(SchulungKatalog)
        .where(func.lower(func.trim(SchulungKatalog.name)) == ziel)
        .values(verantwortlicher=person)
    )
    await db.execute(
        update(EinarbeitungKatalog)
        .where(func.lower(func.trim(EinarbeitungKatalog.inhalt)) == ziel)
        .values(ansprechpartner=person)
    )


async def sync_turnus_nach_name(
    db: AsyncSession, name: str, turnus: str | None, turnus_monate: int | None
) -> None:
    """Setzt Turnus (Text + Monate) auf allen gleichnamigen Schulungen (alle Bereiche)."""
    ziel = (name or "").strip().lower()
    if not ziel:
        return
    await db.execute(
        update(SchulungKatalog)
        .where(func.lower(func.trim(SchulungKatalog.name)) == ziel)
        .values(turnus=turnus, turnus_monate=turnus_monate)
    )


async def sync_beschreibung_nach_name(
    db: AsyncSession, name: str, beschreibung: str | None
) -> None:
    """Setzt die Beschreibung auf allen gleichnamigen Schulungen (alle Bereiche)."""
    ziel = (name or "").strip().lower()
    if not ziel:
        return
    await db.execute(
        update(SchulungKatalog)
        .where(func.lower(func.trim(SchulungKatalog.name)) == ziel)
        .values(beschreibung=beschreibung)
    )


async def sync_frist_nach_name(
    db: AsyncSession, name: str, frist_tage: int | None
) -> None:
    """Setzt die Frist auf allen gleichnamigen Schulungen (alle Bereiche)."""
    ziel = (name or "").strip().lower()
    if not ziel:
        return
    await db.execute(
        update(SchulungKatalog)
        .where(func.lower(func.trim(SchulungKatalog.name)) == ziel)
        .values(frist_tage=frist_tage)
    )


async def person_fuer_name(db: AsyncSession, name: str) -> str | None:
    """Bereits gesetzte Person zu einem Namen (Schulung bevorzugt, sonst Einarbeitung)."""
    ziel = (name or "").strip().lower()
    if not ziel:
        return None
    p = (
        await db.execute(
            select(SchulungKatalog.verantwortlicher)
            .where(
                func.lower(func.trim(SchulungKatalog.name)) == ziel,
                SchulungKatalog.verantwortlicher.isnot(None),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    if p:
        return p
    return (
        await db.execute(
            select(EinarbeitungKatalog.ansprechpartner)
            .where(
                func.lower(func.trim(EinarbeitungKatalog.inhalt)) == ziel,
                EinarbeitungKatalog.ansprechpartner.isnot(None),
            )
            .limit(1)
        )
    ).scalar_one_or_none()
