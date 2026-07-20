"""v1.84: Audit-Modul — audits, phase checklist, Normmatrix, append-only trail

Seven additive tables for the audit module (Phase 1: core workflow). Chains onto
the current head (v1_83_email_office365); creates new tables only and touches no
existing data.

Seed data is inserted for two things a user cannot bootstrap from an empty UI:
the default 10-phase audit template, and the Normmatrix starting values. Every
seeded norm reference is written with ``verified = false`` — the clause numbers
come from the requirement document and have NOT been checked against the current
consolidated regulation text (EASA Easy Access Rules). Verifying them is a
deliberate human step in the UI.
"""
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "v1_84_audit"
down_revision = "v1_83_email_office365"
branch_labels = None
depends_on = None


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


def _uuid_pk() -> sa.Column:
    return sa.Column(
        "id",
        postgresql.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    ]


# The 10 standard phases from the requirement, section 3. Editable in the UI.
DEFAULT_PHASES = [
    ("Audit angelegt / beauftragt", "Scope, Typ, Norm-Referenz und Auditziel festgelegt"),
    ("Auditplan erstellt", "Auditor(en), Termin, Umfang, Kriterien"),
    ("Audit-Agenda erstellt", ""),
    ("Agenda übermittelt", "An Abteilung / Lieferant, mit Datum und Empfänger"),
    ("Audit durchgeführt", "Durchführungsdatum, Teilnehmer, Auditnotizen"),
    ("Auditbericht erstellt", ""),
    ("Auditbericht übermittelt", "An Auditierten / zur Freigabe"),
    ("Findings & Maßnahmen definiert", "Klassifizierung, Verantwortliche, Fristen"),
    ("Maßnahmen abgeschlossen", "Wirksamkeitsprüfung / Verifizierung"),
    ("Audit abgeschlossen", "Formaler Abschluss, Archivierung"),
]

# Startwerte der Normmatrix (requirement section 7). All unverified.
SEED_NORMS = [
    ("EN 9100", "2018", "9.1", "Überwachung, Messung, Analyse und Bewertung"),
    ("EN 9100", "2018", "9.2", "Internes Audit / Auditprogramm"),
    ("EN 9100", "2018", "9.3", "Managementbewertung"),
    ("EN 9100", "2018", "10.2", "Nichtkonformität und Korrekturmaßnahmen"),
    ("EN 9100", "2018", "8.4", "Extern bereitgestellte Prozesse, Produkte und DL"),
    ("EN 9110", "2018", "9.2", "Internes Audit / Auditprogramm"),
    ("EN 9110", "2018", "10.2", "Nichtkonformität und Korrekturmaßnahmen"),
    ("AS9101", "", "—", "Auditprozess (Zertifizierungsaudits)"),
    ("AS9104", "", "—", "Zertifizierungsschema"),
    ("EASA Part 21G", "VO (EU) 2022/201", "21.A.139",
     "Produktionsmanagementsystem, unabhängige Überwachungsfunktion"),
    ("EASA Part 21", "", "21.A.3A", "Ereignismeldung / Occurrence Reporting"),
    ("EASA Part 21J", "VO (EU) 2022/201", "21.A.239",
     "Entwicklungsmanagementsystem, unabhängige Überwachungsfunktion"),
    ("EASA Part 145", "", "145.A.200", "Managementsystem inkl. Compliance-Monitoring"),
    ("EASA Part 145", "", "145.A.202", "Internes Sicherheitsmeldesystem"),
]


def upgrade() -> None:
    op.create_table(
        "audit_norm_references",
        _uuid_pk(),
        sa.Column("regulation", sa.String(length=120), nullable=False),
        sa.Column("revision", sa.String(length=60), nullable=False, server_default=""),
        sa.Column("clause", sa.String(length=60), nullable=False),
        sa.Column("short_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        *_timestamps(),
        sa.UniqueConstraint(
            "regulation", "revision", "clause", name="uq_audit_norm_references_clause"
        ),
    )
    op.create_index(
        "ix_audit_norm_references_regulation", "audit_norm_references", ["regulation"]
    )

    op.create_table(
        "audit_phase_templates",
        _uuid_pk(),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("audit_category", sa.String(length=16), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("active", sa.Boolean(), nullable=False, server_default="true"),
        *_timestamps(),
        sa.CheckConstraint(
            f"audit_category IS NULL OR {_in_list('audit_category', AUDIT_CATEGORIES)}",
            name="ck_audit_phase_templates_category",
        ),
    )

    op.create_table(
        "audit_phase_template_steps",
        _uuid_pk(),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audit_phase_templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("mandatory", sa.Boolean(), nullable=False, server_default="true"),
        sa.UniqueConstraint(
            "template_id", "position", name="uq_audit_phase_template_steps_position"
        ),
    )
    op.create_index(
        "ix_audit_phase_template_steps_template",
        "audit_phase_template_steps",
        ["template_id"],
    )

    op.create_table(
        "audits",
        _uuid_pk(),
        sa.Column("audit_number", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("audit_type", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=16), nullable=False),
        sa.Column("scope_label", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("objective", sa.Text(), nullable=False, server_default=""),
        sa.Column("lead_auditor", sa.String(length=255), nullable=True),
        sa.Column("audit_team", sa.Text(), nullable=False, server_default=""),
        sa.Column("planned_start", sa.Date(), nullable=True),
        sa.Column("planned_end", sa.Date(), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("status", sa.String(length=24), nullable=False, server_default="geplant"),
        sa.Column(
            "template_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audit_phase_templates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        *_timestamps(),
        sa.CheckConstraint(_in_list("status", AUDIT_STATUSES), name="ck_audits_status"),
        sa.CheckConstraint(
            _in_list("audit_type", AUDIT_TYPES), name="ck_audits_audit_type"
        ),
        sa.CheckConstraint(
            _in_list("category", AUDIT_CATEGORIES), name="ck_audits_category"
        ),
        sa.CheckConstraint("priority BETWEEN 1 AND 3", name="ck_audits_priority"),
        sa.CheckConstraint(
            "planned_end IS NULL OR planned_start IS NULL OR planned_end >= planned_start",
            name="ck_audits_planned_range",
        ),
        sa.UniqueConstraint("audit_number", name="uq_audits_audit_number"),
    )
    op.create_index("ix_audits_status", "audits", ["status"])
    op.create_index("ix_audits_planned_start", "audits", ["planned_start"])

    op.create_table(
        "audit_norm_links",
        _uuid_pk(),
        sa.Column(
            "audit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "norm_reference_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audit_norm_references.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.UniqueConstraint("audit_id", "norm_reference_id", name="uq_audit_norm_links"),
    )
    op.create_index("ix_audit_norm_links_audit", "audit_norm_links", ["audit_id"])

    op.create_table(
        "audit_phases",
        _uuid_pk(),
        sa.Column(
            "audit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("audits.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("mandatory", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="offen"),
        sa.Column("responsible", sa.String(length=255), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("completed_on", sa.Date(), nullable=True),
        sa.Column("comment", sa.Text(), nullable=False, server_default=""),
        sa.Column("skip_reason", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            _in_list("status", PHASE_STATUSES), name="ck_audit_phases_status"
        ),
        sa.CheckConstraint(
            "status <> 'nicht_zutreffend' OR mandatory IS FALSE "
            "OR (skip_reason IS NOT NULL AND length(btrim(skip_reason)) > 0)",
            name="ck_audit_phases_skip_reason",
        ),
        sa.CheckConstraint(
            "status <> 'erledigt' OR completed_on IS NOT NULL",
            name="ck_audit_phases_completed_on",
        ),
        sa.UniqueConstraint("audit_id", "position", name="uq_audit_phases_position"),
    )
    op.create_index("ix_audit_phases_audit", "audit_phases", ["audit_id"])
    op.create_index("ix_audit_phases_due_date", "audit_phases", ["due_date"])

    op.create_table(
        "audit_trail_entries",
        _uuid_pk(),
        sa.Column("audit_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("entity_type", sa.String(length=40), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("field", sa.String(length=60), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("actor_role", sa.String(length=20), nullable=False),
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "action IN ('create','update','delete','status_change','phase_skip')",
            name="ck_audit_trail_entries_action",
        ),
    )
    op.create_index("ix_audit_trail_entries_audit", "audit_trail_entries", ["audit_id"])
    op.create_index(
        "ix_audit_trail_entries_entity",
        "audit_trail_entries",
        ["entity_type", "entity_id"],
    )
    op.create_index(
        "ix_audit_trail_entries_occurred_at", "audit_trail_entries", ["occurred_at"]
    )

    _seed()


def _seed() -> None:
    """Insert the default phase template and the Normmatrix starting values."""
    conn = op.get_bind()

    template_id = conn.execute(
        sa.text(
            "INSERT INTO audit_phase_templates (name, audit_category, description) "
            "VALUES (:name, NULL, :description) RETURNING id"
        ),
        {
            "name": "Standard-Auditablauf (10 Phasen)",
            "description": (
                "Standardvorlage für alle Auditarten. Kopiervorlage — Änderungen "
                "wirken nur auf neu angelegte Audits."
            ),
        },
    ).scalar_one()

    for position, (title, description) in enumerate(DEFAULT_PHASES, start=1):
        conn.execute(
            sa.text(
                "INSERT INTO audit_phase_template_steps "
                "(template_id, position, title, description, mandatory) "
                "VALUES (:template_id, :position, :title, :description, true)"
            ),
            {
                "template_id": template_id,
                "position": position,
                "title": title,
                "description": description,
            },
        )

    for regulation, revision_, clause, short_text in SEED_NORMS:
        conn.execute(
            sa.text(
                "INSERT INTO audit_norm_references "
                "(regulation, revision, clause, short_text, verified) "
                "VALUES (:regulation, :revision, :clause, :short_text, false)"
            ),
            {
                "regulation": regulation,
                "revision": revision_,
                "clause": clause,
                "short_text": short_text,
            },
        )


def downgrade() -> None:
    op.drop_index("ix_audit_trail_entries_occurred_at", table_name="audit_trail_entries")
    op.drop_index("ix_audit_trail_entries_entity", table_name="audit_trail_entries")
    op.drop_index("ix_audit_trail_entries_audit", table_name="audit_trail_entries")
    op.drop_table("audit_trail_entries")
    op.drop_index("ix_audit_phases_due_date", table_name="audit_phases")
    op.drop_index("ix_audit_phases_audit", table_name="audit_phases")
    op.drop_table("audit_phases")
    op.drop_index("ix_audit_norm_links_audit", table_name="audit_norm_links")
    op.drop_table("audit_norm_links")
    op.drop_index("ix_audits_planned_start", table_name="audits")
    op.drop_index("ix_audits_status", table_name="audits")
    op.drop_table("audits")
    op.drop_index(
        "ix_audit_phase_template_steps_template", table_name="audit_phase_template_steps"
    )
    op.drop_table("audit_phase_template_steps")
    op.drop_table("audit_phase_templates")
    op.drop_index(
        "ix_audit_norm_references_regulation", table_name="audit_norm_references"
    )
    op.drop_table("audit_norm_references")
