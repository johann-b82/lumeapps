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
Die übrigen GET-Routen (veröffentlichte Ausgaben + Bild) sind viewer-lesbar.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_async_db_session
from app.models import Newsletter, NewsletterEintrag
from app.models.newsletter import NEWSLETTER_RUBRIKEN, NEWSLETTER_STATUS
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


class EintragRead(BaseModel):
    id: int
    rubrik: str
    untertitel: str
    inhalt_md: str
    reihenfolge: int
    hat_bild: bool


class AusgabeDetail(BaseModel):
    id: int
    jahr: int
    quartal: int
    titel: str | None
    status: str
    eintraege: list[EintragRead]


class AusgabeAnlegen(BaseModel):
    jahr: int
    quartal: int
    titel: str | None = None


class AusgabeAendern(BaseModel):
    titel: str | None = None
    status: str | None = None


class EintragAnlegen(BaseModel):
    rubrik: str
    untertitel: str
    inhalt_md: str = ""


class EintragAendern(BaseModel):
    rubrik: str | None = None
    untertitel: str | None = None
    inhalt_md: str | None = None
    reihenfolge: int | None = None


# --------------------------------------------------------------------------
# Hilfen
# --------------------------------------------------------------------------


def _list_item(n: Newsletter) -> AusgabeListItem:
    return AusgabeListItem(id=n.id, jahr=n.jahr, quartal=n.quartal, titel=n.titel, status=n.status)


def _eintrag_read(e: NewsletterEintrag) -> EintragRead:
    return EintragRead(
        id=e.id,
        rubrik=e.rubrik,
        untertitel=e.untertitel,
        inhalt_md=e.inhalt_md,
        reihenfolge=e.reihenfolge,
        hat_bild=e.bild_data is not None,
    )


def _detail(n: Newsletter) -> AusgabeDetail:
    return AusgabeDetail(
        id=n.id,
        jahr=n.jahr,
        quartal=n.quartal,
        titel=n.titel,
        status=n.status,
        eintraege=[_eintrag_read(e) for e in n.eintraege],
    )


async def _hole_ausgabe(db: AsyncSession, ausgabe_id: int) -> Newsletter:
    n = (
        await db.execute(
            select(Newsletter)
            .where(Newsletter.id == ausgabe_id)
            .options(selectinload(Newsletter.eintraege))
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


@router.get("/{ausgabe_id}", response_model=AusgabeDetail)
async def ausgabe(
    ausgabe_id: int, db: AsyncSession = Depends(get_async_db_session)
) -> AusgabeDetail:
    """Eine veröffentlichte Ausgabe mit allen Einträgen."""
    n = await _hole_ausgabe(db, ausgabe_id)
    if n.status != "veroeffentlicht":
        raise HTTPException(status_code=404, detail="Ausgabe nicht gefunden.")
    return _detail(n)


@router.get("/eintrag/{eintrag_id}/bild")
async def bild(eintrag_id: int, db: AsyncSession = Depends(get_async_db_session)) -> Response:
    e = await _hole_eintrag(db, eintrag_id)
    if e.bild_data is None:
        raise HTTPException(status_code=404, detail="Kein Bild.")
    return Response(content=e.bild_data, media_type=e.bild_mime or "image/png")


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
    await db.refresh(e)
    return _eintrag_read(e)


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
    await db.refresh(e)
    return _eintrag_read(e)


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
    await db.refresh(e)
    return _eintrag_read(e)


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
