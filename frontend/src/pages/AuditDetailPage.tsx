/**
 * Audit-Detailseite — the phase checklist is the centrepiece (requirement §3).
 *
 * Each phase row is editable inline: status, responsible, Soll-/Ist-Termin and
 * comment. Two rules are mirrored from the backend so the user gets an
 * immediate answer instead of a 422:
 *
 *   - a mandatory phase cannot be set to "nicht zutreffend" without a reason;
 *   - the audit status is only ever changed by an explicit action, never
 *     derived from the checklist being complete.
 *
 * The trail panel is read-only by construction — there is no edit or delete
 * affordance anywhere, matching the append-only API.
 */
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link, useRoute } from "wouter";
import { toast } from "sonner";

import {
  AuditStatusBadge,
  OverdueBadge,
  PhaseStatusBadge,
  ProgressBar,
} from "@/components/audit/AuditStatusBadge";
import {
  AUDIT_STATUSES,
  PHASE_STATUSES,
  STATUSES_REQUIRING_NOTE,
  auditApi,
  type AuditDetail,
  type AuditPhase,
  type AuditStatus,
  type PhasePatch,
  type PhaseStatus,
} from "@/lib/auditApi";

const auditKey = (id: string) => ["audit", "audit", id] as const;
const trailKey = (id: string) => ["audit", "trail", id] as const;

export function AuditDetailPage() {
  const { t, i18n } = useTranslation();
  const qc = useQueryClient();
  const [, params] = useRoute("/quality/audit/:id");
  const auditId = params?.id ?? "";

  const audit = useQuery({
    queryKey: auditKey(auditId),
    queryFn: () => auditApi.getAudit(auditId),
    enabled: Boolean(auditId),
  });

  const trail = useQuery({
    queryKey: trailKey(auditId),
    queryFn: () => auditApi.getTrail(auditId),
    enabled: Boolean(auditId),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: auditKey(auditId) });
    qc.invalidateQueries({ queryKey: trailKey(auditId) });
    qc.invalidateQueries({ queryKey: ["audit", "audits"] });
  };

  const patchPhase = useMutation({
    mutationFn: ({ id, body }: { id: string; body: PhasePatch }) =>
      auditApi.patchPhase(id, body),
    onSuccess: () => {
      toast.success(t("audit.phase.saved"));
      invalidate();
    },
    onError: (e) => toast.error(String(e)),
  });

  const changeStatus = useMutation({
    mutationFn: ({ status, note }: { status: AuditStatus; note: string }) =>
      auditApi.changeStatus(auditId, status, note),
    onSuccess: () => {
      toast.success(t("audit.statusChanged"));
      invalidate();
    },
    onError: (e) => toast.error(String(e)),
  });

  if (audit.isLoading) {
    return <div className="max-w-5xl mx-auto px-6 py-6">{t("table.loading")}</div>;
  }
  if (!audit.data) {
    return (
      <div className="max-w-5xl mx-auto px-6 py-6">{t("audit.detail.notFound")}</div>
    );
  }

  const data: AuditDetail = audit.data;
  const locale = i18n.language === "de" ? "de-DE" : "en-US";

  return (
    <div className="max-w-5xl mx-auto px-6 py-6">
      <Link href="/quality/audit" className="text-sm text-muted-foreground hover:underline">
        ← {t("audit.detail.back")}
      </Link>

      <div className="flex flex-wrap items-start justify-between gap-4 mt-3 mb-6">
        <div>
          <h1 className="text-2xl font-semibold">
            {data.audit_number} — {data.title}
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            {t(`audit.type.${data.audit_type}`)} ·{" "}
            {data.categories.map((c) => t(`audit.category.${c}`)).join(" + ")}
            {data.scope_label && ` · ${data.scope_label}`}
            {data.lead_auditor && ` · ${data.lead_auditor}`}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <AuditStatusBadge status={data.status} />
          {data.progress.is_overdue && <OverdueBadge />}
        </div>
      </div>

      {/* Progress + explicit status control */}
      <section className="border rounded-lg p-4 mb-6 bg-card">
        <div className="flex flex-wrap items-center gap-6">
          <div className="flex-1 min-w-[220px]">
            <div className="text-sm font-medium mb-2">
              {t("audit.progress.heading", {
                done: data.progress.phases_done,
                total: data.progress.phases_relevant,
              })}
            </div>
            <ProgressBar
              done={data.progress.phases_done}
              relevant={data.progress.phases_relevant}
              percent={data.progress.percent}
              overdue={data.progress.is_overdue}
            />
            {data.progress.phases_not_applicable > 0 && (
              <p className="text-xs text-muted-foreground mt-2">
                {t("audit.progress.notApplicable", {
                  count: data.progress.phases_not_applicable,
                })}
              </p>
            )}
          </div>
          <StatusChanger
            current={data.status}
            pending={changeStatus.isPending}
            onSubmit={(status, note) => changeStatus.mutate({ status, note })}
          />
        </div>
        {data.progress.overdue_phase_titles.length > 0 && (
          <p className="text-xs text-red-700 mt-3">
            {t("audit.progress.overduePhases", {
              titles: data.progress.overdue_phase_titles.join(", "),
            })}
          </p>
        )}
      </section>

      {/* Norm references */}
      {data.norm_references.length > 0 && (
        <section className="mb-6">
          <h2 className="text-lg font-medium mb-2">{t("audit.norms.heading")}</h2>
          <ul className="flex flex-wrap gap-2">
            {data.norm_references.map((n) => (
              <li
                key={n.id}
                className="text-xs border rounded px-2 py-1 bg-muted/40"
                title={n.short_text}
              >
                {n.regulation} {n.clause}
                {!n.verified && (
                  <span className="ml-1 text-amber-700">
                    · {t("audit.norms.unverified")}
                  </span>
                )}
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Phase checklist — the centrepiece */}
      <section className="mb-8">
        <h2 className="text-lg font-medium mb-3">{t("audit.phases.heading")}</h2>
        {data.phases.length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("audit.phases.empty")}</p>
        ) : (
          <ol className="space-y-2">
            {data.phases.map((phase) => (
              <PhaseRow
                key={phase.id}
                phase={phase}
                pending={patchPhase.isPending}
                onSave={(body) => patchPhase.mutate({ id: phase.id, body })}
              />
            ))}
          </ol>
        )}
      </section>

      {/* Append-only trail */}
      <section>
        <h2 className="text-lg font-medium mb-1">{t("audit.trail.heading")}</h2>
        <p className="text-xs text-muted-foreground mb-3">{t("audit.trail.hint")}</p>
        {trail.isLoading ? (
          <p className="text-sm text-muted-foreground">{t("table.loading")}</p>
        ) : (trail.data ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("audit.trail.empty")}</p>
        ) : (
          <ul className="space-y-1 text-xs">
            {(trail.data ?? []).map((e) => (
              <li key={e.id} className="border rounded px-3 py-2 bg-muted/30">
                <span className="text-muted-foreground tabular-nums">
                  {new Date(e.occurred_at).toLocaleString(locale)}
                </span>{" "}
                · <span className="font-medium">{t(`audit.trail.action.${e.action}`)}</span>
                {e.field && <> · {e.field}</>}
                {(e.old_value || e.new_value) && (
                  <>
                    {" "}
                    · <span className="line-through opacity-60">{e.old_value ?? "—"}</span>{" "}
                    → <span>{e.new_value ?? "—"}</span>
                  </>
                )}
                {e.reason && (
                  <div className="mt-1 italic text-muted-foreground">
                    {t("audit.trail.reason")}: {e.reason}
                  </div>
                )}
                <div className="mt-1 text-muted-foreground">
                  {t("audit.trail.actor")}: {e.actor_user_id} ({e.actor_role})
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}

/** Explicit status transition. Closing/cancelling requires a note. */
function StatusChanger({
  current,
  pending,
  onSubmit,
}: {
  current: AuditStatus;
  pending: boolean;
  onSubmit: (status: AuditStatus, note: string) => void;
}) {
  const { t } = useTranslation();
  const [status, setStatus] = useState<AuditStatus>(current);
  const [note, setNote] = useState("");

  const noteRequired = STATUSES_REQUIRING_NOTE.includes(status);
  const blocked = status === current || (noteRequired && !note.trim()) || pending;

  return (
    <div className="flex flex-col gap-2 min-w-[260px]">
      <label className="flex flex-col gap-1 text-sm">
        <span className="text-muted-foreground">{t("audit.statusChange.label")}</span>
        <select
          className="border rounded px-2 py-1.5"
          value={status}
          onChange={(e) => setStatus(e.target.value as AuditStatus)}
        >
          {AUDIT_STATUSES.map((s) => (
            <option key={s} value={s}>
              {t(`audit.status.${s}`)}
            </option>
          ))}
        </select>
      </label>
      <input
        className="border rounded px-2 py-1.5 text-sm"
        placeholder={
          noteRequired
            ? t("audit.statusChange.notePlaceholderRequired")
            : t("audit.statusChange.notePlaceholder")
        }
        value={note}
        onChange={(e) => setNote(e.target.value)}
      />
      <button
        type="button"
        className="border rounded px-3 py-1.5 text-sm bg-primary text-primary-foreground disabled:opacity-50"
        disabled={blocked}
        onClick={() => {
          onSubmit(status, note);
          setNote("");
        }}
      >
        {t("audit.statusChange.apply")}
      </button>
    </div>
  );
}

/** One checklist phase, editable inline. */
function PhaseRow({
  phase,
  pending,
  onSave,
}: {
  phase: AuditPhase;
  pending: boolean;
  onSave: (body: PhasePatch) => void;
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<PhasePatch>({
    status: phase.status,
    responsible: phase.responsible ?? "",
    due_date: phase.due_date ?? "",
    completed_on: phase.completed_on ?? "",
    comment: phase.comment,
    skip_reason: phase.skip_reason ?? "",
  });

  // Mirrors the backend rule so the user is told before the request is sent.
  const needsReason =
    draft.status === "nicht_zutreffend" &&
    phase.mandatory &&
    !(draft.skip_reason ?? "").trim();

  return (
    <li className="border rounded-lg bg-card">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3">
        <span className="text-xs tabular-nums text-muted-foreground w-6">
          {phase.position}.
        </span>
        <span className="flex-1 min-w-[200px] text-sm font-medium">
          {phase.title}
          {phase.mandatory && (
            <span className="ml-1 text-red-600" title={t("audit.phase.mandatory")}>
              *
            </span>
          )}
        </span>
        <PhaseStatusBadge status={phase.status} />
        {phase.is_overdue && <OverdueBadge />}
        {phase.due_date && (
          <span className="text-xs text-muted-foreground tabular-nums">
            {t("audit.phase.due")}: {phase.due_date}
          </span>
        )}
        <button
          type="button"
          className="text-xs border rounded px-2 py-1 hover:bg-accent"
          onClick={() => setOpen((v) => !v)}
        >
          {open ? t("audit.phase.close") : t("audit.phase.edit")}
        </button>
      </div>

      {open && (
        <div className="border-t px-4 py-3">
          {phase.description && (
            <p className="text-xs text-muted-foreground mb-3">{phase.description}</p>
          )}
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-muted-foreground">{t("audit.phase.status")}</span>
              <select
                className="border rounded px-2 py-1.5"
                value={draft.status}
                onChange={(e) =>
                  setDraft({ ...draft, status: e.target.value as PhaseStatus })
                }
              >
                {PHASE_STATUSES.map((s) => (
                  <option key={s} value={s}>
                    {t(`audit.phaseStatus.${s}`)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-muted-foreground">
                {t("audit.phase.responsible")}
              </span>
              <input
                className="border rounded px-2 py-1.5"
                value={draft.responsible ?? ""}
                onChange={(e) => setDraft({ ...draft, responsible: e.target.value })}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-muted-foreground">{t("audit.phase.due")}</span>
              <input
                type="date"
                className="border rounded px-2 py-1.5"
                value={draft.due_date ?? ""}
                onChange={(e) => setDraft({ ...draft, due_date: e.target.value })}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-muted-foreground">{t("audit.phase.completedOn")}</span>
              <input
                type="date"
                className="border rounded px-2 py-1.5"
                value={draft.completed_on ?? ""}
                onChange={(e) => setDraft({ ...draft, completed_on: e.target.value })}
              />
            </label>
            <label className="flex flex-col gap-1 text-sm sm:col-span-2">
              <span className="text-muted-foreground">{t("audit.phase.comment")}</span>
              <input
                className="border rounded px-2 py-1.5"
                value={draft.comment ?? ""}
                onChange={(e) => setDraft({ ...draft, comment: e.target.value })}
              />
            </label>
            {draft.status === "nicht_zutreffend" && (
              <label className="flex flex-col gap-1 text-sm sm:col-span-2 lg:col-span-3">
                <span className="text-muted-foreground">
                  {t("audit.phase.skipReason")}
                  {phase.mandatory && <span className="text-red-600"> *</span>}
                </span>
                <input
                  className="border rounded px-2 py-1.5"
                  value={draft.skip_reason ?? ""}
                  onChange={(e) => setDraft({ ...draft, skip_reason: e.target.value })}
                />
                {needsReason && (
                  <span className="text-xs text-red-700">
                    {t("audit.phase.skipReasonRequired")}
                  </span>
                )}
              </label>
            )}
          </div>
          <div className="mt-4">
            <button
              type="button"
              className="border rounded px-3 py-1.5 text-sm bg-primary text-primary-foreground disabled:opacity-50"
              disabled={needsReason || pending}
              onClick={() =>
                onSave({
                  ...draft,
                  responsible: draft.responsible || null,
                  due_date: draft.due_date || null,
                  completed_on: draft.completed_on || null,
                  skip_reason: draft.skip_reason || null,
                })
              }
            >
              {t("audit.phase.save")}
            </button>
          </div>
        </div>
      )}
    </li>
  );
}
