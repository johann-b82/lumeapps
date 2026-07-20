"""Audit-Modul (internal/external audit management) ORM models — v1.84.

Phase 1 covers the core workflow only: planning an audit and driving it through
its phase checklist. Findings/CAPA, the Auditprogramm year plan, the dashboard
and PDF export are deliberately out of scope here.

Seven tables:
  - ``audit_norm_references``:      editable regulatory master data (Normmatrix).
  - ``audit_phase_templates``:      a reusable phase sequence per audit category.
  - ``audit_phase_template_steps``: the ordered steps inside such a template.
  - ``audits``:                     one planned/running/closed audit.
  - ``audit_norm_links``:           audit <-> norm reference (many-to-many).
  - ``audit_phases``:               the per-audit checklist, instantiated from a
                                    template at creation time and then owned by
                                    the audit (editing a template never rewrites
                                    history on an audit already in flight).
  - ``audit_trail_entries``:        append-only change log.

Two modelling decisions worth knowing about:

*Überfällig is not a stored status.* The requirement lists it as a Sonderstatus,
but it is a pure function of ``due_date`` and today's date. Storing it would go
stale the moment a date passes without a write, so it is derived on read in
``app.services.audit_status`` instead. ``status`` only ever holds a value a human
explicitly set.

*The trail records the actor's Directus user UUID and nothing else.* The JWT
carries only ``id`` and ``role``; ``CurrentUser.email`` is currently a synthesized
placeholder (see ``app/security/directus_auth.py``). Writing that placeholder into
a revision-proof log would fabricate an identity, so the UUID is stored on its own
until real user data is fetched from Directus.
"""
import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.database import Base

# Kept in sync with the CheckConstraints below and the Literal aliases in
# app/schemas/audit.py. Three places, matching the house convention.
AUDIT_STATUSES = (
    "geplant",
    "in_vorbereitung",
    "in_durchfuehrung",
    "berichtet",
    "massnahmen_offen",
    "abgeschlossen",
    "verschoben",
    "abgesagt",
)
PHASE_STATUSES = ("offen", "in_arbeit", "erledigt", "nicht_zutreffend")
AUDIT_TYPES = ("intern", "extern")
AUDIT_CATEGORIES = ("system", "prozess", "produkt", "lieferant")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({','.join(repr(v) for v in values)})"


class AuditNormReference(Base):
    """One regulatory clause, maintained as master data by the user.

    Nothing in the application logic branches on these values — they are labels
    an auditor attaches to an audit. ``verified`` stays False until a human has
    checked the clause against the current consolidated regulation text; the
    seeded rows all start unverified on purpose.
    """

    __tablename__ = "audit_norm_references"
    __table_args__ = (
        UniqueConstraint(
            "regulation", "revision", "clause", name="uq_audit_norm_references_clause"
        ),
        Index("ix_audit_norm_references_regulation", "regulation"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    # e.g. "EN 9100", "EASA Part 21G", "AS9101"
    regulation: Mapped[str] = mapped_column(String(120), nullable=False)
    # e.g. "2018", "VO (EU) 2022/201"
    revision: Mapped[str] = mapped_column(String(60), nullable=False, server_default="")
    # e.g. "9.2", "21.A.139"
    clause: Mapped[str] = mapped_column(String(60), nullable=False)
    short_text: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    valid_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    verified: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class AuditPhaseTemplate(Base):
    """A reusable phase sequence. ``audit_category`` NULL means 'any category'."""

    __tablename__ = "audit_phase_templates"
    __table_args__ = (
        CheckConstraint(
            f"audit_category IS NULL OR {_in_list('audit_category', AUDIT_CATEGORIES)}",
            name="ck_audit_phase_templates_category",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    audit_category: Mapped[str | None] = mapped_column(String(16), nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    steps: Mapped[list["AuditPhaseTemplateStep"]] = relationship(
        "AuditPhaseTemplateStep",
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="AuditPhaseTemplateStep.position",
    )


class AuditPhaseTemplateStep(Base):
    """One ordered step in a phase template."""

    __tablename__ = "audit_phase_template_steps"
    __table_args__ = (
        UniqueConstraint(
            "template_id", "position", name="uq_audit_phase_template_steps_position"
        ),
        Index("ix_audit_phase_template_steps_template", "template_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audit_phase_templates.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    # A mandatory step cannot be set to 'nicht_zutreffend' without a reason.
    mandatory: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    template: Mapped["AuditPhaseTemplate"] = relationship(
        "AuditPhaseTemplate", back_populates="steps"
    )


class Audit(Base):
    """One audit — planned, in progress, or formally closed.

    ``scope_label`` is free text in Phase 1 (department or supplier name). It
    becomes an FK once the Abteilung/Lieferant entities land in Phase 2.
    """

    __tablename__ = "audits"
    __table_args__ = (
        CheckConstraint(_in_list("status", AUDIT_STATUSES), name="ck_audits_status"),
        CheckConstraint(
            _in_list("audit_type", AUDIT_TYPES), name="ck_audits_audit_type"
        ),
        CheckConstraint(
            _in_list("category", AUDIT_CATEGORIES), name="ck_audits_category"
        ),
        CheckConstraint(
            "priority BETWEEN 1 AND 3", name="ck_audits_priority"
        ),
        CheckConstraint(
            "planned_end IS NULL OR planned_start IS NULL OR planned_end >= planned_start",
            name="ck_audits_planned_range",
        ),
        UniqueConstraint("audit_number", name="uq_audits_audit_number"),
        Index("ix_audits_status", "status"),
        Index("ix_audits_planned_start", "planned_start"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    audit_number: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    audit_type: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(16), nullable=False)
    scope_label: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")
    objective: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    lead_auditor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    audit_team: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    planned_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    planned_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    # 1 = niedrig, 2 = mittel, 3 = hoch (risk-based priority).
    priority: Mapped[int] = mapped_column(Integer, nullable=False, server_default="2")
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, server_default="geplant"
    )
    # Which template the phases came from, kept for reference only. Phases are
    # copied at creation, so changing the template later never mutates an audit.
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audit_phase_templates.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    phases: Mapped[list["AuditPhase"]] = relationship(
        "AuditPhase",
        back_populates="audit",
        cascade="all, delete-orphan",
        order_by="AuditPhase.position",
    )
    norm_links: Mapped[list["AuditNormLink"]] = relationship(
        "AuditNormLink",
        back_populates="audit",
        cascade="all, delete-orphan",
    )


class AuditNormLink(Base):
    """Join row tying an audit to one norm reference."""

    __tablename__ = "audit_norm_links"
    __table_args__ = (
        UniqueConstraint("audit_id", "norm_reference_id", name="uq_audit_norm_links"),
        Index("ix_audit_norm_links_audit", "audit_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        nullable=False,
    )
    norm_reference_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # RESTRICT: a norm reference that is in use must be deactivated, not
        # deleted, or an audit would silently lose its regulatory basis.
        ForeignKey("audit_norm_references.id", ondelete="RESTRICT"),
        nullable=False,
    )

    audit: Mapped["Audit"] = relationship("Audit", back_populates="norm_links")
    norm_reference: Mapped["AuditNormReference"] = relationship("AuditNormReference")


class AuditPhase(Base):
    """One checklist phase belonging to an audit.

    Two invariants are enforced here, in the Pydantic schema, and re-checked in
    the PATCH handler (the ``*Patch`` models skip the model validator):

      - a mandatory phase marked 'nicht_zutreffend' needs a non-empty
        ``skip_reason`` — "kein Überspringen von Pflichtphasen ohne Begründung";
      - a phase marked 'erledigt' needs a ``completed_on`` date (the Ist-Termin).
    """

    __tablename__ = "audit_phases"
    __table_args__ = (
        CheckConstraint(
            _in_list("status", PHASE_STATUSES), name="ck_audit_phases_status"
        ),
        CheckConstraint(
            "status <> 'nicht_zutreffend' OR mandatory IS FALSE "
            "OR (skip_reason IS NOT NULL AND length(btrim(skip_reason)) > 0)",
            name="ck_audit_phases_skip_reason",
        ),
        CheckConstraint(
            "status <> 'erledigt' OR completed_on IS NOT NULL",
            name="ck_audit_phases_completed_on",
        ),
        UniqueConstraint("audit_id", "position", name="uq_audit_phases_position"),
        Index("ix_audit_phases_audit", "audit_id"),
        Index("ix_audit_phases_due_date", "due_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    audit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audits.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    mandatory: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, server_default="offen"
    )
    responsible: Mapped[str | None] = mapped_column(String(255), nullable=True)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    completed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    comment: Mapped[str] = mapped_column(Text, nullable=False, server_default="")
    skip_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    audit: Mapped["Audit"] = relationship("Audit", back_populates="phases")


class AuditTrailEntry(Base):
    """Append-only change log for the audit module.

    Written exclusively through ``app.services.audit_trail.record``; the router
    exposes no UPDATE or DELETE path. Note this is application-level
    immutability — a DB role with table privileges can still modify rows. Making
    that impossible (revoking UPDATE/DELETE, or a rule/trigger) is deferred and
    documented in docs/modules/audit.md.

    ``old_value``/``new_value`` are rendered as text rather than typed columns:
    the log has to survive schema changes to the entities it describes, so it
    stores a human-readable snapshot, not a foreign-keyed diff.
    """

    __tablename__ = "audit_trail_entries"
    __table_args__ = (
        CheckConstraint(
            "action IN ('create','update','delete','status_change','phase_skip')",
            name="ck_audit_trail_entries_action",
        ),
        Index("ix_audit_trail_entries_audit", "audit_id"),
        Index("ix_audit_trail_entries_entity", "entity_type", "entity_id"),
        Index("ix_audit_trail_entries_occurred_at", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    # Denormalised so an audit's full history is one indexed query. NULL for
    # master-data edits (norm references, templates) that belong to no audit.
    # No FK: the log must outlive the row it describes.
    audit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    entity_type: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    field: Mapped[str | None] = mapped_column(String(60), nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Justification captured when a mandatory phase is skipped.
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Directus user UUID from the JWT. Deliberately no email — see module docstring.
    actor_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False)

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
