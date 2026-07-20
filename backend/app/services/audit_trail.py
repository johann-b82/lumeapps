"""Append-only audit trail writer for the Audit-Modul (v1.84).

Every mutation in ``app/routers/audit.py`` goes through ``record`` or
``record_field_changes``. There is no update path and no delete path — not in
this module, and not exposed by the router.

Scope of the guarantee, stated plainly: this is *application-level*
immutability. Nothing in the app can alter a trail row, but the database role
the app connects with still holds UPDATE/DELETE privileges on the table, so a
direct SQL session could. Closing that gap (revoking those privileges from the
app role, or a rule that rejects the statements) is deliberately deferred and
tracked in docs/modules/audit.md.

The actor is recorded as the Directus user UUID from the JWT. ``CurrentUser.email``
is currently synthesized from that UUID (``app/security/directus_auth.py``), so it
is not written here — a fabricated identity in a revision-proof log is worse than
no identity at all.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditTrailEntry
from app.schemas import CurrentUser

# Fields that carry no information worth logging on every write.
_IGNORED_FIELDS = frozenset({"updated_at", "created_at"})


def _render(value: Any) -> str | None:
    """Render a column value as the text snapshot stored in the log."""
    if value is None:
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    return str(value)


def record(
    db: AsyncSession,
    *,
    actor: CurrentUser,
    entity_type: str,
    entity_id: uuid.UUID,
    action: str,
    audit_id: uuid.UUID | None = None,
    field: str | None = None,
    old_value: Any = None,
    new_value: Any = None,
    reason: str | None = None,
) -> AuditTrailEntry:
    """Stage one trail entry on the session.

    Does not commit — the caller commits the entry together with the change it
    describes, so a change can never land without its log row.
    """
    entry = AuditTrailEntry(
        audit_id=audit_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        field=field,
        old_value=_render(old_value),
        new_value=_render(new_value),
        reason=reason,
        actor_user_id=actor.id,
        actor_role=str(actor.role),
    )
    db.add(entry)
    return entry


def record_field_changes(
    db: AsyncSession,
    *,
    actor: CurrentUser,
    entity_type: str,
    entity_id: uuid.UUID,
    before: dict[str, Any],
    after: dict[str, Any],
    audit_id: uuid.UUID | None = None,
    action: str = "update",
) -> list[AuditTrailEntry]:
    """Stage one entry per field that actually changed.

    One row per field rather than one row per request: "wer/wann/was/alt→neu"
    only reads cleanly if each row is a single alt→neu pair.
    """
    entries: list[AuditTrailEntry] = []
    for field, new_value in after.items():
        if field in _IGNORED_FIELDS:
            continue
        old_value = before.get(field)
        if old_value == new_value:
            continue
        entries.append(
            record(
                db,
                actor=actor,
                entity_type=entity_type,
                entity_id=entity_id,
                action=action,
                audit_id=audit_id,
                field=field,
                old_value=old_value,
                new_value=new_value,
            )
        )
    return entries


def snapshot(obj: Any, fields: tuple[str, ...]) -> dict[str, Any]:
    """Capture the named attributes of an ORM object as a plain dict."""
    return {field: getattr(obj, field) for field in fields}
