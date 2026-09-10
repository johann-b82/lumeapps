"""Befund 10: Grenzen vor pandas/openpyxl.

Zwei Angriffe, zwei Prüfungen:
  * ein zu großer Anfragerumpf wird abgewiesen, bevor Starlette ihn puffert
  * ein Archiv, das entpackt den Speicher sprengen würde, kommt gar nicht
    erst in openpyxl — das Inhaltsverzeichnis verrät die Größe vorher
"""
from __future__ import annotations

import io
import zipfile

import pytest
import pytest_asyncio
from fastapi import FastAPI, Request, UploadFile, File
from httpx import ASGITransport, AsyncClient

from app.security.limits import (
    BodySizeLimitMiddleware,
    MAX_ENTPACKT_BYTES,
    pruefe_archivgroesse,
)

# asyncio_mode = auto (pytest.ini) — async-Tests brauchen keine Markierung.
_GRENZE = 4096


@pytest.fixture
def app():
    a = FastAPI()
    a.add_middleware(BodySizeLimitMiddleware, max_bytes=_GRENZE)

    @a.post("/_test/upload")
    async def hoch(file: UploadFile = File(...)):
        return {"bytes": len(await file.read())}

    @a.post("/_test/roh")
    async def roh(request: Request):
        return {"bytes": len(await request.body())}

    return a


@pytest_asyncio.fixture
async def client(app):
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


# --- Rumpfgrenze -------------------------------------------------------------


async def test_kleiner_rumpf_geht_durch(client):
    r = await client.post("/_test/upload", files={"file": ("a.csv", b"x" * 100)})
    assert r.status_code == 200
    assert r.json()["bytes"] == 100


async def test_angekuendigt_zu_grosser_rumpf_wird_abgewiesen(client):
    r = await client.post("/_test/upload", files={"file": ("a.csv", b"x" * (_GRENZE * 2))})
    assert r.status_code == 413
    assert "MB" in r.json()["detail"]


async def test_zu_grosser_rumpf_ohne_content_length(client):
    """Chunked: die Größe steht erst beim Lesen fest, die Grenze greift trotzdem."""

    async def strom():
        for _ in range(10):
            yield b"y" * 1024

    r = await client.post("/_test/roh", content=strom())
    assert r.status_code == 413


async def test_andere_gerueste_bleiben_unberuehrt(app):
    """Nicht-HTTP-Scopes (lifespan, websocket) laufen ungefiltert durch."""
    from asgi_lifespan import LifespanManager

    async with LifespanManager(app):
        pass  # kommt der Lifespan durch, ist der Scope-Zweig richtig


# --- Archivgrenze ------------------------------------------------------------


def _zip_mit(entpackt: int) -> bytes:
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("gross.bin", b"0" * entpackt)
    return puffer.getvalue()


def test_csv_ist_kein_archiv_und_geht_durch():
    pruefe_archivgroesse(b"Kunde;Umsatz\nMeier;100\n")  # wirft nicht


def test_kaputtes_archiv_geht_durch():
    """Ein defektes ZIP ist nicht unsere Baustelle — der Parser meldet das."""
    pruefe_archivgroesse(b"PK\x03\x04kaputt")


def test_harmloses_archiv_geht_durch():
    pruefe_archivgroesse(_zip_mit(10_000))


def test_dekompressionsbombe_wird_abgewiesen():
    from fastapi import HTTPException

    bombe = _zip_mit(2 * 1024 * 1024)
    # Gemessen: das gepackte Archiv ist Bruchteile davon groß.
    assert len(bombe) < 100_000
    with pytest.raises(HTTPException) as ausnahme:
        pruefe_archivgroesse(bombe, grenze=1024 * 1024)
    assert ausnahme.value.status_code == 413
    assert "2 MB" in ausnahme.value.detail


def test_grenze_hat_einen_vernuenftigen_vorgabewert():
    assert MAX_ENTPACKT_BYTES == 256 * 1024 * 1024
