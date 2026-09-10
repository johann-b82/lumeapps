"""Grenzen für hochgeladene Daten (Befund 10 der Sicherheitsanalyse).

Zwei Größen, zwei Angriffe:

  * ``MAX_REQUEST_BYTES`` deckelt den Rumpf einer Anfrage, bevor Starlette
    ihn in den Speicher liest. Caddy hat vorne dieselbe Grenze; die hier
    greift, wenn jemand die api direkt anspricht.
  * ``pruefe_archivgroesse`` deckelt, was beim Entpacken daraus wird. xlsx,
    docx und pptx sind ZIP-Archive: 200 KB gepackter Nullen werden zu
    200 MB, sobald openpyxl das Blatt liest — gemessen, kein Schätzwert.
    Das Inhaltsverzeichnis des Archivs nennt die entpackten Größen, ohne
    dass ein Byte entpackt werden muss, und ``zipfile`` gibt auch nie mehr
    heraus als dort steht. Die Prüfung kostet also nichts.

Kein ``defusedxml``: openpyxl liegt hier auf lxml (``openpyxl.xml.LXML``
ist True) und baut seinen Parser mit ``resolve_entities=False``; lxml lädt
externe DTDs von sich aus nicht. ``defuse_stdlib()`` würde nur die
stdlib-ElementTree flicken, die gar nicht benutzt wird.
"""
from __future__ import annotations

import io
import json
import zipfile

from fastapi import HTTPException

# Größte Nutzlast, die ein Weg im Haus wirklich braucht: die 50 MB der
# Signage-PPTX (services/directus_uploads.py) plus Luft für den
# multipart-Rahmen.
MAX_REQUEST_BYTES = 64 * 1024 * 1024

# Entpackt darf daraus das Vierfache werden. Eine echte Arbeitsmappe mit
# 100.000 Zeilen bleibt weit darunter.
MAX_ENTPACKT_BYTES = 256 * 1024 * 1024


def pruefe_archivgroesse(daten: bytes, *, grenze: int = MAX_ENTPACKT_BYTES) -> None:
    """413, wenn das ZIP entpackt größer wäre als ``grenze``.

    Keine Datei? Kein ZIP? Dann ist nichts zu prüfen — CSV und TXT gehen
    hier unbehelligt durch.
    """
    try:
        archiv = zipfile.ZipFile(io.BytesIO(daten))
        entpackt = sum(eintrag.file_size for eintrag in archiv.infolist())
    except (zipfile.BadZipFile, OSError):
        return
    if entpackt > grenze:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Archiv entpackt {entpackt // (1024 * 1024)} MB — "
                f"erlaubt sind {grenze // (1024 * 1024)} MB."
            ),
        )


class _ZuGross(Exception):
    """Signal aus dem receive-Kanal an ``BodySizeLimitMiddleware``."""


def _content_length(scope) -> int | None:
    for name, wert in scope.get("headers", ()):
        if name == b"content-length":
            try:
                return int(wert)
            except ValueError:
                return None
    return None


async def _antwort_413(send, grenze: int) -> None:
    rumpf = json.dumps(
        {"detail": f"Anfrage größer als {grenze // (1024 * 1024)} MB."}
    ).encode()
    await send({
        "type": "http.response.start",
        "status": 413,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(rumpf)).encode()),
        ],
    })
    await send({"type": "http.response.body", "body": rumpf})


class BodySizeLimitMiddleware:
    """Weist zu große Anfragerümpfe ab, bevor sie im Speicher landen.

    Reines ASGI statt ``BaseHTTPMiddleware``: letztere puffert Antworten und
    würde die Player-Streams kappen (SSE-Invariante).
    """

    def __init__(self, app, *, max_bytes: int = MAX_REQUEST_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        angekuendigt = _content_length(scope)
        if angekuendigt is not None and angekuendigt > self.max_bytes:
            await _antwort_413(send, self.max_bytes)
            return

        gesamt = 0
        antwort_begonnen = False

        async def zaehlendes_receive():
            nonlocal gesamt
            nachricht = await receive()
            if nachricht["type"] == "http.request":
                gesamt += len(nachricht.get("body", b""))
                if gesamt > self.max_bytes:
                    raise _ZuGross
            return nachricht

        async def merkendes_send(nachricht) -> None:
            nonlocal antwort_begonnen
            if nachricht["type"] == "http.response.start":
                antwort_begonnen = True
            await send(nachricht)

        try:
            await self.app(scope, zaehlendes_receive, merkendes_send)
        except _ZuGross:
            if not antwort_begonnen:
                await _antwort_413(send, self.max_bytes)
