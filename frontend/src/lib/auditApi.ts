/**
 * Audit-Modul API adapter — talks to the admin-gated FastAPI router at
 * /api/audit. All endpoints are JSON, so everything goes through the shared
 * `apiClient` (Bearer token + 401 silent-refresh).
 *
 * Phase 1 covers the core workflow: plan an audit, drive its phase checklist,
 * read the trail. Findings/CAPA and the year plan are not implemented yet.
 */
import { apiClient } from "@/lib/apiClient";

export type AuditStatus =
  | "geplant"
  | "in_vorbereitung"
  | "in_durchfuehrung"
  | "berichtet"
  | "massnahmen_offen"
  | "abgeschlossen"
  | "verschoben"
  | "abgesagt";

export type PhaseStatus = "offen" | "in_arbeit" | "erledigt" | "nicht_zutreffend";
export type AuditType = "intern" | "extern";
export type AuditCategory = "system" | "prozess" | "produkt" | "lieferant";

/** Status values a user can select. "überfällig" is absent on purpose — it is
 *  derived from due dates by the backend, never stored. */
export const AUDIT_STATUSES: readonly AuditStatus[] = [
  "geplant",
  "in_vorbereitung",
  "in_durchfuehrung",
  "berichtet",
  "massnahmen_offen",
  "abgeschlossen",
  "verschoben",
  "abgesagt",
];

export const PHASE_STATUSES: readonly PhaseStatus[] = [
  "offen",
  "in_arbeit",
  "erledigt",
  "nicht_zutreffend",
];

export const AUDIT_TYPES: readonly AuditType[] = ["intern", "extern"];
export const AUDIT_CATEGORIES: readonly AuditCategory[] = [
  "system",
  "prozess",
  "produkt",
  "lieferant",
];

/** Closing or cancelling an audit requires a note (backend returns 422 without one). */
export const STATUSES_REQUIRING_NOTE: readonly AuditStatus[] = [
  "abgeschlossen",
  "abgesagt",
];

export interface NormReference {
  id: string;
  regulation: string;
  revision: string;
  clause: string;
  short_text: string;
  valid_from: string | null;
  valid_to: string | null;
  verified: boolean;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface AuditPhase {
  id: string;
  position: number;
  title: string;
  description: string;
  mandatory: boolean;
  status: PhaseStatus;
  responsible: string | null;
  due_date: string | null;
  completed_on: string | null;
  comment: string;
  skip_reason: string | null;
  is_overdue: boolean;
  created_at: string;
  updated_at: string;
}

/** Derived server-side from the phase rows — nothing here is stored. */
export interface AuditProgress {
  phases_total: number;
  phases_relevant: number;
  phases_done: number;
  phases_not_applicable: number;
  percent: number;
  is_overdue: boolean;
  overdue_phase_titles: string[];
}

export interface Audit {
  id: string;
  audit_number: string;
  title: string;
  audit_type: AuditType;
  category: AuditCategory;
  scope_label: string;
  objective: string;
  lead_auditor: string | null;
  audit_team: string;
  planned_start: string | null;
  planned_end: string | null;
  priority: number;
  status: AuditStatus;
  template_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuditListItem extends Audit {
  progress: AuditProgress;
}

export interface AuditDetail extends Audit {
  phases: AuditPhase[];
  norm_references: NormReference[];
  progress: AuditProgress;
}

export interface PhaseTemplate {
  id: string;
  name: string;
  audit_category: AuditCategory | null;
  description: string;
  active: boolean;
}

export interface TrailEntry {
  id: string;
  audit_id: string | null;
  entity_type: string;
  entity_id: string;
  action: string;
  field: string | null;
  old_value: string | null;
  new_value: string | null;
  reason: string | null;
  actor_user_id: string;
  actor_role: string;
  occurred_at: string;
}

export interface AuditInput {
  audit_number: string;
  title: string;
  audit_type: AuditType;
  category: AuditCategory;
  scope_label?: string;
  objective?: string;
  lead_auditor?: string | null;
  audit_team?: string;
  planned_start?: string | null;
  planned_end?: string | null;
  priority?: number;
  template_id?: string | null;
  norm_reference_ids?: string[];
}

export interface PhasePatch {
  title?: string;
  description?: string;
  status?: PhaseStatus;
  responsible?: string | null;
  due_date?: string | null;
  completed_on?: string | null;
  comment?: string;
  skip_reason?: string | null;
}

export interface AuditListFilters {
  status?: string;
  audit_type?: string;
  category?: string;
  year?: number;
}

function query(filters: AuditListFilters): string {
  const params = new URLSearchParams();
  if (filters.status) params.set("status", filters.status);
  if (filters.audit_type) params.set("audit_type", filters.audit_type);
  if (filters.category) params.set("category", filters.category);
  if (filters.year) params.set("year", String(filters.year));
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export const auditApi = {
  listAudits: (filters: AuditListFilters = {}) =>
    apiClient<AuditListItem[]>(`/api/audit/audits${query(filters)}`),

  getAudit: (id: string) => apiClient<AuditDetail>(`/api/audit/audits/${id}`),

  createAudit: (body: AuditInput) =>
    apiClient<AuditDetail>("/api/audit/audits", {
      method: "POST",
      body: JSON.stringify(body),
    }),

  patchAudit: (id: string, body: Partial<AuditInput>) =>
    apiClient<AuditDetail>(`/api/audit/audits/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  /** Explicit, logged status transition. Never happens automatically. */
  changeStatus: (id: string, status: AuditStatus, note: string) =>
    apiClient<AuditDetail>(`/api/audit/audits/${id}/status`, {
      method: "POST",
      body: JSON.stringify({ status, note }),
    }),

  patchPhase: (phaseId: string, body: PhasePatch) =>
    apiClient<AuditPhase>(`/api/audit/phases/${phaseId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  getTrail: (auditId: string) =>
    apiClient<TrailEntry[]>(`/api/audit/audits/${auditId}/trail`),

  listNormReferences: () =>
    apiClient<NormReference[]>("/api/audit/norm-references"),

  patchNormReference: (id: string, body: Partial<NormReference>) =>
    apiClient<NormReference>(`/api/audit/norm-references/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),

  listTemplates: () => apiClient<PhaseTemplate[]>("/api/audit/templates"),
};
