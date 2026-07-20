"""Derived progress and overdue state for the Audit-Modul (v1.84).

Everything in here is a pure function of rows already in the database, computed
on read. Nothing is written back.

Why "überfällig" is not a stored status: it is a function of ``due_date`` and
today's date, so a stored copy would be wrong the moment a deadline passes
without anyone touching the record. A nightly job could keep it fresh, but that
buys staleness and a scheduler dependency to save one comparison per phase.

Why the audit status is not derived from the phases: the requirement forbids
automatic closure without human approval. Phase completion therefore drives the
*progress* readout and nothing else — advancing ``Audit.status`` stays an
explicit, logged human act.
"""
from __future__ import annotations

from datetime import date

from app.models import Audit, AuditPhase
from app.schemas.audit import AuditProgress

# A phase in one of these states is finished as far as progress is concerned and
# can never be overdue.
_SETTLED_PHASE_STATUSES = frozenset({"erledigt", "nicht_zutreffend"})

# An audit in one of these states is off the clock; a past due date no longer
# means anything actionable.
_CLOSED_AUDIT_STATUSES = frozenset({"abgeschlossen", "abgesagt", "verschoben"})


def phase_is_overdue(phase: AuditPhase, today: date) -> bool:
    """True when a phase has a due date in the past and is not yet settled."""
    if phase.status in _SETTLED_PHASE_STATUSES:
        return False
    return phase.due_date is not None and phase.due_date < today


def compute_progress(
    audit: Audit, phases: list[AuditPhase], today: date | None = None
) -> AuditProgress:
    """Derive the progress block shown on the list and detail views.

    ``phases_relevant`` excludes 'nicht_zutreffend' phases, so marking a phase as
    not applicable moves the bar forward rather than capping it below 100%.
    """
    today = today or date.today()

    total = len(phases)
    not_applicable = sum(1 for p in phases if p.status == "nicht_zutreffend")
    relevant = total - not_applicable
    done = sum(1 for p in phases if p.status == "erledigt")
    percent = round(done / relevant * 100) if relevant else 0

    audit_is_closed = audit.status in _CLOSED_AUDIT_STATUSES
    overdue_titles = (
        []
        if audit_is_closed
        else [p.title for p in phases if phase_is_overdue(p, today)]
    )

    # The audit's own planned end can lapse even when no single phase carries a
    # due date, so it counts as overdue in its own right.
    planned_end_lapsed = (
        not audit_is_closed
        and audit.planned_end is not None
        and audit.planned_end < today
    )

    return AuditProgress(
        phases_total=total,
        phases_relevant=relevant,
        phases_done=done,
        phases_not_applicable=not_applicable,
        percent=percent,
        is_overdue=bool(overdue_titles) or planned_end_lapsed,
        overdue_phase_titles=overdue_titles,
    )
