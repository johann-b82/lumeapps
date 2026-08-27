"""Newsletter — vierteljährliche Ausgabe, online + PDF (v1.112).

Gemischt gegated (siehe Konvention in CLAUDE.md): Lesen ist für alle Dashboard-
Rollen (require_dashboard_read) freigegeben, damit die Belegschaft den Newsletter
liest. **Admin-only** (Depends(require_admin)) sind alle schreibenden Routen und
die Entwurfs-Ansicht:
  - GET  /admin                     (Ausgaben inkl. Entwürfe)
  - GET  /admin/{ausgabe_id}        (Ausgabe inkl. Entwurf + Einträge)
  - POST /                          (Ausgabe anlegen)
  - PUT  /{ausgabe_id}              (Titel/Status ändern, veröffentlichen)
  - DELETE /{ausgabe_id}
  - POST /{ausgabe_id}/eintrag      (Eintrag anlegen)
  - PUT  /eintrag/{eintrag_id}      (Eintrag ändern)
  - DELETE /eintrag/{eintrag_id}
  - PUT  /eintrag/{eintrag_id}/bild (Bild hochladen)
  - DELETE /eintrag/{eintrag_id}/bild
  - PUT  /{ausgabe_id}/cover        (Titelbild hochladen)
  - DELETE /{ausgabe_id}/cover
  - PUT  /{ausgabe_id}/rueckseite   (Rückseitenbild hochladen)
  - DELETE /{ausgabe_id}/rueckseite
  - POST /eintrag/{eintrag_id}/bilder        (Puzzle-Bild hinzufügen)
  - PUT  /eintrag/{eintrag_id}/bilder/anordnung (Reihenfolge setzen)
  - PUT  /eintrag-bild/{bild_id}             (Zellen-Spanne ändern)
  - DELETE /eintrag-bild/{bild_id}
Die übrigen GET-Routen (veröffentlichte Ausgaben + Bilder) sind viewer-lesbar.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_async_db_session
from app.models import Newsletter, NewsletterEintrag, NewsletterEintragBild
from app.models.newsletter import NEWSLETTER_RUBRIKEN, NEWSLETTER_STATUS
from app.routers.hr_belegschaft import aggregiere_belegschaft
from app.security.directus_auth import get_current_user, require_admin, require_dashboard_read

router = APIRouter(
    prefix="/api/newsletter",
    tags=["newsletter"],
    dependencies=[Depends(get_current_user), Depends(require_dashboard_read)],
)

_BILD_MIMES = {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}
_MAX_BILD = 8 * 1024 * 1024  # 8 MB


def _jetzt() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------


class AusgabeListItem(BaseModel):
    id: int
    jahr: int
    quartal: int
    titel: str | None
    status: str


class BildRead(BaseModel):
    id: int
    reihenfolge: int
    spalten: int
    zeilen: int


class EintragRead(BaseModel):
    id: int
    rubrik: str
    untertitel: str
    inhalt_md: str
    reihenfolge: int
    hat_bild: bool
    #: Puzzle-Bilder in Reihenfolge (mit Zellen-Spanne).
    bilder: list[BildRead] = []


class AusgabeDetail(BaseModel):
    id: int
    jahr: int
    quartal: int
    titel: str | None
    status: str
    eintraege: list[EintragRead]
    #: Eingefrorener KPI-Stand (Belegschaft) für den „ACM KPIs"-Block; None = ohne.
    kpi_snapshot: dict | None = None
    #: Block-Reihenfolge (Rubrik-Schlüssel + "kpi"); None = Standard.
    block_reihenfolge: list[str] | None = None
    #: Überschriebene Abschnitts-Titel {block_key: titel}; fehlt ein Key → Standard.
    rubrik_titel: dict[str, str] | None = None
    #: Ob ein vollflächiges Titel- bzw. Rückseitenbild hinterlegt ist.
    hat_cover: bool = False
    hat_rueck: bool = False


class AusgabeAnlegen(BaseModel):
    jahr: int
    quartal: int
    titel: str | None = None


class AusgabeAendern(BaseModel):
    titel: str | None = None
    status: str | None = None
    block_reihenfolge: list[str] | None = None
    #: {block_key: titel} — leere/whitespace-Werte entfernen den Override.
    rubrik_titel: dict[str, str] | None = None


class EintragAnlegen(BaseModel):
    rubrik: str
    untertitel: str
    inhalt_md: str = ""


class EintragAendern(BaseModel):
    rubrik: str | None = None
    untertitel: str | None = None
    inhalt_md: str | None = None
    reihenfolge: int | None = None


class BildLayout(BaseModel):
    #: Zellen-Spanne im 4-Spalten-Raster (Spalten 1–4, Zeilen 1–2).
    spalten: int | None = None
    zeilen: int | None = None


class BilderAnordnung(BaseModel):
    #: Bild-IDs in gewünschter Reihenfolge.
    ids: list[int]


# --------------------------------------------------------------------------
# Hilfen
# --------------------------------------------------------------------------


def _list_item(n: Newsletter) -> AusgabeListItem:
    return AusgabeListItem(id=n.id, jahr=n.jahr, quartal=n.quartal, titel=n.titel, status=n.status)


def _bild_read(b: NewsletterEintragBild) -> BildRead:
    return BildRead(id=b.id, reihenfolge=b.reihenfolge, spalten=b.spalten, zeilen=b.zeilen)


def _eintrag_read(e: NewsletterEintrag) -> EintragRead:
    return EintragRead(
        id=e.id,
        rubrik=e.rubrik,
        untertitel=e.untertitel,
        inhalt_md=e.inhalt_md,
        reihenfolge=e.reihenfolge,
        hat_bild=e.bild_data is not None,
        bilder=[_bild_read(b) for b in e.bilder],
    )


def _detail(n: Newsletter) -> AusgabeDetail:
    return AusgabeDetail(
        id=n.id,
        jahr=n.jahr,
        quartal=n.quartal,
        titel=n.titel,
        status=n.status,
        eintraege=[_eintrag_read(e) for e in n.eintraege],
        kpi_snapshot=n.kpi_snapshot,
        block_reihenfolge=n.block_reihenfolge,
        rubrik_titel=n.rubrik_titel,
        hat_cover=n.cover_bild is not None,
        hat_rueck=n.rueck_bild is not None,
    )


async def _hole_ausgabe(db: AsyncSession, ausgabe_id: int) -> Newsletter:
    n = (
        await db.execute(
            select(Newsletter)
            .where(Newsletter.id == ausgabe_id)
            .options(selectinload(Newsletter.eintraege).selectinload(NewsletterEintrag.bilder))
        )
    ).scalar_one_or_none()
    if n is None:
        raise HTTPException(status_code=404, detail="Ausgabe nicht gefunden.")
    return n


async def _hole_eintrag(db: AsyncSession, eintrag_id: int) -> NewsletterEintrag:
    e = await db.get(NewsletterEintrag, eintrag_id)
    if e is None:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden.")
    return e


async def _eintrag_voll(db: AsyncSession, eintrag_id: int) -> NewsletterEintrag:
    """Eintrag inkl. eager-geladener Puzzle-Bilder — für EintragRead-Antworten."""
    e = (
        await db.execute(
            select(NewsletterEintrag)
            .where(NewsletterEintrag.id == eintrag_id)
            .options(selectinload(NewsletterEintrag.bilder))
        )
    ).scalar_one_or_none()
    if e is None:
        raise HTTPException(status_code=404, detail="Eintrag nicht gefunden.")
    return e


async def _hole_eintrag_bild(db: AsyncSession, bild_id: int) -> NewsletterEintragBild:
    b = await db.get(NewsletterEintragBild, bild_id)
    if b is None:
        raise HTTPException(status_code=404, detail="Bild nicht gefunden.")
    return b


async def _hole_newsletter(db: AsyncSession, ausgabe_id: int) -> Newsletter:
    """Nur die Ausgabe-Zeile (ohne Einträge) — für Cover-Bild-Operationen."""
    n = await db.get(Newsletter, ausgabe_id)
    if n is None:
        raise HTTPException(status_code=404, detail="Ausgabe nicht gefunden.")
    return n


async def _lies_bild(datei: UploadFile) -> tuple[bytes, str]:
    mime = (datei.content_type or "").split(";")[0].strip().lower()
    if mime not in _BILD_MIMES:
        raise HTTPException(status_code=400, detail="Nur PNG/JPEG/WebP/GIF erlaubt.")
    daten = await datei.read()
    if len(daten) > _MAX_BILD:
        raise HTTPException(status_code=400, detail="Bild ist größer als 8 MB.")
    return daten, mime


# --------------------------------------------------------------------------
# Viewer: veröffentlichte Ausgaben lesen
# --------------------------------------------------------------------------


@router.get("", response_model=list[AusgabeListItem])
async def liste(db: AsyncSession = Depends(get_async_db_session)) -> list[AusgabeListItem]:
    """Veröffentlichte Ausgaben, neueste zuerst."""
    rows = (
        (
            await db.execute(
                select(Newsletter)
                .where(Newsletter.status == "veroeffentlicht")
                .order_by(Newsletter.jahr.desc(), Newsletter.quartal.desc())
            )
        )
        .scalars()
        .all()
    )
    return [_list_item(n) for n in rows]


@router.get("/rubriken", response_model=list[str])
async def rubriken() -> list[str]:
    """Die festen Rubrik-Schlüssel in Anzeige-Reihenfolge."""
    return list(NEWSLETTER_RUBRIKEN)


@router.get("/eintrag/{eintrag_id}/bild")
async def bild(eintrag_id: int, db: AsyncSession = Depends(get_async_db_session)) -> Response:
    e = await _hole_eintrag(db, eintrag_id)
    if e.bild_data is None:
        raise HTTPException(status_code=404, detail="Kein Bild.")
    return Response(content=e.bild_data, media_type=e.bild_mime or "image/png")


@router.get("/eintrag-bild/{bild_id}")
async def eintrag_bild(bild_id: int, db: AsyncSession = Depends(get_async_db_session)) -> Response:
    """Ein Puzzle-Bild eines Eintrags (inline)."""
    b = await _hole_eintrag_bild(db, bild_id)
    return Response(content=b.bild_data, media_type=b.bild_mime or "image/png")


@router.get("/{ausgabe_id}/cover")
async def cover(ausgabe_id: int, db: AsyncSession = Depends(get_async_db_session)) -> Response:
    n = await _hole_newsletter(db, ausgabe_id)
    if n.cover_bild is None:
        raise HTTPException(status_code=404, detail="Kein Titelbild.")
    return Response(content=n.cover_bild, media_type=n.cover_mime or "image/png")


@router.get("/{ausgabe_id}/rueckseite")
async def rueckseite(ausgabe_id: int, db: AsyncSession = Depends(get_async_db_session)) -> Response:
    n = await _hole_newsletter(db, ausgabe_id)
    if n.rueck_bild is None:
        raise HTTPException(status_code=404, detail="Kein Rückseitenbild.")
    return Response(content=n.rueck_bild, media_type=n.rueck_mime or "image/png")


# --------------------------------------------------------------------------
# Admin: Redaktion (anlegen/bearbeiten/veröffentlichen)
# --------------------------------------------------------------------------


@router.get("/admin", response_model=list[AusgabeListItem], dependencies=[Depends(require_admin)])
async def admin_liste(db: AsyncSession = Depends(get_async_db_session)) -> list[AusgabeListItem]:
    """Alle Ausgaben inkl. Entwürfe."""
    rows = (
        (
            await db.execute(
                select(Newsletter).order_by(
                    Newsletter.jahr.desc(), Newsletter.quartal.desc()
                )
            )
        )
        .scalars()
        .all()
    )
    return [_list_item(n) for n in rows]


@router.get(
    "/admin/{ausgabe_id}", response_model=AusgabeDetail, dependencies=[Depends(require_admin)]
)
async def admin_ausgabe(
    ausgabe_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> AusgabeDetail:
    """Eine Ausgabe (auch Entwurf) mit Einträgen — für die Redaktion."""
    return _detail(await _hole_ausgabe(db, ausgabe_id))


@router.post("", response_model=AusgabeDetail, status_code=201, dependencies=[Depends(require_admin)])
async def anlegen(
    eingabe: AusgabeAnlegen, db: AsyncSession = Depends(get_async_db_session)
) -> AusgabeDetail:
    if eingabe.quartal not in (1, 2, 3, 4):
        raise HTTPException(status_code=400, detail="Quartal muss 1–4 sein.")
    vorhanden = (
        await db.execute(
            select(Newsletter).where(
                Newsletter.jahr == eingabe.jahr, Newsletter.quartal == eingabe.quartal
            )
        )
    ).scalar_one_or_none()
    if vorhanden is not None:
        raise HTTPException(status_code=409, detail="Für dieses Quartal gibt es bereits eine Ausgabe.")
    n = Newsletter(
        jahr=eingabe.jahr,
        quartal=eingabe.quartal,
        titel=(eingabe.titel or "").strip() or None,
        status="entwurf",
        erstellt_am=_jetzt(),
        aktualisiert_am=_jetzt(),
    )
    db.add(n)
    await db.commit()
    return _detail(await _hole_ausgabe(db, n.id))


@router.put("/{ausgabe_id}", response_model=AusgabeDetail, dependencies=[Depends(require_admin)])
async def aendern(
    ausgabe_id: int, eingabe: AusgabeAendern, db: AsyncSession = Depends(get_async_db_session)
) -> AusgabeDetail:
    n = await _hole_ausgabe(db, ausgabe_id)
    if eingabe.titel is not None:
        n.titel = eingabe.titel.strip() or None
    if eingabe.status is not None:
        if eingabe.status not in NEWSLETTER_STATUS:
            raise HTTPException(status_code=400, detail="Unbekannter Status.")
        n.status = eingabe.status
    if eingabe.block_reihenfolge is not None:
        erlaubt = set(NEWSLETTER_RUBRIKEN) | {"kpi"}
        if any(b not in erlaubt for b in eingabe.block_reihenfolge):
            raise HTTPException(status_code=400, detail="Unbekannter Block in der Reihenfolge.")
        n.block_reihenfolge = list(eingabe.block_reihenfolge)
    if eingabe.rubrik_titel is not None:
        erlaubt = set(NEWSLETTER_RUBRIKEN) | {"kpi"}
        if any(k not in erlaubt for k in eingabe.rubrik_titel):
            raise HTTPException(status_code=400, detail="Unbekannter Block-Titel.")
        # Nur nicht-leere Titel als Override behalten; alles leer → kein Override.
        bereinigt = {k: v.strip() for k, v in eingabe.rubrik_titel.items() if v and v.strip()}
        n.rubrik_titel = bereinigt or None
    n.aktualisiert_am = _jetzt()
    await db.commit()
    return _detail(await _hole_ausgabe(db, n.id))


@router.delete("/{ausgabe_id}", status_code=204, dependencies=[Depends(require_admin)])
async def entfernen(ausgabe_id: int, db: AsyncSession = Depends(get_async_db_session)) -> Response:
    n = await _hole_ausgabe(db, ausgabe_id)
    await db.delete(n)
    await db.commit()
    return Response(status_code=204)


@router.post(
    "/{ausgabe_id}/eintrag", response_model=EintragRead, status_code=201,
    dependencies=[Depends(require_admin)],
)
async def eintrag_anlegen(
    ausgabe_id: int, eingabe: EintragAnlegen, db: AsyncSession = Depends(get_async_db_session)
) -> EintragRead:
    await _hole_ausgabe(db, ausgabe_id)
    if eingabe.rubrik not in NEWSLETTER_RUBRIKEN:
        raise HTTPException(status_code=400, detail="Unbekannte Rubrik.")
    if not eingabe.untertitel.strip():
        raise HTTPException(status_code=400, detail="Untertitel ist Pflicht.")
    letzte = (
        await db.execute(
            select(NewsletterEintrag.reihenfolge)
            .where(
                NewsletterEintrag.newsletter_id == ausgabe_id,
                NewsletterEintrag.rubrik == eingabe.rubrik,
            )
            .order_by(NewsletterEintrag.reihenfolge.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    e = NewsletterEintrag(
        newsletter_id=ausgabe_id,
        rubrik=eingabe.rubrik,
        untertitel=eingabe.untertitel.strip(),
        inhalt_md=eingabe.inhalt_md or "",
        reihenfolge=(letzte or 0) + 1,
    )
    db.add(e)
    await db.commit()
    return _eintrag_read(await _eintrag_voll(db, e.id))


@router.put("/eintrag/{eintrag_id}", response_model=EintragRead, dependencies=[Depends(require_admin)])
async def eintrag_aendern(
    eintrag_id: int, eingabe: EintragAendern, db: AsyncSession = Depends(get_async_db_session)
) -> EintragRead:
    e = await _hole_eintrag(db, eintrag_id)
    if eingabe.rubrik is not None:
        if eingabe.rubrik not in NEWSLETTER_RUBRIKEN:
            raise HTTPException(status_code=400, detail="Unbekannte Rubrik.")
        e.rubrik = eingabe.rubrik
    if eingabe.untertitel is not None:
        if not eingabe.untertitel.strip():
            raise HTTPException(status_code=400, detail="Untertitel darf nicht leer sein.")
        e.untertitel = eingabe.untertitel.strip()
    if eingabe.inhalt_md is not None:
        e.inhalt_md = eingabe.inhalt_md
    if eingabe.reihenfolge is not None:
        e.reihenfolge = eingabe.reihenfolge
    await db.commit()
    return _eintrag_read(await _eintrag_voll(db, e.id))


@router.delete("/eintrag/{eintrag_id}", status_code=204, dependencies=[Depends(require_admin)])
async def eintrag_entfernen(
    eintrag_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> Response:
    e = await _hole_eintrag(db, eintrag_id)
    await db.delete(e)
    await db.commit()
    return Response(status_code=204)


@router.put(
    "/eintrag/{eintrag_id}/bild", response_model=EintragRead, dependencies=[Depends(require_admin)]
)
async def bild_hochladen(
    eintrag_id: int,
    datei: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db_session),
) -> EintragRead:
    e = await _hole_eintrag(db, eintrag_id)
    mime = (datei.content_type or "").split(";")[0].strip().lower()
    if mime not in _BILD_MIMES:
        raise HTTPException(status_code=400, detail="Nur PNG/JPEG/WebP/GIF erlaubt.")
    daten = await datei.read()
    if len(daten) > _MAX_BILD:
        raise HTTPException(status_code=400, detail="Bild ist größer als 8 MB.")
    e.bild_data = daten
    e.bild_mime = mime
    await db.commit()
    return _eintrag_read(await _eintrag_voll(db, e.id))


@router.delete(
    "/eintrag/{eintrag_id}/bild", status_code=204, dependencies=[Depends(require_admin)]
)
async def bild_entfernen(
    eintrag_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> Response:
    e = await _hole_eintrag(db, eintrag_id)
    e.bild_data = None
    e.bild_mime = None
    await db.commit()
    return Response(status_code=204)


# -------- Puzzle-Bilder (mehrere Bilder je Eintrag, im Raster) --------


@router.post(
    "/eintrag/{eintrag_id}/bilder", response_model=EintragRead, status_code=201,
    dependencies=[Depends(require_admin)],
)
async def eintrag_bild_hinzufuegen(
    eintrag_id: int,
    datei: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db_session),
) -> EintragRead:
    e = await _eintrag_voll(db, eintrag_id)
    daten, mime = await _lies_bild(datei)
    letzte = max((b.reihenfolge for b in e.bilder), default=-1)
    db.add(
        NewsletterEintragBild(
            eintrag_id=eintrag_id, bild_data=daten, bild_mime=mime, reihenfolge=letzte + 1
        )
    )
    await db.commit()
    return _eintrag_read(await _eintrag_voll(db, eintrag_id))


@router.put(
    "/eintrag/{eintrag_id}/bilder/anordnung", response_model=EintragRead,
    dependencies=[Depends(require_admin)],
)
async def eintrag_bilder_anordnen(
    eintrag_id: int, eingabe: BilderAnordnung, db: AsyncSession = Depends(get_async_db_session)
) -> EintragRead:
    e = await _eintrag_voll(db, eintrag_id)
    pos = {bid: i for i, bid in enumerate(eingabe.ids)}
    for b in e.bilder:
        if b.id in pos:
            b.reihenfolge = pos[b.id]
    await db.commit()
    return _eintrag_read(await _eintrag_voll(db, eintrag_id))


@router.put(
    "/eintrag-bild/{bild_id}", response_model=BildRead, dependencies=[Depends(require_admin)]
)
async def eintrag_bild_layout(
    bild_id: int, eingabe: BildLayout, db: AsyncSession = Depends(get_async_db_session)
) -> BildRead:
    b = await _hole_eintrag_bild(db, bild_id)
    if eingabe.spalten is not None:
        b.spalten = max(1, min(4, eingabe.spalten))
    if eingabe.zeilen is not None:
        b.zeilen = max(1, min(2, eingabe.zeilen))
    await db.commit()
    await db.refresh(b)
    return _bild_read(b)


@router.delete("/eintrag-bild/{bild_id}", status_code=204, dependencies=[Depends(require_admin)])
async def eintrag_bild_entfernen(
    bild_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> Response:
    b = await _hole_eintrag_bild(db, bild_id)
    await db.delete(b)
    await db.commit()
    return Response(status_code=204)


@router.put(
    "/{ausgabe_id}/cover", response_model=AusgabeDetail, dependencies=[Depends(require_admin)]
)
async def cover_hochladen(
    ausgabe_id: int,
    datei: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db_session),
) -> AusgabeDetail:
    n = await _hole_newsletter(db, ausgabe_id)
    n.cover_bild, n.cover_mime = await _lies_bild(datei)
    n.aktualisiert_am = _jetzt()
    await db.commit()
    return _detail(await _hole_ausgabe(db, ausgabe_id))


@router.delete(
    "/{ausgabe_id}/cover", response_model=AusgabeDetail, dependencies=[Depends(require_admin)]
)
async def cover_entfernen(
    ausgabe_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> AusgabeDetail:
    n = await _hole_newsletter(db, ausgabe_id)
    n.cover_bild = None
    n.cover_mime = None
    n.aktualisiert_am = _jetzt()
    await db.commit()
    return _detail(await _hole_ausgabe(db, ausgabe_id))


@router.put(
    "/{ausgabe_id}/rueckseite", response_model=AusgabeDetail, dependencies=[Depends(require_admin)]
)
async def rueckseite_hochladen(
    ausgabe_id: int,
    datei: UploadFile = File(...),
    db: AsyncSession = Depends(get_async_db_session),
) -> AusgabeDetail:
    n = await _hole_newsletter(db, ausgabe_id)
    n.rueck_bild, n.rueck_mime = await _lies_bild(datei)
    n.aktualisiert_am = _jetzt()
    await db.commit()
    return _detail(await _hole_ausgabe(db, ausgabe_id))


@router.delete(
    "/{ausgabe_id}/rueckseite", response_model=AusgabeDetail, dependencies=[Depends(require_admin)]
)
async def rueckseite_entfernen(
    ausgabe_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> AusgabeDetail:
    n = await _hole_newsletter(db, ausgabe_id)
    n.rueck_bild = None
    n.rueck_mime = None
    n.aktualisiert_am = _jetzt()
    await db.commit()
    return _detail(await _hole_ausgabe(db, ausgabe_id))


@router.post(
    "/{ausgabe_id}/kpi", response_model=AusgabeDetail, dependencies=[Depends(require_admin)]
)
async def kpi_einfuegen(
    ausgabe_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> AusgabeDetail:
    """Aktuelle Belegschafts-KPIs als Snapshot in die Ausgabe einfrieren."""
    n = await _hole_ausgabe(db, ausgabe_id)
    kpi = await aggregiere_belegschaft(db)
    n.kpi_snapshot = kpi.model_dump()
    n.aktualisiert_am = _jetzt()
    await db.commit()
    return _detail(await _hole_ausgabe(db, n.id))


@router.delete(
    "/{ausgabe_id}/kpi", response_model=AusgabeDetail, dependencies=[Depends(require_admin)]
)
async def kpi_entfernen(
    ausgabe_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> AusgabeDetail:
    n = await _hole_ausgabe(db, ausgabe_id)
    n.kpi_snapshot = None
    n.aktualisiert_am = _jetzt()
    await db.commit()
    return _detail(await _hole_ausgabe(db, n.id))


# Ganz zuletzt registriert: die 1-Segment-Parameter-Route darf die literalen
# Routen (/admin, /rubriken) NICHT abfangen (FastAPI matcht in Deklarations-
# reihenfolge).
@router.get("/{ausgabe_id}", response_model=AusgabeDetail)
async def ausgabe(
    ausgabe_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> AusgabeDetail:
    """Eine veröffentlichte Ausgabe mit allen Einträgen."""
    n = await _hole_ausgabe(db, ausgabe_id)
    if n.status != "veroeffentlicht":
        raise HTTPException(status_code=404, detail="Ausgabe nicht gefunden.")
    return _detail(n)
