"""Befund 4: der session-lose Kiosk-Embed gibt nur her, was das Board malt.

Drei Kontrollen werden hier festgeschrieben:
  1. Die Antwort trägt kein Geburtsdatum und kein Alter — die Karte zeigt
     Wochentag und Tag/Monat, mehr nicht.
  2. Der Foto-Proxy antwortet nur für Personen, die gerade auf einem der
     beiden Boards stehen. Sonst wäre die Personalnummer ein Index durch
     die Belegschaft.
  3. Der Proxy zieht Personio nur einmal je Person und Stunde und ist pro
     IP begrenzt.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import delete, update

from app.database import AsyncSessionLocal
from app.models import AppSettings, PersonioEmployee
from app.routers import hr_embed
from app.security import rate_limit as rl_mod
from app.security.fernet import encrypt_credential
from app.services.personio_client import PersonioClient

pytestmark = pytest.mark.asyncio

_ID_GEBURTSTAG = 9_610_001
_ID_NEUZUGANG = 9_610_002
_ID_UNSICHTBAR = 9_610_003
_ALLE = (_ID_GEBURTSTAG, _ID_NEUZUGANG, _ID_UNSICHTBAR)


@pytest.fixture(autouse=True)
def _frischer_zustand():
    rl_mod._reset_for_tests()
    hr_embed._reset_foto_cache_for_tests()
    yield
    rl_mod._reset_for_tests()
    hr_embed._reset_foto_cache_for_tests()


def _raw(geburtstag: date | None) -> dict:
    attribute: dict = {"profile_picture": {"label": "Profile Picture", "value": "https://x/y.jpg"}}
    if geburtstag is not None:
        attribute["birthday"] = {"label": "Geburtsdatum", "value": geburtstag.isoformat()}
    return {"attributes": attribute}


@pytest.fixture
async def personen():
    """Drei Personen: Geburtstag diese Woche, gestern eingetreten, unsichtbar."""
    heute = date.today()
    montag = heute - timedelta(days=heute.weekday())
    # 100 Tage entfernt — liegt garantiert außerhalb der laufenden Woche.
    fern = heute + timedelta(days=100)
    async with AsyncSessionLocal() as s:
        await s.execute(delete(PersonioEmployee).where(PersonioEmployee.id.in_(_ALLE)))
        s.add(PersonioEmployee(
            id=_ID_GEBURTSTAG, first_name="Geb", last_name="Urtstag",
            department="Fertigung", status="active",
            hire_date=date(2015, 1, 1), termination_date=None,
            raw_json=_raw(date(1980, montag.month, montag.day)),
            synced_at=datetime.now(timezone.utc),
        ))
        s.add(PersonioEmployee(
            id=_ID_NEUZUGANG, first_name="Neu", last_name="Zugang",
            department="Einkauf", status="active",
            hire_date=heute - timedelta(days=1), termination_date=None,
            raw_json=_raw(None),
            synced_at=datetime.now(timezone.utc),
        ))
        s.add(PersonioEmployee(
            id=_ID_UNSICHTBAR, first_name="Un", last_name="Sichtbar",
            department="Vertrieb", status="active",
            hire_date=date(2015, 6, 1), termination_date=None,
            raw_json=_raw(fern.replace(year=1980)),
            synced_at=datetime.now(timezone.utc),
        ))
        await s.commit()
    yield
    async with AsyncSessionLocal() as s:
        await s.execute(delete(PersonioEmployee).where(PersonioEmployee.id.in_(_ALLE)))
        await s.commit()


async def _personio_konfigurieren():
    async with AsyncSessionLocal() as s:
        await s.execute(
            update(AppSettings).where(AppSettings.id == 1).values(
                personio_client_id_enc=encrypt_credential("id"),
                personio_client_secret_enc=encrypt_credential("secret"),
            )
        )
        await s.commit()


# --- 1. Datenminimierung -----------------------------------------------------


async def test_geburtstage_ohne_geburtsdatum_und_alter(client, personen):
    r = await client.get("/api/hr/embed/birthdays/this-week")
    assert r.status_code == 200
    eintraege = r.json()
    meiner = [e for e in eintraege if e["employee_id"] == _ID_GEBURTSTAG]
    assert len(meiner) == 1, "Geburtstagskind der laufenden Woche fehlt"
    for e in eintraege:
        assert "birthday" not in e
        assert "age_turning" not in e
    assert set(meiner[0]) == {
        "employee_id", "first_name", "last_name", "department",
        "weekday", "occurs_on", "has_photo",
    }


async def test_authentifizierte_route_behaelt_geburtsdatum(admin_client, personen):
    """Gegenprobe: die gesicherte Route ist unverändert, nur der Embed ist schmaler."""
    r = await admin_client.get("/api/hr/birthdays/this-week")
    assert r.status_code == 200
    meiner = [e for e in r.json() if e["employee_id"] == _ID_GEBURTSTAG]
    assert len(meiner) == 1
    assert meiner[0]["birthday"].startswith("1980-")
    assert meiner[0]["age_turning"] == date.today().year - 1980


# --- 2. Kein Durchzählen der Belegschaft ------------------------------------


async def test_foto_nur_fuer_gezeigte_personen(client, personen, monkeypatch):
    await _personio_konfigurieren()
    gerufen: list[int] = []

    async def _fake(self, employee_id: int):
        gerufen.append(employee_id)
        return b"JPEGBYTES", "image/jpeg"

    monkeypatch.setattr(PersonioClient, "fetch_profile_picture", _fake)

    for eid in (_ID_GEBURTSTAG, _ID_NEUZUGANG):
        r = await client.get(f"/api/hr/embed/employees/{eid}/photo")
        assert r.status_code == 200, eid
        assert r.content == b"JPEGBYTES"

    r = await client.get(f"/api/hr/embed/employees/{_ID_UNSICHTBAR}/photo")
    assert r.status_code == 404
    assert _ID_UNSICHTBAR not in gerufen, "Personio wurde trotz 404 befragt"


async def test_unbekannte_id_und_unsichtbare_id_nicht_unterscheidbar(client, personen):
    await _personio_konfigurieren()
    a = await client.get(f"/api/hr/embed/employees/{_ID_UNSICHTBAR}/photo")
    b = await client.get("/api/hr/embed/employees/98765432/photo")
    assert a.status_code == b.status_code == 404
    assert a.json() == b.json()


# --- 3. Zwischenspeicher und Begrenzung -------------------------------------


async def test_foto_wird_zwischengespeichert(client, personen, monkeypatch):
    await _personio_konfigurieren()
    gerufen: list[int] = []

    async def _fake(self, employee_id: int):
        gerufen.append(employee_id)
        return b"JPEGBYTES", "image/jpeg"

    monkeypatch.setattr(PersonioClient, "fetch_profile_picture", _fake)

    for _ in range(3):
        r = await client.get(f"/api/hr/embed/employees/{_ID_GEBURTSTAG}/photo")
        assert r.status_code == 200
    assert gerufen == [_ID_GEBURTSTAG], "Personio je Aufruf statt einmal befragt"


async def test_foto_proxy_ist_pro_ip_begrenzt(client, personen):
    grenze = rl_mod.rate_limit_embed_photo.limit
    for _ in range(grenze):
        r = await client.get(f"/api/hr/embed/employees/{_ID_UNSICHTBAR}/photo")
        assert r.status_code == 404
    r = await client.get(f"/api/hr/embed/employees/{_ID_UNSICHTBAR}/photo")
    assert r.status_code == 429
    assert r.headers["Retry-After"] == "60"
