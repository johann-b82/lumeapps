"""Binärdateien ablegen/laden — Directus als Store, mit lokalem Disk-Fallback.

In Produktion ist Directus der Binärspeicher (wie bei den Schulungsübersichten):
Upload nach ``/files`` mit Admin-Token, die zurückgegebene UUID wird persistiert.
Ist kein Directus konfiguriert (z. B. isolierte Test-Umgebung, ``DIRECTUS_URL``
leer), fällt der Helfer transparent auf ein lokales Verzeichnis zurück — so
läuft die gesamte Vorgangs-Funktion auch ohne Directus.
"""
from __future__ import annotations

import os
import uuid as _uuid
from pathlib import Path

import httpx

from app.config import settings

_TIMEOUT_S = 30.0
_LOKAL_DIR = Path(os.environ.get("EA_FILE_DIR", "/app/media/ea_files"))


def _directus_aktiv() -> bool:
    return bool(settings.DIRECTUS_URL and settings.DIRECTUS_ADMIN_TOKEN)


async def datei_speichern(name: str, daten: bytes, mime: str = "application/pdf") -> str:
    """Datei ablegen; gibt die Referenz (Directus-UUID bzw. lokaler Dateiname) zurück."""
    if _directus_aktiv():
        url = f"{settings.DIRECTUS_URL.rstrip('/')}/files"
        headers = {"Authorization": f"Bearer {settings.DIRECTUS_ADMIN_TOKEN}"}
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as http:
            antwort = await http.post(url, headers=headers, files={"file": (name, daten, mime)})
        if antwort.status_code // 100 != 2:
            raise RuntimeError(f"Directus-Upload fehlgeschlagen (HTTP {antwort.status_code})")
        return antwort.json()["data"]["id"]

    _LOKAL_DIR.mkdir(parents=True, exist_ok=True)
    ref = _uuid.uuid4().hex
    (_LOKAL_DIR / ref).write_bytes(daten)
    return ref


async def datei_laden(ref: str) -> bytes:
    """Datei über ihre Referenz laden."""
    if _directus_aktiv():
        url = f"{settings.DIRECTUS_URL.rstrip('/')}/assets/{ref}"
        headers = {"Authorization": f"Bearer {settings.DIRECTUS_ADMIN_TOKEN}"}
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as http:
            antwort = await http.get(url, headers=headers)
        antwort.raise_for_status()
        return antwort.content

    pfad = _LOKAL_DIR / ref
    if not pfad.exists():
        raise FileNotFoundError(ref)
    return pfad.read_bytes()
