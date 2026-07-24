"""Automatische Schulungsübersicht für neue Mitarbeiter (v1.91).

Läuft nach jedem Personio-Abgleich: für jeden neuen Eintritt wird aus Abteilung
und Position der Soll-Schulungsplan abgeleitet, daraus Formblatt 71 als PDF
erzeugt und in Directus abgelegt.

Zwei Regeln halten den Bestand sauber:

* **Kein leeres Blatt.** Ohne passende Regel in der Anforderungsmatrix wäre das
  PDF eine Seite mit Kopf und ohne Zeilen. Solche Dokumente werden nicht
  erzeugt — sie hätten keinen Aussagewert und würden nur die Ablage füllen.
  Sobald die Matrix gepflegt ist, entsteht das Dokument beim nächsten Lauf.
* **Ein Dokument je Person.** ``plan_signatur`` ist ein Hash über die Menge der
  Soll-Schulungen. Ändert sich die Matrix oder die Positions-Zuordnung, weicht
  die Signatur ab und das Dokument wird ersetzt statt ein zweites anzulegen.
"""
from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import date, timedelta

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import OnboardingDokument, PersonioEmployee
from app.services.onboarding import schulungsplan
from app.services.pdf_logo import lade_logo
from app.services.schulungsuebersicht_pdf import (
    UebersichtZeile,
    dateiname,
    erzeuge_schulungsuebersicht_pdf,
)

log = logging.getLogger(__name__)

#: Fenster, in dem ein Eintritt als "neu" gilt — deckungsgleich mit der
#: Eintritte-Liste im Onboarding-Router.
NEU_TAGE = 90

_DIRECTUS_TIMEOUT_S = 30.0


@dataclass
class LaufErgebnis:
    """Was ein Durchlauf getan hat — landet im Log und in der Sync-Antwort."""

    geprueft: int = 0
    erzeugt: int = 0
    aktualisiert: int = 0
    uebersprungen_leer: int = 0
    fehler: int = 0


def plan_signatur(schulung_ids: list[int]) -> str:
    """Stabiler Hash über die Menge der Soll-Schulungen.

    Sortiert, damit die Reihenfolge aus der Datenbank keine Rolle spielt.
    """
    roh = ",".join(str(i) for i in sorted(schulung_ids))
    return hashlib.sha256(roh.encode()).hexdigest()


async def _nach_directus(dateiname_: str, pdf: bytes) -> str:
    """PDF in Directus ablegen, gibt die Datei-UUID zurück."""
    url = f"{settings.DIRECTUS_URL.rstrip('/')}/files"
    headers = {"Authorization": f"Bearer {settings.DIRECTUS_ADMIN_TOKEN}"}
    async with httpx.AsyncClient(timeout=_DIRECTUS_TIMEOUT_S) as http:
        antwort = await http.post(
            url,
            headers=headers,
            files={"file": (dateiname_, pdf, "application/pdf")},
        )
    if antwort.status_code // 100 != 2:
        raise RuntimeError(
            f"Directus-Upload fehlgeschlagen (HTTP {antwort.status_code})"
        )
    return antwort.json()["data"]["id"]


async def _aus_directus_loeschen(datei_uuid: str) -> None:
    """Alte Fassung entfernen. Fehler hier dürfen den Lauf nicht abbrechen —
    ein verwaistes Directus-File ist harmloser als ein fehlendes Dokument."""
    url = f"{settings.DIRECTUS_URL.rstrip('/')}/files/{datei_uuid}"
    headers = {"Authorization": f"Bearer {settings.DIRECTUS_ADMIN_TOKEN}"}
    try:
        async with httpx.AsyncClient(timeout=_DIRECTUS_TIMEOUT_S) as http:
            await http.delete(url, headers=headers)
    except httpx.HTTPError as exc:
        log.warning("alte Schulungsübersicht %s nicht löschbar: %s", datei_uuid, exc)


async def dokument_erzeugen(
    db: AsyncSession, employee: PersonioEmployee, vorhanden: OnboardingDokument | None
) -> str | None:
    """Übersicht für eine Person erzeugen bzw. auffrischen.

    Gibt "erzeugt", "aktualisiert", "leer" oder None (unverändert) zurück.
    """
    plan = await schulungsplan(db, employee)
    if not plan.soll:
        return "leer"

    signatur = plan_signatur([s.schulung_id for s in plan.soll])
    if vorhanden is not None and vorhanden.plan_signatur == signatur:
        return None

    pdf = await erzeuge_schulungsuebersicht_pdf(
        name=plan.name,
        funktion=plan.position or "",
        zeilen=[
            UebersichtZeile(
                bezeichnung=f"{s.bereich}: {s.name}" if s.bereich else s.name
            )
            for s in plan.soll
        ],
        logo=await lade_logo(db),
    )
    name = f"{dateiname(plan.name, date.today())}.pdf"
    datei_uuid = await _nach_directus(name, pdf)

    if vorhanden is None:
        db.add(
            OnboardingDokument(
                employee_id=employee.id,
                directus_file_uuid=datei_uuid,
                dateiname=name,
                plan_signatur=signatur,
                schulungen=len(plan.soll),
            )
        )
        return "erzeugt"

    alt = vorhanden.directus_file_uuid
    vorhanden.directus_file_uuid = datei_uuid
    vorhanden.dateiname = name
    vorhanden.plan_signatur = signatur
    vorhanden.schulungen = len(plan.soll)
    await _aus_directus_loeschen(alt)
    return "aktualisiert"


async def uebersichten_erzeugen(db: AsyncSession) -> LaufErgebnis:
    """Für alle neuen Eintritte die Schulungsübersicht anlegen bzw. auffrischen.

    Wird nach dem Personio-Abgleich aufgerufen. Ein Fehler bei einer Person
    beendet den Lauf nicht — die übrigen sollen trotzdem ihr Dokument bekommen.
    """
    ergebnis = LaufErgebnis()
    grenze = date.today() - timedelta(days=NEU_TAGE)

    neue = (
        (
            await db.execute(
                select(PersonioEmployee).where(
                    PersonioEmployee.status == "active",
                    PersonioEmployee.hire_date.isnot(None),
                    PersonioEmployee.hire_date >= grenze,
                )
            )
        )
        .scalars()
        .all()
    )

    bestand = {
        d.employee_id: d
        for d in (await db.execute(select(OnboardingDokument))).scalars().all()
    }

    for emp in neue:
        ergebnis.geprueft += 1
        try:
            was = await dokument_erzeugen(db, emp, bestand.get(emp.id))
        except Exception as exc:  # Directus, LibreOffice, Datenfehler
            ergebnis.fehler += 1
            log.warning("Schulungsübersicht für %s fehlgeschlagen: %s", emp.id, exc)
            continue
        if was == "erzeugt":
            ergebnis.erzeugt += 1
        elif was == "aktualisiert":
            ergebnis.aktualisiert += 1
        elif was == "leer":
            ergebnis.uebersprungen_leer += 1

    await db.commit()
    if ergebnis.uebersprungen_leer:
        log.info(
            "Schulungsübersicht: %s Eintritte ohne Soll übersprungen "
            "(Anforderungsmatrix für ihre Abteilung/Position nicht gepflegt)",
            ergebnis.uebersprungen_leer,
        )
    return ergebnis
