"""Einarbeitungs-Zeilen für einen Satz Abteilungen zusammenstellen.

Geteilt vom Einarbeitungsbogen und vom Onboarding-Paket, damit beide dieselbe
Katalog+Matrix-Logik nutzen.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import EinarbeitungKatalog, EinarbeitungPflicht
from app.services.einarbeitung_pdf import EinarbeitungZeile


async def zeilen_fuer_abteilungen(
    db: AsyncSession, abteilungen: list[str]
) -> list[EinarbeitungZeile]:
    """Einarbeitungsinhalte, die für die gegebenen Abteilungen nötig sind."""
    gewaehlt = [a.strip() for a in abteilungen if a and a.strip()]
    if not gewaehlt:
        return []
    rows = (
        await db.execute(
            select(EinarbeitungKatalog, EinarbeitungPflicht.abteilung)
            .join(
                EinarbeitungPflicht,
                EinarbeitungPflicht.einarbeitung_id == EinarbeitungKatalog.id,
            )
            .where(EinarbeitungPflicht.abteilung.in_(gewaehlt))
            .order_by(EinarbeitungPflicht.abteilung, EinarbeitungKatalog.reihenfolge)
        )
    ).all()
    return [
        EinarbeitungZeile(
            # v1.103: eigener Bereich der Einarbeitung; leer → Matrix-Abteilung (alt).
            abteilung=(k.bereich or "").strip() or abt,
            inhalt=k.inhalt,
            ansprechpartner=k.ansprechpartner or "",
        )
        for k, abt in rows
    ]
