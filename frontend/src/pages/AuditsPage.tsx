/**
 * Auditübersicht — list of all audits with derived progress and filters.
 *
 * Admin-only (gated in App.tsx and enforced by the backend router). Follows the
 * MaintenanceMachinesPage shape: inline useQuery/useMutation, a plain useState
 * draft for the create form, and the shared DataTable.
 */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import { toast } from "sonner";

import { DataTable, type DataTableColumn } from "@/components/DataTable";
import {
  AuditStatusBadge,
  OverdueBadge,
  ProgressBar,
} from "@/components/audit/AuditStatusBadge";
import {
  AUDIT_CATEGORIES,
  AUDIT_STATUSES,
  AUDIT_TYPES,
  auditApi,
  type AuditCategory,
  type AuditInput,
  type AuditListItem,
  type AuditType,
} from "@/lib/auditApi";

type AuditRow = AuditListItem & Record<string, unknown>;

const EMPTY: AuditInput = {
  audit_number: "",
  title: "",
  audit_type: "intern",
  category: "system",
  scope_label: "",
  planned_start: "",
  planned_end: "",
  lead_auditor: "",
  template_id: "",
};

export function AuditsPage() {
  const { t } = useTranslation();
  const [, setLocation] = useLocation();
  const qc = useQueryClient();

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [draft, setDraft] = useState<AuditInput>(EMPTY);

  const audits = useQuery({
    queryKey: ["audit", "audits", statusFilter, typeFilter],
    queryFn: () =>
      auditApi.listAudits({
        status: statusFilter || undefined,
        audit_type: typeFilter || undefined,
      }),
  });

  const templates = useQuery({
    queryKey: ["audit", "templates"],
    queryFn: () => auditApi.listTemplates(),
  });

  const create = useMutation({
    mutationFn: () => {
      // Empty strings are the form's "not set"; the API wants null/absent.
      const body: AuditInput = {
        ...draft,
        planned_start: draft.planned_start || null,
        planned_end: draft.planned_end || null,
        lead_auditor: draft.lead_auditor || null,
        template_id: draft.template_id || null,
      };
      return auditApi.createAudit(body);
    },
    onSuccess: (created) => {
      toast.success(t("audit.created"));
      setDraft(EMPTY);
      setShowForm(false);
      qc.invalidateQueries({ queryKey: ["audit", "audits"] });
      setLocation(`/audit/${created.id}`);
    },
    onError: (e) => toast.error(String(e)),
  });

  const rows = useMemo<AuditRow[]>(() => {
    const term = search.trim().toLowerCase();
    const all = (audits.data ?? []) as AuditRow[];
    if (!term) return all;
    return all.filter((a) =>
      [a.audit_number, a.title, a.scope_label, a.lead_auditor ?? ""]
        .join(" ")
        .toLowerCase()
        .includes(term),
    );
  }, [audits.data, search]);

  const columns: DataTableColumn<AuditRow>[] = [
    { key: "audit_number", header: t("audit.col.number"), sortable: true },
    { key: "title", header: t("audit.col.title"), sortable: true },
    {
      key: "audit_type",
      header: t("audit.col.type"),
      sortable: true,
      cell: (row) => t(`audit.type.${row.audit_type}`),
    },
    {
      key: "category",
      header: t("audit.col.category"),
      sortable: true,
      cell: (row) => t(`audit.category.${row.category}`),
    },
    { key: "scope_label", header: t("audit.col.scope"), sortable: true },
    { key: "planned_start", header: t("audit.col.plannedStart"), sortable: true },
    {
      key: "status",
      header: t("audit.col.status"),
      cell: (row) => (
        <div className="flex items-center gap-1.5">
          <AuditStatusBadge status={row.status} />
          {row.progress.is_overdue && <OverdueBadge />}
        </div>
      ),
    },
    {
      key: "progress",
      header: t("audit.col.progress"),
      cell: (row) => (
        <ProgressBar
          done={row.progress.phases_done}
          relevant={row.progress.phases_relevant}
          percent={row.progress.percent}
          overdue={row.progress.is_overdue}
        />
      ),
    },
  ];

  const field = (
    key: keyof AuditInput,
    label: string,
    type: "text" | "date" = "text",
  ) => (
    <label className="flex flex-col gap-1 text-sm">
      <span className="text-muted-foreground">{label}</span>
      <input
        type={type}
        className="border rounded px-2 py-1.5"
        value={(draft[key] as string) ?? ""}
        onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
      />
    </label>
  );

  return (
    <div className="max-w-6xl mx-auto px-6 py-6">
      <h1 className="text-2xl font-semibold mb-1">{t("audit.heading")}</h1>
      <p className="text-sm text-muted-foreground mb-6">{t("audit.subheading")}</p>

      <div className="flex flex-wrap items-end gap-3 mb-4">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">{t("audit.filter.status")}</span>
          <select
            className="border rounded px-2 py-1.5"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">{t("audit.filter.all")}</option>
            {AUDIT_STATUSES.map((s) => (
              <option key={s} value={s}>
                {t(`audit.status.${s}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">{t("audit.filter.type")}</span>
          <select
            className="border rounded px-2 py-1.5"
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
          >
            <option value="">{t("audit.filter.all")}</option>
            {AUDIT_TYPES.map((s) => (
              <option key={s} value={s}>
                {t(`audit.type.${s}`)}
              </option>
            ))}
          </select>
        </label>
        <button
          type="button"
          className="ml-auto border rounded px-3 py-1.5 text-sm hover:bg-accent"
          onClick={() => setShowForm((v) => !v)}
        >
          {showForm ? t("audit.form.cancel") : t("audit.new")}
        </button>
      </div>

      {showForm && (
        <div className="border rounded-lg p-4 mb-6 bg-card">
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {field("audit_number", t("audit.col.number"))}
            {field("title", t("audit.col.title"))}
            {field("scope_label", t("audit.col.scope"))}
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-muted-foreground">{t("audit.col.type")}</span>
              <select
                className="border rounded px-2 py-1.5"
                value={draft.audit_type}
                onChange={(e) =>
                  setDraft({ ...draft, audit_type: e.target.value as AuditType })
                }
              >
                {AUDIT_TYPES.map((s) => (
                  <option key={s} value={s}>
                    {t(`audit.type.${s}`)}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-muted-foreground">{t("audit.col.category")}</span>
              <select
                className="border rounded px-2 py-1.5"
                value={draft.category}
                onChange={(e) =>
                  setDraft({ ...draft, category: e.target.value as AuditCategory })
                }
              >
                {AUDIT_CATEGORIES.map((s) => (
                  <option key={s} value={s}>
                    {t(`audit.category.${s}`)}
                  </option>
                ))}
              </select>
            </label>
            {field("lead_auditor", t("audit.col.leadAuditor"))}
            {field("planned_start", t("audit.col.plannedStart"), "date")}
            {field("planned_end", t("audit.col.plannedEnd"), "date")}
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-muted-foreground">{t("audit.form.template")}</span>
              <select
                className="border rounded px-2 py-1.5"
                value={draft.template_id ?? ""}
                onChange={(e) => setDraft({ ...draft, template_id: e.target.value })}
              >
                <option value="">{t("audit.form.noTemplate")}</option>
                {(templates.data ?? []).map((tpl) => (
                  <option key={tpl.id} value={tpl.id}>
                    {tpl.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <p className="text-xs text-muted-foreground mt-3">
            {t("audit.form.templateHint")}
          </p>
          <div className="mt-4">
            <button
              type="button"
              className="border rounded px-3 py-1.5 text-sm bg-primary text-primary-foreground disabled:opacity-50"
              disabled={
                !draft.audit_number.trim() || !draft.title.trim() || create.isPending
              }
              onClick={() => create.mutate()}
            >
              {t("audit.form.save")}
            </button>
          </div>
        </div>
      )}

      <DataTable
        rows={rows}
        rowKey={(row) => row.id}
        columns={columns}
        isLoading={audits.isLoading}
        emptyText={t("audit.empty")}
        search={{ value: search, onChange: setSearch }}
        initialSort={{ key: "planned_start", dir: "desc" }}
        onRowClick={(row) => setLocation(`/audit/${row.id}`)}
        minWidth={1000}
        card={false}
      />
    </div>
  );
}
