"""Auslieferung gespeicherter Nutzerdateien (Befund 13 und 15).

Zwei Dinge gingen hier schief:

  * Hochgeladene Dateien wurden ``inline`` ausgeliefert, mit dem MIME-Typ,
    den die Datenbank zu ihnen gespeichert hatte — also dem, den der
    Hochladende bestimmt hat. Eine als ``text/html`` abgelegte Datei lief
    damit im Ursprung der Anwendung, mit Zugriff auf die Sitzung jedes
    Betrachters. SVG genügt dafür auch.
  * Der Dateiname ging ungefiltert in die ``Content-Disposition``.

Die Regel hier: nur Typen, die nichts ausführen können, dürfen ``inline``
und behalten ihren MIME-Typ. Alles andere geht als ``application/
octet-stream`` in den Anhang. ``nosniff`` kommt immer mit — damit hilft
auch ein gefälschter Typ nicht weiter: der Browser rät nicht nach.

Keine Prüfung der magischen Bytes: ``nosniff`` und die Typ-Liste nehmen
ihr die Arbeit ab. Wer eine HTML-Seite als ``application/pdf`` ablegt,
bekommt sie als PDF ausgeliefert, das der Betrachter nicht öffnen kann —
ausgeführt wird sie nicht.
"""
from __future__ import annotations

import re
from urllib.parse import quote

# Typen, die im Ursprung der Anwendung nichts ausführen können. Bewusst
# ohne image/svg+xml: SVG darf Skripte enthalten.
INLINE_ERLAUBT = frozenset({
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
})

_UNERWUENSCHT = re.compile(r'[^A-Za-z0-9 ._-]')


def sicherer_dateiname(name: str | None, *, ersatz: str = "datei") -> str:
    """Ein Dateiname, der in eine Kopfzeile darf.

    Alles außer Buchstaben, Ziffern, Leerzeichen, Punkt, Unterstrich und
    Bindestrich wird zu einem Unterstrich — damit sind Anführungszeichen,
    Schrägstriche und vor allem Zeilenumbrüche erledigt. Umlaute gehen
    dabei verloren; sie kommen über ``filename*`` unversehrt mit.
    """
    if not name:
        return ersatz
    sauber = _UNERWUENSCHT.sub("_", name).strip(" .")
    return sauber or ersatz


def _mime(roh: str | None) -> str:
    typ = (roh or "").split(";")[0].strip().lower()
    # Kein echter Typ, aber verbreitet — sonst fiele ein JPEG in den Anhang.
    return "image/jpeg" if typ == "image/jpg" else typ


def auslieferung(
    dateiname: str | None,
    mime: str | None,
    *,
    inline: bool = True,
    ersatz: str = "datei",
) -> tuple[str, dict[str, str]]:
    """``(media_type, headers)`` für eine gespeicherte Nutzerdatei.

    ``inline=False`` erzwingt den Anhang auch für einen harmlosen Typ.
    """
    typ = _mime(mime)
    darf_inline = inline and typ in INLINE_ERLAUBT
    media_type = typ if typ in INLINE_ERLAUBT else "application/octet-stream"

    ascii_name = sicherer_dateiname(dateiname, ersatz=ersatz)
    disposition = "inline" if darf_inline else "attachment"
    kopfzeile = f'{disposition}; filename="{ascii_name}"'
    if dateiname and dateiname != ascii_name:
        kopfzeile += f"; filename*=UTF-8''{quote(dateiname, safe='')}"

    return media_type, {
        "Content-Disposition": kopfzeile,
        "X-Content-Type-Options": "nosniff",
    }
