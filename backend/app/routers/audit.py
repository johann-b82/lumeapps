"""Audit-Modul router — internal/external audit management (v1.84, admin-only).

All endpoints are admin-gated at the router level. That is a Phase 1 limitation,
not a design choice: the identity provider currently exposes exactly two roles
(Admin/Viewer, see app/security/roles.py), which is too coarse to express the
Auditor / Lead-Auditor / Auditierter / QM-Leitung split the regulations expect.
Until that lands, the four-eyes principle on audit closure and the auditor
independence check are NOT implemented — see docs/modules/audit.md.

Routes:

    GET    /api/audit/audits                    list audits + derived progress
    POST   /api/audit/audits                    create (instantiates phases)
    GET    /api/audit/audits/{id}               audit + phases + norms + progress
    PATCH  /api/audit/audits/{id}               edit audit fields
    POST   /api/audit/audits/{id}/status        explicit, logged status change
    POST   /api/audit/audits/{id}/phases        add an ad-hoc phase
    GET    /api/audit/audits/{id}/trail         read the change log
    PATCH  /api/audit/phases/{pid}              update one checklist phase
    GET    /api/audit/norm-references           Normmatrix master data
    POST   /api/audit/norm-references           add a clause
    PATCH  /api/audit/norm-references/{nid}     edit / verify / deactivate
    GET    /api/audit/templates                 phase templates
    POST   /api/audit/templates                 create a template + steps
    GET    /api/audit/templates/{tid}           template + steps
    PATCH  /api/audit/templates/{tid}           edit template metadata

There is deliberately no DELETE for audits, phases or trail entries. An audit
that should not have existed is cancelled ('abgesagt'), not erased — deleting it
would take its trail's subject away with it. Norm references are deactivated
rather than deleted (the FK is ON DELETE RESTRICT).
"""
from __future__ import annotations

import uuid
from datetime import date

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_async_db_session
from app.models import (
    Audit,
    AuditCategoryLink,
    AuditNormLink,
    AuditNormReference,
    AuditPhase,
    AuditPhaseTemplate,
    AuditPhaseTemplateStep,
    AuditTrailEntry,
)
from app.schemas import CurrentUser
from app.schemas.audit import (
    AuditDetail,
    AuditIn,
    AuditListItem,
    AuditOut,
    AuditPatch,
    AuditStatusChange,
    NormReferenceIn,
    NormReferenceOut,
    NormReferencePatch,
    PhaseIn,
    PhaseOut,
    PhasePatch,
    PhaseTemplateDetail,
    PhaseTemplateIn,
    PhaseTemplateOut,
    PhaseTemplatePatch,
    PhaseWithFlags,
    TrailEntryOut,
)
from app.security.directus_auth import get_current_user, require_admin
from app.services.audit_status import compute_progress, phase_is_overdue
from app.services.audit_trail import record, record_field_changes, snapshot

router = APIRouter(
    prefix="/api/audit",
    tags=["audit"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)

# Audit columns worth logging individually on a PATCH.
_AUDIT_TRACKED_FIELDS = (
    "audit_number",
    "title",
    "audit_type",
    "scope_label",
    "objective",
    "lead_auditor",
    "audit_team",
    "planned_start",
    "planned_end",
    "priority",
)
_PHASE_TRACKED_FIELDS = (
    "title",
    "description",
    "responsible",
    "due_date",
    "completed_on",
    "comment",
)


async def _load_audit(db: AsyncSession, audit_id: uuid.UUID) -> Audit:
    result = await db.execute(
        sa.select(Audit)
        .where(Audit.id == audit_id)
        .options(
            selectinload(Audit.phases),
            selectinload(Audit.norm_links).selectinload(AuditNormLink.norm_reference),
            selectinload(Audit.category_links),
        )
    )
    audit = result.scalar_one_or_none()
    if audit is None:
        raise HTTPException(status_code=404, detail="audit not found")
    return audit


def _audit_base(audit: Audit) -> dict:
    """Scalar audit fields plus the derived category list.

    ``categories`` lives in a join table rather than on the row, so it cannot be
    pulled off the ORM object by name like the other AuditOut fields.
    """
    data = {
        f: getattr(audit, f) for f in AuditOut.model_fields if f != "categories"
    }
    # Sorted here, not left to the relationship's order_by: that only applies
    # when the collection comes from the DB, so a collection just mutated in
    # memory would come back in insertion order and make the response order
    # depend on the load path.
    data["categories"] = sorted(link.category for link in audit.category_links)
    return data


def _detail(audit: Audit, today: date | None = None) -> AuditDetail:
    today = today or date.today()
    phases = sorted(audit.phases, key=lambda p: p.position)
    return AuditDetail(
        **_audit_base(audit),
        phases=[
            PhaseWithFlags(
                **{f: getattr(p, f) for f in PhaseOut.model_fields},
                is_overdue=phase_is_overdue(p, today),
            )
            for p in phases
        ],
        norm_references=[
            NormReferenceOut.model_validate(link.norm_reference)
            for link in audit.norm_links
        ],
        progress=compute_progress(audit, phases, today),
    )


async def _validate_norm_ids(db: AsyncSession, norm_ids: set[uuid.UUID]) -> None:
    if not norm_ids:
        return
    found = await db.execute(
        sa.select(AuditNormReference.id).where(AuditNormReference.id.in_(norm_ids))
    )
    missing = norm_ids - set(found.scalars().all())
    if missing:
        raise HTTPException(
            status_code=422,
            detail=f"unknown norm reference id(s): {sorted(str(m) for m in missing)}",
        )


async def _set_norm_links(
    db: AsyncSession, audit: Audit, norm_ids: list[uuid.UUID]
) -> None:
    """Replace the norm references of an *already loaded* audit.

    Requires ``audit.norm_links`` to be eagerly loaded (``_load_audit`` does
    this) — reading the collection here would otherwise lazy-load under async
    and raise MissingGreenlet.
    """
    wanted = set(norm_ids)
    await _validate_norm_ids(db, wanted)

    # Mutate the relationship collection rather than issuing raw add/delete:
    # the audit is already loaded, and a raw insert would leave the in-memory
    # collection stale for the response built after the commit. delete-orphan
    # turns the removal into a DELETE.
    existing = {link.norm_reference_id: link for link in audit.norm_links}
    for norm_id, link in existing.items():
        if norm_id not in wanted:
            audit.norm_links.remove(link)
    for norm_id in sorted(wanted - set(existing), key=str):
        audit.norm_links.append(AuditNormLink(norm_reference_id=norm_id))


# ── Audits ──────────────────────────────────────────────────────────────


@router.get("/audits", response_model=list[AuditListItem])
async def list_audits(
    status: str | None = Query(default=None),
    audit_type: str | None = Query(default=None),
    category: str | None = Query(default=None),
    year: int | None = Query(default=None, ge=2000, le=2100),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[AuditListItem]:
    stmt = sa.select(Audit).options(
        selectinload(Audit.phases), selectinload(Audit.category_links)
    )
    if status:
        stmt = stmt.where(Audit.status == status)
    if audit_type:
        stmt = stmt.where(Audit.audit_type == audit_type)
    if category:
        # "has this category", not "is exactly this category" — an audit can
        # carry several (v1.85).
        stmt = stmt.where(
            Audit.category_links.any(AuditCategoryLink.category == category)
        )
    if year:
        stmt = stmt.where(
            sa.extract("year", Audit.planned_start) == year
        )
    stmt = stmt.order_by(Audit.planned_start.desc().nullslast(), Audit.audit_number)

    result = await db.execute(stmt)
    audits = list(result.scalars().all())
    today = date.today()
    return [
        AuditListItem(
            **_audit_base(a),
            progress=compute_progress(a, sorted(a.phases, key=lambda p: p.position), today),
        )
        for a in audits
    ]


@router.post("/audits", response_model=AuditDetail, status_code=201)
async def create_audit(
    payload: AuditIn,
    db: AsyncSession = Depends(get_async_db_session),
    current_user: CurrentUser = Depends(require_admin),
) -> AuditDetail:
    existing = await db.execute(
        sa.select(Audit.id).where(Audit.audit_number == payload.audit_number)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=409, detail="an audit with this audit_number already exists"
        )

    # Validate before inserting anything, so a bad norm id fails the request
    # rather than half-building an audit.
    await _validate_norm_ids(db, set(payload.norm_reference_ids))

    data = payload.model_dump(exclude={"norm_reference_ids", "categories"})
    audit = Audit(**data)
    db.add(audit)
    await db.flush()  # assign audit.id before children reference it

    for category in payload.categories:
        db.add(AuditCategoryLink(audit_id=audit.id, category=category))

    # Copy the template's steps into owned phase rows. Copied on purpose: a
    # later template edit must not rewrite an audit already in flight.
    if payload.template_id is not None:
        template = await db.get(
            AuditPhaseTemplate,
            payload.template_id,
            options=[selectinload(AuditPhaseTemplate.steps)],
        )
        if template is None:
            raise HTTPException(status_code=422, detail="unknown template_id")
        for step in sorted(template.steps, key=lambda s: s.position):
            db.add(
                AuditPhase(
                    audit_id=audit.id,
                    position=step.position,
                    title=step.title,
                    description=step.description,
                    mandatory=step.mandatory,
                )
            )

    # Insert links directly: the audit is brand new, so there is nothing to
    # diff against and no reason to read back its (unloaded) collection.
    for norm_id in dict.fromkeys(payload.norm_reference_ids):
        db.add(AuditNormLink(audit_id=audit.id, norm_reference_id=norm_id))

    record(
        db,
        actor=current_user,
        entity_type="audit",
        entity_id=audit.id,
        audit_id=audit.id,
        action="create",
        field="audit_number",
        new_value=audit.audit_number,
    )

    await db.commit()
    return _detail(await _load_audit(db, audit.id))


@router.get("/audits/{audit_id}", response_model=AuditDetail)
async def get_audit(
    audit_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> AuditDetail:
    return _detail(await _load_audit(db, audit_id))


@router.patch("/audits/{audit_id}", response_model=AuditDetail)
async def patch_audit(
    audit_id: uuid.UUID,
    patch: AuditPatch,
    db: AsyncSession = Depends(get_async_db_session),
    current_user: CurrentUser = Depends(require_admin),
) -> AuditDetail:
    audit = await _load_audit(db, audit_id)
    changes = patch.model_dump(exclude_unset=True)
    norm_ids = changes.pop("norm_reference_ids", None)
    categories = changes.pop("categories", None)

    before = snapshot(audit, _AUDIT_TRACKED_FIELDS)
    for field, value in changes.items():
        setattr(audit, field, value)

    # Re-check the date ordering: AuditPatch has no model validator, so a patch
    # that moves only one of the two dates could otherwise invert the range and
    # fail at the DB constraint with an opaque error.
    if (
        audit.planned_start is not None
        and audit.planned_end is not None
        and audit.planned_end < audit.planned_start
    ):
        raise HTTPException(
            status_code=422, detail="planned_end must not be before planned_start"
        )

    record_field_changes(
        db,
        actor=current_user,
        entity_type="audit",
        entity_id=audit.id,
        audit_id=audit.id,
        before=before,
        after=snapshot(audit, _AUDIT_TRACKED_FIELDS),
    )

    if categories is not None:
        old_categories = sorted(link.category for link in audit.category_links)
        new_categories = sorted(set(categories))
        if old_categories != new_categories:
            # Mutate the relationship collection rather than issuing raw
            # add/delete: the audit is already loaded, and a raw insert would
            # leave the in-memory collection stale for the response we build
            # after the commit. delete-orphan turns the removal into a DELETE.
            for link in list(audit.category_links):
                if link.category not in new_categories:
                    audit.category_links.remove(link)
            for category in sorted(set(new_categories) - set(old_categories)):
                audit.category_links.append(AuditCategoryLink(category=category))
            record(
                db,
                actor=current_user,
                entity_type="audit",
                entity_id=audit.id,
                audit_id=audit.id,
                action="update",
                field="categories",
                old_value=", ".join(old_categories),
                new_value=", ".join(new_categories),
            )

    if norm_ids is not None:
        old_ids = sorted(str(link.norm_reference_id) for link in audit.norm_links)
        await _set_norm_links(db, audit, norm_ids)
        new_ids = sorted(str(n) for n in norm_ids)
        if old_ids != new_ids:
            record(
                db,
                actor=current_user,
                entity_type="audit",
                entity_id=audit.id,
                audit_id=audit.id,
                action="update",
                field="norm_references",
                old_value=", ".join(old_ids),
                new_value=", ".join(new_ids),
            )

    await db.commit()
    return _detail(await _load_audit(db, audit_id))


@router.post("/audits/{audit_id}/status", response_model=AuditDetail)
async def change_audit_status(
    audit_id: uuid.UUID,
    payload: AuditStatusChange,
    db: AsyncSession = Depends(get_async_db_session),
    current_user: CurrentUser = Depends(require_admin),
) -> AuditDetail:
    """Move an audit to a new status. Always an explicit human act, always logged.

    Nothing in this module advances the status automatically, and closing is not
    blocked on the checklist being complete — a lead auditor may have a valid
    reason to close with open phases. The unfinished phases stay visible in the
    trail and in the progress readout rather than being silently resolved.
    """
    audit = await _load_audit(db, audit_id)
    old_status = audit.status
    if old_status == payload.status:
        return _detail(audit)

    audit.status = payload.status
    record(
        db,
        actor=current_user,
        entity_type="audit",
        entity_id=audit.id,
        audit_id=audit.id,
        action="status_change",
        field="status",
        old_value=old_status,
        new_value=payload.status,
        reason=payload.note.strip() or None,
    )
    await db.commit()
    return _detail(await _load_audit(db, audit_id))


@router.get("/audits/{audit_id}/trail", response_model=list[TrailEntryOut])
async def get_audit_trail(
    audit_id: uuid.UUID,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[AuditTrailEntry]:
    await _load_audit(db, audit_id)
    result = await db.execute(
        sa.select(AuditTrailEntry)
        .where(AuditTrailEntry.audit_id == audit_id)
        .order_by(AuditTrailEntry.occurred_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


# ── Phases ──────────────────────────────────────────────────────────────


@router.post("/audits/{audit_id}/phases", response_model=PhaseOut, status_code=201)
async def create_phase(
    audit_id: uuid.UUID,
    payload: PhaseIn,
    db: AsyncSession = Depends(get_async_db_session),
    current_user: CurrentUser = Depends(require_admin),
) -> AuditPhase:
    audit = await _load_audit(db, audit_id)
    if any(p.position == payload.position for p in audit.phases):
        raise HTTPException(
            status_code=409, detail="a phase with this position already exists"
        )

    phase = AuditPhase(audit_id=audit_id, **payload.model_dump())
    db.add(phase)
    await db.flush()
    record(
        db,
        actor=current_user,
        entity_type="audit_phase",
        entity_id=phase.id,
        audit_id=audit_id,
        action="create",
        field="title",
        new_value=phase.title,
    )
    await db.commit()
    await db.refresh(phase)
    return phase


@router.patch("/phases/{phase_id}", response_model=PhaseWithFlags)
async def patch_phase(
    phase_id: uuid.UUID,
    patch: PhasePatch,
    db: AsyncSession = Depends(get_async_db_session),
    current_user: CurrentUser = Depends(require_admin),
) -> PhaseWithFlags:
    phase = await db.get(AuditPhase, phase_id)
    if phase is None:
        raise HTTPException(status_code=404, detail="phase not found")

    changes = patch.model_dump(exclude_unset=True)
    old_status = phase.status
    before = snapshot(phase, _PHASE_TRACKED_FIELDS)

    for field, value in changes.items():
        setattr(phase, field, value)

    new_status = phase.status

    # Invariant 1 — no skipping a mandatory phase without a justification.
    # PhasePatch has no model validator, so this is re-checked here; the DB
    # CheckConstraint is the last line of defence, not the first.
    if (
        new_status == "nicht_zutreffend"
        and phase.mandatory
        and not (phase.skip_reason or "").strip()
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "skip_reason is required to mark a mandatory phase as "
                "'nicht_zutreffend'"
            ),
        )

    # Invariant 2 — a completed phase carries its Ist-Termin. Default it to today
    # when the caller did not supply one: recording the date the phase was
    # actually marked done is the ALCOA+ 'contemporaneous' behaviour.
    if new_status == "erledigt" and phase.completed_on is None:
        phase.completed_on = date.today()

    # A phase moved back out of 'nicht_zutreffend' must not keep displaying a
    # stale justification. The old value survives in the trail.
    if new_status != "nicht_zutreffend" and phase.skip_reason:
        record(
            db,
            actor=current_user,
            entity_type="audit_phase",
            entity_id=phase.id,
            audit_id=phase.audit_id,
            action="update",
            field="skip_reason",
            old_value=phase.skip_reason,
            new_value=None,
        )
        phase.skip_reason = None

    record_field_changes(
        db,
        actor=current_user,
        entity_type="audit_phase",
        entity_id=phase.id,
        audit_id=phase.audit_id,
        before=before,
        after=snapshot(phase, _PHASE_TRACKED_FIELDS),
    )

    if new_status != old_status:
        record(
            db,
            actor=current_user,
            entity_type="audit_phase",
            entity_id=phase.id,
            audit_id=phase.audit_id,
            action="phase_skip" if new_status == "nicht_zutreffend" else "status_change",
            field="status",
            old_value=old_status,
            new_value=new_status,
            reason=(phase.skip_reason or None)
            if new_status == "nicht_zutreffend"
            else None,
        )

    await db.commit()
    await db.refresh(phase)
    return PhaseWithFlags(
        **{f: getattr(phase, f) for f in PhaseOut.model_fields},
        is_overdue=phase_is_overdue(phase, date.today()),
    )


# ── Normmatrix master data ──────────────────────────────────────────────


@router.get("/norm-references", response_model=list[NormReferenceOut])
async def list_norm_references(
    include_inactive: bool = Query(default=False),
    db: AsyncSession = Depends(get_async_db_session),
) -> list[AuditNormReference]:
    stmt = sa.select(AuditNormReference)
    if not include_inactive:
        stmt = stmt.where(AuditNormReference.active.is_(True))
    stmt = stmt.order_by(AuditNormReference.regulation, AuditNormReference.clause)
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.post("/norm-references", response_model=NormReferenceOut, status_code=201)
async def create_norm_reference(
    payload: NormReferenceIn,
    db: AsyncSession = Depends(get_async_db_session),
    current_user: CurrentUser = Depends(require_admin),
) -> AuditNormReference:
    norm = AuditNormReference(**payload.model_dump())
    db.add(norm)
    await db.flush()
    record(
        db,
        actor=current_user,
        entity_type="audit_norm_reference",
        entity_id=norm.id,
        action="create",
        field="clause",
        new_value=f"{norm.regulation} {norm.clause}",
    )
    await db.commit()
    await db.refresh(norm)
    return norm


@router.patch("/norm-references/{norm_id}", response_model=NormReferenceOut)
async def patch_norm_reference(
    norm_id: uuid.UUID,
    patch: NormReferencePatch,
    db: AsyncSession = Depends(get_async_db_session),
    current_user: CurrentUser = Depends(require_admin),
) -> AuditNormReference:
    norm = await db.get(AuditNormReference, norm_id)
    if norm is None:
        raise HTTPException(status_code=404, detail="norm reference not found")

    tracked = ("regulation", "revision", "clause", "short_text", "verified", "active")
    before = snapshot(norm, tracked)
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(norm, field, value)

    record_field_changes(
        db,
        actor=current_user,
        entity_type="audit_norm_reference",
        entity_id=norm.id,
        before=before,
        after=snapshot(norm, tracked),
    )
    await db.commit()
    await db.refresh(norm)
    return norm


# ── Phase templates ─────────────────────────────────────────────────────


@router.get("/templates", response_model=list[PhaseTemplateOut])
async def list_templates(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[AuditPhaseTemplate]:
    result = await db.execute(
        sa.select(AuditPhaseTemplate).order_by(AuditPhaseTemplate.name)
    )
    return list(result.scalars().all())


@router.get("/templates/{template_id}", response_model=PhaseTemplateDetail)
async def get_template(
    template_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> AuditPhaseTemplate:
    template = await db.get(
        AuditPhaseTemplate,
        template_id,
        options=[selectinload(AuditPhaseTemplate.steps)],
    )
    if template is None:
        raise HTTPException(status_code=404, detail="template not found")
    return template


@router.post("/templates", response_model=PhaseTemplateDetail, status_code=201)
async def create_template(
    payload: PhaseTemplateIn,
    db: AsyncSession = Depends(get_async_db_session),
    current_user: CurrentUser = Depends(require_admin),
) -> AuditPhaseTemplate:
    template = AuditPhaseTemplate(**payload.model_dump(exclude={"steps"}))
    db.add(template)
    await db.flush()
    for step in payload.steps:
        db.add(AuditPhaseTemplateStep(template_id=template.id, **step.model_dump()))

    record(
        db,
        actor=current_user,
        entity_type="audit_phase_template",
        entity_id=template.id,
        action="create",
        field="name",
        new_value=template.name,
    )
    await db.commit()
    return await get_template(template.id, db)


@router.patch("/templates/{template_id}", response_model=PhaseTemplateOut)
async def patch_template(
    template_id: uuid.UUID,
    patch: PhaseTemplatePatch,
    db: AsyncSession = Depends(get_async_db_session),
    current_user: CurrentUser = Depends(require_admin),
) -> AuditPhaseTemplate:
    template = await db.get(AuditPhaseTemplate, template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="template not found")

    tracked = ("name", "audit_category", "description", "active")
    before = snapshot(template, tracked)
    for field, value in patch.model_dump(exclude_unset=True).items():
        setattr(template, field, value)

    record_field_changes(
        db,
        actor=current_user,
        entity_type="audit_phase_template",
        entity_id=template.id,
        before=before,
        after=snapshot(template, tracked),
    )
    await db.commit()
    await db.refresh(template)
    return template
