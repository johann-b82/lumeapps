"""Produktions-Priorisierung router (v1.126, admin-only).

Eigenständiges Modul unter Produktion. Der gesamte Router ist admin-gated,
wie das übrige Produktion-Hub (Wartung). Routes:

    GET    /api/production/prio/status                    Import-Stand + Listen
    POST   /api/production/prio/import/artikelstamm       AswStm.txt ersetzen
    POST   /api/production/prio/import/ressourcenplan     RESSOURCENPLAN ersetzen
    POST   /api/production/prio/import/auftraege          AswKpf.txt ersetzen
    POST   /api/production/prio/import/liste              Prioliste anlegen (Diehl)
    DELETE /api/production/prio/listen/{liste_id}         Prioliste löschen
    GET    /api/production/prio/gesamt                    Gesamtpriorisierung je BA (+ Positionen)
    PUT    /api/production/prio/manuell                   manuelle BA-Reihenfolge speichern
    DELETE /api/production/prio/manuell                   manuelle BA-Reihenfolge verwerfen
    GET    /api/production/prio/bereiche                  Bereiche + Anzahl Tätigkeiten
    GET    /api/production/prio/bereiche/{bereich}        Tätigkeitsliste eines Bereichs
    GET    /api/production/prio/bereiche/{bereich}/export.xlsx

Compute-justified: clause 1 (file parsing) — die Import-Routen lesen Apollo-
Exporte und die Kunden-Prioliste serverseitig; clause 3 (multi-row atomic
compute) — Importe ersetzen Tabellen in einer Transaktion, die Gesamtliste
verschmilzt Listen, Termine und manuelle Reihenfolge, die Bereichslisten lösen
jede Position rekursiv über die Stückliste auf; clause 2 (document generation)
— der Excel-Export.
"""
from __future__ import annotations

import asyncio
from datetime import date, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import (
    PrioArtikel,
    PrioAuftragPosition,
    PrioImport,
    PrioListe,
    PrioListeEintrag,
    PrioManuell,
    PrioPlanPosition,
)
from app.parsing.produktion_prio_parser import (
    Ergebnis,
    parse_artikelstamm,
    parse_auftraege,
    parse_diehl_prioliste,
    parse_ressourcenplan,
)
from app.security.directus_auth import get_current_user, require_admin
from app.services.produktion_prio import (
    BEREICH_LABEL,
    BEREICHE,
    bereich_xlsx,
    lade_bereiche,
    lade_gesamtliste,
)

router = APIRouter(
    prefix="/api/production/prio",
    tags=["produktion-prio"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)

_BLOCK = 5000


class ImportStand(BaseModel):
    quelle: str
    dateiname: str | None
    zeilen: int
    warnungen: int
    importiert_am: datetime


class ListeRead(BaseModel):
    id: int
    name: str
    typ: str
    stand: date
    dateiname: str | None
    importiert_am: datetime
    eintraege: int
    mit_rang: int


class StatusRead(BaseModel):
    importe: list[ImportStand]
    listen: list[ListeRead]


class ImportErgebnisRead(BaseModel):
    zeilen: int
    warnungen: list[str]
    warnungen_anzahl: int


class PositionRead(BaseModel):
    pos: int
    upos: int
    artikelnr: str | None
    bezeichnung: str | None
    menge: Decimal | None
    einheit: str | None
    lieferdatum: date | None
    termin: date | None
    liste: str | None
    listen_rang: int | None
    kommentar: str | None
    gesperrt: bool
    ohne_plan: bool


class BaRead(BaseModel):
    rang: int
    vorgang_nr: str
    kunde: str | None
    termin: date | None
    listen_rang: int | None
    gesperrt: bool
    manuell: bool
    positionen: list[PositionRead]


class ManuellIn(BaseModel):
    #: BA-Nummern in der gewünschten Reihenfolge.
    reihenfolge: list[str]


class BereichRead(BaseModel):
    key: str
    label: str
    taetigkeiten: int
    minuten: Decimal


class BereichsZeileRead(BaseModel):
    prio: int
    vorgang_nr: str
    pos: int
    upos: int
    termin: date | None
    kunde: str | None
    endartikel: str | None
    endartikel_bez: str | None
    ebene: int
    pfad: str
    artikelnr: str
    artikel_bez: str | None
    ressource: str
    kostenstelle: str | None
    taetigkeit: str | None
    menge: Decimal
    minuten: Decimal
    gesperrt: bool
    kommentar: str | None


async def _lies(file: UploadFile, endungen: tuple[str, ...]) -> tuple[bytes, str]:
    name = file.filename or "unbenannt"
    if not name.lower().endswith(endungen):
        raise HTTPException(status_code=400, detail=f"Bitte eine {'/'.join(endungen)}-Datei hochladen.")
    return await file.read(), name


async def _parse(fn, *args):
    try:
        return await asyncio.to_thread(fn, *args)
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # defekte Dateien werfen je nach Stelle sehr unterschiedlich
        raise HTTPException(status_code=400, detail=f"Datei konnte nicht gelesen werden: {exc}") from exc


async def _ersetze(db: AsyncSession, modell, erg: Ergebnis, quelle: str, dateiname: str) -> ImportErgebnisRead:
    if not erg.zeilen:
        raise HTTPException(status_code=400, detail="Die Datei enthält keine übernehmbaren Zeilen.")
    await db.execute(delete(modell))
    for i in range(0, len(erg.zeilen), _BLOCK):
        await db.execute(insert(modell), erg.zeilen[i:i + _BLOCK])
    await db.execute(delete(PrioImport).where(PrioImport.quelle == quelle))
    db.add(PrioImport(quelle=quelle, dateiname=dateiname[:255], zeilen=len(erg.zeilen),
                      warnungen=erg.warnungen_anzahl))
    await db.commit()
    return ImportErgebnisRead(zeilen=len(erg.zeilen), warnungen=erg.warnungen,
                              warnungen_anzahl=erg.warnungen_anzahl)


@router.get("/status", response_model=StatusRead)
async def status(db: AsyncSession = Depends(get_async_db_session)) -> StatusRead:
    importe = (await db.execute(select(PrioImport).order_by(PrioImport.quelle))).scalars().all()
    zaehler = (
        select(
            PrioListeEintrag.liste_id,
            func.count().label("n"),
            func.count(PrioListeEintrag.rang).label("mit_rang"),
        )
        .group_by(PrioListeEintrag.liste_id)
        .subquery()
    )
    rows = await db.execute(
        select(PrioListe, zaehler.c.n, zaehler.c.mit_rang)
        .outerjoin(zaehler, zaehler.c.liste_id == PrioListe.id)
        .order_by(PrioListe.stand.desc(), PrioListe.id.desc())
    )
    listen = [
        ListeRead(id=l.id, name=l.name, typ=l.typ, stand=l.stand, dateiname=l.dateiname,
                  importiert_am=l.importiert_am, eintraege=n or 0, mit_rang=mr or 0)
        for l, n, mr in rows.all()
    ]
    return StatusRead(importe=[ImportStand.model_validate(i, from_attributes=True) for i in importe],
                      listen=listen)


@router.post("/import/artikelstamm", response_model=ImportErgebnisRead)
async def import_artikelstamm(
    file: UploadFile = File(...), db: AsyncSession = Depends(get_async_db_session)
) -> ImportErgebnisRead:
    daten, name = await _lies(file, (".txt", ".csv"))
    erg = await _parse(parse_artikelstamm, daten)
    return await _ersetze(db, PrioArtikel, erg, "artikelstamm", name)


@router.post("/import/ressourcenplan", response_model=ImportErgebnisRead)
async def import_ressourcenplan(
    file: UploadFile = File(...), db: AsyncSession = Depends(get_async_db_session)
) -> ImportErgebnisRead:
    daten, name = await _lies(file, (".txt", ".csv"))
    erg = await _parse(parse_ressourcenplan, daten)
    return await _ersetze(db, PrioPlanPosition, erg, "ressourcenplan", name)


@router.post("/import/auftraege", response_model=ImportErgebnisRead)
async def import_auftraege(
    file: UploadFile = File(...), db: AsyncSession = Depends(get_async_db_session)
) -> ImportErgebnisRead:
    daten, name = await _lies(file, (".txt", ".csv"))
    erg = await _parse(parse_auftraege, daten, name)
    return await _ersetze(db, PrioAuftragPosition, erg, "auftraege", name)


@router.post("/import/liste", response_model=ImportErgebnisRead)
async def import_liste(
    file: UploadFile = File(...),
    typ: str = Form("diehl"),
    stand: date | None = Form(None),
    db: AsyncSession = Depends(get_async_db_session),
) -> ImportErgebnisRead:
    if typ != "diehl":
        raise HTTPException(status_code=400, detail="Unbekannter Listentyp.")
    daten, name = await _lies(file, (".xlsx", ".xlsm"))
    erg = await _parse(parse_diehl_prioliste, daten, name)
    if not erg.zeilen:
        raise HTTPException(status_code=400, detail="Die Liste enthält keine zuordenbaren Positionen.")
    liste = PrioListe(name="Diehl", typ=typ, stand=stand or erg.stand or date.today(), dateiname=name[:255])
    db.add(liste)
    await db.flush()
    for i in range(0, len(erg.zeilen), _BLOCK):
        await db.execute(insert(PrioListeEintrag), [{**z, "liste_id": liste.id} for z in erg.zeilen[i:i + _BLOCK]])
    await db.commit()
    return ImportErgebnisRead(zeilen=len(erg.zeilen), warnungen=erg.warnungen,
                              warnungen_anzahl=erg.warnungen_anzahl)


@router.delete("/listen/{liste_id}", status_code=204)
async def delete_liste(liste_id: int, db: AsyncSession = Depends(get_async_db_session)) -> Response:
    liste = await db.get(PrioListe, liste_id)
    if liste is None:
        raise HTTPException(status_code=404, detail="Liste nicht gefunden.")
    await db.delete(liste)
    await db.commit()
    return Response(status_code=204)


@router.get("/gesamt", response_model=list[BaRead])
async def gesamt(db: AsyncSession = Depends(get_async_db_session)) -> list[BaRead]:
    return [BaRead.model_validate(z, from_attributes=True) for z in await lade_gesamtliste(db)]


@router.put("/manuell", status_code=204)
async def save_manuell(payload: ManuellIn, db: AsyncSession = Depends(get_async_db_session)) -> Response:
    bas = [b.strip()[:32] for b in payload.reihenfolge]
    if len(set(bas)) != len(bas) or not all(bas):
        raise HTTPException(status_code=400, detail="BA leer oder doppelt in der Reihenfolge.")
    await db.execute(delete(PrioManuell))
    werte = [{"vorgang_nr": v, "reihenfolge": i} for i, v in enumerate(bas)]
    for i in range(0, len(werte), _BLOCK):
        await db.execute(insert(PrioManuell), werte[i:i + _BLOCK])
    await db.commit()
    return Response(status_code=204)


@router.delete("/manuell", status_code=204)
async def reset_manuell(db: AsyncSession = Depends(get_async_db_session)) -> Response:
    await db.execute(delete(PrioManuell))
    await db.commit()
    return Response(status_code=204)


@router.get("/bereiche", response_model=list[BereichRead])
async def bereiche(db: AsyncSession = Depends(get_async_db_session)) -> list[BereichRead]:
    daten = await lade_bereiche(db)
    return [
        BereichRead(key=key, label=label, taetigkeiten=len(daten.zeilen[key]),
                    minuten=sum((z.minuten for z in daten.zeilen[key]), Decimal(0)))
        for key, label, _ in BEREICHE
    ]


def _pruefe_bereich(bereich: str) -> str:
    if bereich not in BEREICH_LABEL:
        raise HTTPException(status_code=404, detail="Unbekannter Bereich.")
    return bereich


@router.get("/bereiche/{bereich}", response_model=list[BereichsZeileRead])
async def bereich_liste(bereich: str, db: AsyncSession = Depends(get_async_db_session)) -> list[BereichsZeileRead]:
    daten = await lade_bereiche(db, nur=_pruefe_bereich(bereich))
    return [BereichsZeileRead.model_validate(z, from_attributes=True) for z in daten.zeilen[bereich]]


@router.get("/bereiche/{bereich}/export.xlsx")
async def bereich_export(bereich: str, db: AsyncSession = Depends(get_async_db_session)) -> Response:
    daten = await lade_bereiche(db, nur=_pruefe_bereich(bereich))
    label = BEREICH_LABEL[bereich]
    inhalt = await asyncio.to_thread(bereich_xlsx, label, daten.zeilen[bereich])
    return Response(
        content=inhalt,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="Prioliste_{bereich}_{date.today():%Y-%m-%d}.xlsx"'},
    )
