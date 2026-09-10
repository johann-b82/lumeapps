"""Befund 9: eine Cookie-Sitzung darf nicht von einer fremden Seite aus wirken.

Die Sitzung steckt in ``directus_session_token``. Ein Browser schickt dieses
Cookie an diesen Ursprung, gleich wer die Anfrage ausgelöst hat. Verändernde
Anfragen brauchen deshalb zusätzlich ``X-LumeApps-Request`` — eine Kopfzeile,
die ein Formular auf einer fremden Seite nicht setzen kann.

Wer sich mit ``Authorization`` ausweist, ist nicht betroffen: dieses Token
schickt kein Browser von allein mit.
"""
from __future__ import annotations

import pytest

from tests._auth import ADMIN_UUID, mint

pytestmark = pytest.mark.asyncio

# Ein admin-gesicherter Schreibweg. Die Nutzlast darf ruhig unvollständig
# sein: geprüft wird, ob die Anfrage überhaupt bis zur Prüfung durchkommt.
_WEG = "/api/settings"
_NUTZLAST: dict = {}


def _cookie() -> dict[str, str]:
    return {"directus_session_token": mint(ADMIN_UUID)}


async def test_cookie_ohne_kopfzeile_wird_abgewiesen(client):
    r = await client.put(_WEG, json=_NUTZLAST, cookies=_cookie())
    assert r.status_code == 403
    assert "x-lumeapps-request" in r.json()["detail"]


async def test_cookie_mit_kopfzeile_geht_durch(client):
    r = await client.put(
        _WEG,
        json=_NUTZLAST,
        cookies=_cookie(),
        headers={"X-LumeApps-Request": "1"},
    )
    # 422 (unvollständige Nutzlast) ist recht — die Sicherung war nicht im Weg.
    assert r.status_code in (200, 422), r.text


async def test_lesen_braucht_die_kopfzeile_nicht(client):
    """Sonst bräche jeder Bild- und PDF-Weg, den der Browser direkt lädt."""
    r = await client.get(_WEG, cookies=_cookie())
    assert r.status_code == 200


async def test_authorization_kopfzeile_ist_nicht_betroffen(client):
    """Dienste, Pi-Beiwagen und Tests weisen sich per Bearer aus."""
    r = await client.put(
        _WEG, json=_NUTZLAST, headers={"Authorization": f"Bearer {mint(ADMIN_UUID)}"}
    )
    assert r.status_code in (200, 422), r.text


async def test_ohne_jede_anmeldung_bleibt_es_bei_401(client):
    """Die neue Prüfung darf 401 nicht in 403 verwandeln."""
    r = await client.put(_WEG, json=_NUTZLAST)
    assert r.status_code == 401
