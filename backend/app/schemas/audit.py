"""Pydantic v2 schemas for the Audit-Modul (v1.84).

``*In`` create payloads, ``*Patch`` all-optional partial updates, ``*Out`` read
models (``from_attributes``). ``AuditDetail`` nests phases, norm links and the
derived progress block so the detail page loads in a single request.

The ``Literal`` aliases below mirror the CheckConstraints in
``app/models/audit.py`` — keep the two in sync.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

AuditStatus = Literal[
    "geplant",
    "in_vorbereitung",
    "in_durchfuehrung",
    "berichtet",
    "massnahmen_offen",
    "abgeschlossen",
    "verschoben",
    "abgesagt",
]
PhaseStatus = Literal["offen", "in_arbeit", "erledigt", "nicht_zutreffend"]
AuditType = Literal["intern", "extern"]
AuditCategory = Literal["system", "prozess", "produkt", "lieferant"]
TrailAction = Literal["create", "update", "delete", "status_change", "phase_skip"]


# ── Norm references (Normmatrix master data) ────────────────────────────


class NormReferenceIn(BaseModel):
    regulation: str = Field(min_length=1, max_length=120)
    revision: str = Field(default="", max_length=60)
    clause: str = Field(min_length=1, max_length=60)
    short_text: str = ""
    valid_from: date | None = None
    valid_to: date | None = None
    # Defaults to False: a clause is unverified until a human confirms it
    # against the current consolidated regulation text.
    verified: bool = False
    active: bool = True


class NormReferencePatch(BaseModel):
    regulation: str | None = Field(default=None, min_length=1, max_length=120)
    revision: str | None = Field(default=None, max_length=60)
    clause: str | None = Field(default=None, min_length=1, max_length=60)
    short_text: str | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    verified: bool | None = None
    active: bool | None = None


class NormReferenceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    regulation: str
    revision: str
    clause: str
    short_text: str
    valid_from: date | None
    valid_to: date | None
    verified: bool
    active: bool
    created_at: datetime
    updated_at: datetime


# ── Phase templates ─────────────────────────────────────────────────────


class TemplateStepIn(BaseModel):
    position: int = Field(ge=1, le=200)
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    mandatory: bool = True


class TemplateStepOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    title: str
    description: str
    mandatory: bool


class PhaseTemplateIn(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    audit_category: AuditCategory | None = None
    description: str = ""
    active: bool = True
    steps: list[TemplateStepIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_positions(self) -> PhaseTemplateIn:
        positions = [s.position for s in self.steps]
        if len(positions) != len(set(positions)):
            raise ValueError("step positions must be unique within a template")
        return self


class PhaseTemplatePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    audit_category: AuditCategory | None = None
    description: str | None = None
    active: bool | None = None


class PhaseTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    audit_category: str | None
    description: str
    active: bool
    created_at: datetime
    updated_at: datetime


class PhaseTemplateDetail(PhaseTemplateOut):
    steps: list[TemplateStepOut] = Field(default_factory=list)


# ── Audit phases ────────────────────────────────────────────────────────


class PhaseIn(BaseModel):
    """Add an ad-hoc phase to an audit that a template did not cover."""

    position: int = Field(ge=1, le=200)
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    mandatory: bool = True
    responsible: str | None = Field(default=None, max_length=255)
    due_date: date | None = None


class PhasePatch(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: PhaseStatus | None = None
    responsible: str | None = Field(default=None, max_length=255)
    due_date: date | None = None
    completed_on: date | None = None
    comment: str | None = None
    skip_reason: str | None = None


class PhaseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    position: int
    title: str
    description: str
    mandatory: bool
    status: str
    responsible: str | None
    due_date: date | None
    completed_on: date | None
    comment: str
    skip_reason: str | None
    created_at: datetime
    updated_at: datetime


class PhaseWithFlags(PhaseOut):
    """A phase plus the derived overdue flag (never stored — see models/audit.py)."""

    is_overdue: bool = False


# ── Audits ──────────────────────────────────────────────────────────────


class AuditIn(BaseModel):
    audit_number: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=255)
    audit_type: AuditType
    # A set, not one value: an audit is often a Prozessaudit and a Produktaudit
    # in the same session (v1.85).
    categories: list[AuditCategory] = Field(min_length=1)
    scope_label: str = Field(default="", max_length=255)
    objective: str = ""
    lead_auditor: str | None = Field(default=None, max_length=255)
    audit_team: str = ""
    planned_start: date | None = None
    planned_end: date | None = None
    priority: int = Field(default=2, ge=1, le=3)
    # When given, the template's steps are copied into audit_phases. Copied, not
    # referenced: editing the template later must not rewrite a running audit.
    template_id: uuid.UUID | None = None
    norm_reference_ids: list[uuid.UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def _dedupe_categories(self) -> AuditIn:
        # Order-insensitive: the set is what matters, and the DB has a
        # unique(audit_id, category) constraint that duplicates would trip.
        self.categories = sorted(set(self.categories))
        return self

    @model_validator(mode="after")
    def _check_planned_range(self) -> AuditIn:
        if (
            self.planned_start is not None
            and self.planned_end is not None
            and self.planned_end < self.planned_start
        ):
            raise ValueError("planned_end must not be before planned_start")
        return self


class AuditPatch(BaseModel):
    audit_number: str | None = Field(default=None, min_length=1, max_length=64)
    title: str | None = Field(default=None, min_length=1, max_length=255)
    audit_type: AuditType | None = None
    categories: list[AuditCategory] | None = Field(default=None, min_length=1)
    scope_label: str | None = Field(default=None, max_length=255)
    objective: str | None = None
    lead_auditor: str | None = Field(default=None, max_length=255)
    audit_team: str | None = None
    planned_start: date | None = None
    planned_end: date | None = None
    priority: int | None = Field(default=None, ge=1, le=3)
    norm_reference_ids: list[uuid.UUID] | None = None


class AuditStatusChange(BaseModel):
    """Explicit, human-driven status transition.

    Status is never derived or auto-advanced — "keine automatische Schließung
    von Audits ohne menschliche Freigabe". Closing an audit requires a note.
    """

    status: AuditStatus
    note: str = ""

    @model_validator(mode="after")
    def _require_note_on_close(self) -> AuditStatusChange:
        if self.status in ("abgeschlossen", "abgesagt") and not self.note.strip():
            raise ValueError(
                "a note is required when closing or cancelling an audit"
            )
        return self


class AuditProgress(BaseModel):
    """Derived at read time from the phase rows. Nothing here is stored."""

    phases_total: int
    phases_relevant: int
    phases_done: int
    phases_not_applicable: int
    percent: int
    is_overdue: bool
    # Titles of phases past their due date and not yet done — drives the UI hint.
    overdue_phase_titles: list[str] = Field(default_factory=list)


class AuditOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    audit_number: str
    title: str
    audit_type: str
    categories: list[str] = Field(default_factory=list)
    scope_label: str
    objective: str
    lead_auditor: str | None
    audit_team: str
    planned_start: date | None
    planned_end: date | None
    priority: int
    status: str
    template_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class AuditListItem(AuditOut):
    progress: AuditProgress


class AuditDetail(AuditOut):
    phases: list[PhaseWithFlags] = Field(default_factory=list)
    norm_references: list[NormReferenceOut] = Field(default_factory=list)
    progress: AuditProgress


# ── Trail (read-only) ───────────────────────────────────────────────────


class TrailEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    audit_id: uuid.UUID | None
    entity_type: str
    entity_id: uuid.UUID
    action: str
    field: str | None
    old_value: str | None
    new_value: str | None
    reason: str | None
    actor_user_id: uuid.UUID
    actor_role: str
    occurred_at: datetime
