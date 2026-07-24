"""Firmenlogo für die generierten PDFs (v1.92).

Quelle ist das in den Einstellungen hinterlegte App-Logo (app_settings.logo_data)
— dasselbe Logo, das die Oberfläche brandet. Eine einzige Stelle, an der es
gepflegt wird.

Nur Rasterformate (PNG/JPEG) lassen sich mit openpyxl einbetten; ein als SVG
hochgeladenes Logo wird übersprungen (der Rest des Blatts entsteht trotzdem).
Deshalb: für die Dokumente ein PNG hochladen.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from io import BytesIO

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AppSettings

log = logging.getLogger(__name__)

_RASTER_MIMES = {"image/png", "image/jpeg", "image/jpg"}

#: Zielbreite des Logos auf dem Blatt in Pixeln; die Höhe folgt dem
#: Seitenverhältnis. ~45 mm bei 96 dpi.
LOGO_BREITE_PX = 170


@dataclass
class LogoBild:
    daten: bytes
    breite: int
    hoehe: int


async def lade_logo(db: AsyncSession) -> LogoBild | None:
    """Das App-Logo als einbettbares Bild, oder None.

    None, wenn kein Logo hinterlegt ist oder es kein Rasterformat ist — die
    PDF-Erzeugung läuft dann ohne Logo weiter, statt zu scheitern.
    """
    row = (
        await db.execute(
            select(AppSettings.logo_data, AppSettings.logo_mime).where(
                AppSettings.id == 1
            )
        )
    ).first()
    if row is None:
        return None
    daten, mime = row
    if not daten:
        return None
    if (mime or "").lower() not in _RASTER_MIMES:
        log.info("Logo für PDF übersprungen: MIME %r ist kein Rasterformat.", mime)
        return None

    # Pillow ist zur Laufzeit da (openpyxl braucht es ohnehin zum Einbetten);
    # der Import steht hier lokal, damit das Modul auch ohne Pillow importierbar
    # bleibt.
    from PIL import Image as PILImage

    try:
        with PILImage.open(BytesIO(daten)) as bild:
            w, h = bild.size
    except Exception as exc:  # defekte Datei soll das PDF nicht kippen
        log.warning("Logo für PDF nicht lesbar: %s", exc)
        return None
    if not w or not h:
        return None

    hoehe = max(1, round(LOGO_BREITE_PX * h / w))
    return LogoBild(daten=daten, breite=LOGO_BREITE_PX, hoehe=hoehe)


def bild_einsetzen(ws, logo: LogoBild | None, anker: str) -> None:
    """Logo an der Ankerzelle einsetzen (No-op, wenn kein Logo)."""
    if logo is None:
        return
    from openpyxl.drawing.image import Image as XLImage

    img = XLImage(BytesIO(logo.daten))
    img.width = logo.breite
    img.height = logo.hoehe
    ws.add_image(img, anker)
