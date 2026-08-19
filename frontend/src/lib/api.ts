import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { readItems } from "@directus/sdk";

import { apiClient } from "./apiClient";
import { directus } from "./directusClient";
import { toApiError } from "./toApiError";

export interface ValidationErrorDetail {
  row: number;
  column: string;
  message: string;
}

export interface UploadResponse {
  id: number;
  filename: string;
  row_count: number;
  error_count: number;
  status: "success" | "partial" | "failed";
  errors: ValidationErrorDetail[];
}

export interface UploadBatchSummary {
  id: number;
  filename: string;
  uploaded_at: string;
  row_count: number;
  error_count: number;
  status: "success" | "partial" | "failed";
  kind:
    | "orders"
    | "contacts"
    | "quality"
    | "interessenten"
    | "offers"
    | "revenues"
    | "auftraege"
    | "deliveries"
    | "delivery_reliability"
    | "tippspiel"
    | "goods_receipts"
    | "material_movements"
    | "material_prices"
    | "stock_prices";
}

export async function uploadFile(file: File): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient<UploadResponse>("/api/upload", {
    method: "POST",
    body: formData,
  });
}

// v1.41 — Kontakte (sales contact log) upload (v1.42: dropped
// unmapped_tokens — sales reps are identified by the Wer token directly,
// no Personio binding remains).
export interface ContactsUploadResponse {
  rows_inserted: number;
  rows_replaced: number;
  date_range_from: string | null;
  date_range_to: string | null;
}

export async function uploadContactsFile(file: File): Promise<ContactsUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient<ContactsUploadResponse>("/api/upload-contacts", {
    method: "POST",
    body: formData,
  });
}

export async function getUploads(): Promise<UploadBatchSummary[]> {
  // v1.23 C-1: Directus SDK replacement for GET /api/uploads. Field list
  // mirrors the Viewer permission row in directus/bootstrap-roles.sh and
  // the UploadBatchSummary type above — keep all three in lockstep.
  try {
    const rows = await directus.request(
      readItems("upload_batches", {
        sort: ["-uploaded_at"],
        fields: [
          "id",
          "filename",
          "uploaded_at",
          "row_count",
          "error_count",
          "status",
          "kind",
        ],
      }),
    );
    return rows as UploadBatchSummary[];
  } catch (e) {
    throw toApiError(e);
  }
}

export async function deleteUpload(id: number): Promise<void> {
  await apiClient<void>(`/api/uploads/${id}`, { method: "DELETE" });
}

/**
 * Phase 8 nullable sibling for the dual-delta KPI cards. Matches the
 * `KpiSummaryComparison` Pydantic model on the backend — three numeric
 * fields, no further nesting.
 */
export interface KpiSummaryComparison {
  total_revenue: number;
  avg_order_value: number;
  total_orders: number;
}

export interface KpiSummary {
  total_revenue: number;
  avg_order_value: number;
  total_orders: number;
  /** Null when no baseline exists (thisYear, allTime, or zero-row window). */
  previous_period: KpiSummaryComparison | null;
  /** Null when no prior-year data exists for the requested window. */
  previous_year: KpiSummaryComparison | null;
}

import type { PrevBounds } from "./prevBounds.ts";

export interface ChartPoint {
  date: string; // ISO date string "YYYY-MM-DD" (bucket-truncated by granularity)
  // `revenue` is null only in the `previous` series of ChartResponse for
  // missing trailing buckets (CHART-03). The `current` series always
  // carries concrete numeric revenues.
  revenue: number | null;
}

/**
 * Phase 8 wrapped chart response. The bare `ChartPoint[]` shape shipped in
 * v1.0/v1.1 has been replaced with `{ current, previous }` so the endpoint
 * can optionally carry an overlay series aligned positionally to `current`.
 * `previous` is null unless the caller requests a comparison via the
 * `comparison` + `prev_start` + `prev_end` query params (not yet wired in
 * this adapter — that's Phase 10's concern).
 */
export interface ChartResponse {
  current: ChartPoint[];
  previous: ChartPoint[] | null;
}

import type { ComparisonMode } from "./chartComparisonMode.ts";

export interface LatestUploadResponse {
  uploaded_at: string | null;
}

export async function fetchKpiSummary(
  start?: string,
  end?: string,
  prev?: PrevBounds,
): Promise<KpiSummary> {
  const params = new URLSearchParams();
  if (start) params.set("start_date", start);
  if (end) params.set("end_date", end);
  if (prev?.prev_period_start)
    params.set("prev_period_start", prev.prev_period_start);
  if (prev?.prev_period_end)
    params.set("prev_period_end", prev.prev_period_end);
  if (prev?.prev_year_start)
    params.set("prev_year_start", prev.prev_year_start);
  if (prev?.prev_year_end) params.set("prev_year_end", prev.prev_year_end);
  const qs = params.toString();
  return apiClient<KpiSummary>(`/api/kpis${qs ? `?${qs}` : ""}`);
}

export async function fetchChartData(
  start: string | undefined,
  end: string | undefined,
  granularity: "daily" | "weekly" | "monthly" = "monthly",
  comparison?: ComparisonMode,
  prevStart?: string,
  prevEnd?: string,
): Promise<ChartResponse> {
  const params = new URLSearchParams({ granularity });
  if (start) params.set("start_date", start);
  if (end) params.set("end_date", end);
  if (comparison && comparison !== "none") {
    params.set("comparison", comparison);
    if (prevStart) params.set("prev_start", prevStart);
    if (prevEnd) params.set("prev_end", prevEnd);
  }
  return apiClient<ChartResponse>(`/api/kpis/chart?${params.toString()}`);
}

export async function fetchLatestUpload(): Promise<LatestUploadResponse> {
  return apiClient<LatestUploadResponse>("/api/kpis/latest-upload");
}

export interface Settings {
  color_primary: string;
  color_accent: string;
  color_background: string;
  color_foreground: string;
  color_muted: string;
  color_destructive: string;
  app_name: string;
  logo_url: string | null;
  logo_updated_at: string | null;
  // Phase 13 Personio fields
  personio_has_credentials: boolean;
  personio_sync_interval_h: number;
  personio_sick_leave_type_id: number[];
  personio_production_dept: string[];
  personio_skill_attr_key: string[];
  // HR KPI targets
  target_overtime_ratio: number | null;
  target_sick_leave_ratio: number | null;
  target_fluctuation: number | null;
  target_revenue_per_employee: number | null;
  // v1.66 Quality targets — complaint rates are fractions (0.02 = 2 %),
  // finding counts are integer thresholds shown as ReferenceLines.
  target_complaint_rate_customer: number | null;
  target_complaint_rate_internal: number | null;
  target_complaint_rate_supplier: number | null;
  target_complaint_rate_subcontractor: number | null;
  target_audit_findings_level1: number | null;
  target_audit_findings_level2: number | null;
  target_inspection_large: number | null;
  target_inspection_small: number | null;
  // v1.71 / v1.72 — Finance KPI targets (cost ratios as fractions)
  target_material_cost_ratio: number | null;
  target_personnel_cost_ratio: number | null;
  target_produktion_verzug: number | null;
  // v1.55 — Sales-dashboard weekly targets
  target_sales_erstkontakte: number | null;
  target_sales_interessenten: number | null;
  target_sales_besuche: number | null;
  target_sales_angebote_eur: number | null;
  // v1.56 — €/week/rep goal on the OrdersDistributionCard headline tile.
  target_sales_orders_per_rep_eur: number | null;
  // Phase 39-02 — Sensor config read-only surfaces.
  // Decimal serialized as string; parse via Number() at render (never store as number).
  // Admin write endpoints arrive Phase 40 (SettingsUpdatePayload intentionally NOT extended).
  sensor_poll_interval_s: number;
  sensor_temperature_min: string | null;
  sensor_temperature_max: string | null;
  sensor_humidity_min: string | null;
  sensor_humidity_max: string | null;
  // v1.57 World Cup signage — key is write-only, only the boolean is exposed.
  worldcup_has_api_key: boolean;
  worldcup_refresh_seconds: number;
  // ATR fileserver — password is write-only, only the boolean is exposed.
  atr_smb_host: string | null;
  atr_smb_share: string | null;
  atr_smb_domain: string | null;
  atr_smb_user: string | null;
  atr_smb_has_password: boolean;
  atr_input_path: string | null;
  atr_output_path: string | null;
  atr_archive_path: string | null;
  atr_scan_interval_s: number;
  atr_auto_mode: boolean;
  // v1.83 E-Mail (Office 365 / Graph) — client secret is write-only, only the
  // boolean is exposed.
  email_tenant_id: string | null;
  email_client_id: string | null;
  email_sender_address: string | null;
  email_sender_name: string | null;
  email_has_secret: boolean;
  email_enabled: boolean;
  // 'app' (client-credentials) or 'delegated' (device-code sign-in).
  email_auth_mode: "app" | "delegated";
  email_delegated_account: string | null;
  email_delegated_connected: boolean;
  // v1.102 — Personio-Rückschreiben (inert bis Freischaltung)
  personio_writeback_enabled?: boolean;
  personio_writeback_kategorie_id?: string | null;
}

export async function fetchSettings(): Promise<Settings> {
  return apiClient<Settings>("/api/settings");
}

/**
 * Payload for PUT /api/settings. Exactly 8 required fields — logo bytes have their
 * own endpoint (Phase 4 D-05). All color_* fields must be in canonical
 * `oklch(L C H)` format; the backend's _OKLCH_RE regex rejects hex and
 * any string containing `;`, `}`, `{`, `url(`, `expression(`, or quotes.
 * Phase 13: Personio fields are optional — undefined means "don't change".
 */
export interface SettingsUpdatePayload {
  color_primary: string;
  color_accent: string;
  color_background: string;
  color_foreground: string;
  color_muted: string;
  color_destructive: string;
  app_name: string;
  // Phase 13 Personio fields — undefined means "don't change"
  personio_client_id?: string;
  personio_client_secret?: string;
  personio_sync_interval_h?: 0 | 1 | 6 | 24 | 168;
  personio_sick_leave_type_id?: number[];
  personio_production_dept?: string[];
  personio_skill_attr_key?: string[];
  target_overtime_ratio?: number | null;
  target_sick_leave_ratio?: number | null;
  target_fluctuation?: number | null;
  target_revenue_per_employee?: number | null;
  // v1.55 — Sales-dashboard weekly targets (undefined = "don't change")
  target_sales_erstkontakte?: number | null;
  target_sales_interessenten?: number | null;
  target_sales_besuche?: number | null;
  target_sales_angebote_eur?: number | null;
  // v1.56 — €/week/rep goal on the OrdersDistributionCard tile.
  target_sales_orders_per_rep_eur?: number | null;
  // v1.66 — Quality targets (undefined = "don't change"). Complaint rates
  // travel as fractions (0.02 = 2 %); finding counts as integer thresholds.
  target_complaint_rate_customer?: number | null;
  target_complaint_rate_internal?: number | null;
  target_complaint_rate_supplier?: number | null;
  target_complaint_rate_subcontractor?: number | null;
  target_audit_findings_level1?: number | null;
  target_audit_findings_level2?: number | null;
  target_inspection_large?: number | null;
  target_inspection_small?: number | null;
  // v1.71 / v1.72 — Finance KPI targets (cost ratios as fractions)
  target_material_cost_ratio?: number | null;
  target_personnel_cost_ratio?: number | null;
  target_produktion_verzug?: number | null;
  // Phase 40-01 — Sensor Monitor admin writes. undefined = "don't change"
  // (mirrors Pydantic None-means-don't-change on SettingsUpdate). Decimals
  // go on the wire as strings to match Pydantic's Decimal input coercion.
  sensor_poll_interval_s?: number;
  sensor_temperature_min?: string | null;
  sensor_temperature_max?: string | null;
  sensor_humidity_min?: string | null;
  sensor_humidity_max?: string | null;
  // v1.57 World Cup signage. undefined = "don't change".
  worldcup_api_key?: string;
  worldcup_refresh_seconds?: number;
  // ATR fileserver. undefined = "don't change". Password is write-only.
  atr_smb_host?: string | null;
  atr_smb_share?: string | null;
  atr_smb_domain?: string | null;
  atr_smb_user?: string | null;
  atr_smb_password?: string;
  atr_input_path?: string | null;
  atr_output_path?: string | null;
  atr_archive_path?: string | null;
  atr_scan_interval_s?: number;
  atr_auto_mode?: boolean;
  // v1.83 E-Mail (Office 365 / Graph). undefined = "don't change". Secret is
  // write-only.
  email_tenant_id?: string | null;
  email_client_id?: string | null;
  email_client_secret?: string;
  email_sender_address?: string | null;
  email_sender_name?: string | null;
  email_enabled?: boolean;
  email_auth_mode?: "app" | "delegated";
  // v1.102 — Personio-Rückschreiben (inert bis Freischaltung)
  personio_writeback_enabled?: boolean;
  personio_writeback_kategorie_id?: string | null;
}

/**
 * PUT /api/settings — persists all 8 editable fields atomically.
 * apiClient preserves the legacy `err.detail` error shape so existing
 * callers (settings form toasts) keep working.
 */
export async function updateSettings(
  payload: SettingsUpdatePayload,
): Promise<Settings> {
  return apiClient<Settings>("/api/settings", {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

/**
 * POST /api/settings/logo — uploads a PNG or SVG. FormData body; apiClient
 * leaves Content-Type unset so the browser writes the multipart boundary.
 */
export async function uploadLogo(file: File): Promise<Settings> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient<Settings>("/api/settings/logo", {
    method: "POST",
    body: formData,
  });
}

// ---------------------------------------------------------------------------
// Phase 13 — Personio options and sync test
// ---------------------------------------------------------------------------

export interface AbsenceTypeOption {
  id: number;
  name: string;
}

export interface PersonioOptions {
  absence_types: AbsenceTypeOption[];
  departments: string[];
  skill_attributes: string[];
  error: string | null;
}

export interface SyncTestResult {
  success: boolean;
  error: string | null;
}

/**
 * GET /api/settings/personio-options — fetches live absence types and
 * departments from Personio. Only called when hasCredentials is true.
 */
export async function fetchPersonioOptions(): Promise<PersonioOptions> {
  return apiClient<PersonioOptions>("/api/settings/personio-options");
}

/**
 * POST /api/sync/test — tests the Personio connection using the stored
 * credentials. Returns { success, error } — does not throw on API-level
 * failures (only on network/parse errors).
 */
export async function testPersonioConnection(): Promise<SyncTestResult> {
  return apiClient<SyncTestResult>("/api/sync/test", { method: "POST" });
}

// v1.102 — Personio-Rückschreiben: kontrollierter Test-Upload
export interface WritebackTestResult {
  ok: boolean;
  schritt: string;
  detail: string;
}

export async function testPersonioWriteback(eingabe: {
  employee_id: number;
  art: "schulung" | "kompetenz";
}): Promise<WritebackTestResult> {
  return apiClient<WritebackTestResult>("/api/sync/writeback-test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(eingabe),
  });
}

// ---------------------------------------------------------------------------
// Phase 14 — Sync meta and trigger
// ---------------------------------------------------------------------------

export interface SyncMetaResponse {
  last_synced_at: string | null;
  last_sync_status: "ok" | "partial" | "error" | null;
  last_sync_error: string | null;
}

export async function fetchSyncMeta(): Promise<SyncMetaResponse> {
  return apiClient<SyncMetaResponse>("/api/sync/meta");
}

export interface SyncResult {
  employees_synced: number;
  attendance_synced: number;
  absences_synced: number;
  status: "ok" | "partial" | "error";
  error_message: string | null;
}

export async function triggerSync(): Promise<SyncResult> {
  return apiClient<SyncResult>("/api/sync", { method: "POST" });
}

// ---------------------------------------------------------------------------
// Phase 15 — HR KPIs
// ---------------------------------------------------------------------------

export interface HrKpiValue {
  value: number | null;
  is_configured: boolean;
  previous_period: number | null;
  previous_year: number | null;
}

export interface HrKpiResponse {
  overtime_ratio: HrKpiValue;
  sick_leave_ratio: HrKpiValue;
  fluctuation: HrKpiValue;
  skill_development: HrKpiValue;
  revenue_per_production_employee: HrKpiValue;
}

export async function fetchHrKpis(params?: {
  date_from?: string;
  date_to?: string;
}): Promise<HrKpiResponse> {
  const q = new URLSearchParams();
  if (params?.date_from) q.set("date_from", params.date_from);
  if (params?.date_to) q.set("date_to", params.date_to);
  const qs = q.toString();
  return apiClient<HrKpiResponse>(`/api/hr/kpis${qs ? `?${qs}` : ""}`);
}

// Org chart — active employees + their supervisor id (from synced Personio data).
export interface OrgChartNode {
  id: number;
  first_name: string | null;
  last_name: string | null;
  position: string | null;
  department: string | null;
  office: string | null;
  supervisor_id: number | null;
}

export async function fetchOrgChart(): Promise<OrgChartNode[]> {
  return apiClient<OrgChartNode[]>("/api/hr/org-chart");
}

export interface HrKpiHistoryPoint {
  // bucket label: "YYYY-MM-DD" (daily) | "YYYY-Www" (weekly) | "YYYY-MM" (monthly) | "YYYY-Qn" (quarterly)
  month: string;
  overtime_ratio: number | null;
  sick_leave_ratio: number | null;
  fluctuation: number | null;
  revenue_per_production_employee: number | null;
}

export async function fetchHrKpiHistory(params?: {
  date_from?: string;
  date_to?: string;
}): Promise<HrKpiHistoryPoint[]> {
  const q = new URLSearchParams();
  if (params?.date_from) q.set("date_from", params.date_from);
  if (params?.date_to) q.set("date_to", params.date_to);
  const qs = q.toString();
  return apiClient<HrKpiHistoryPoint[]>(
    `/api/hr/kpis/history${qs ? `?${qs}` : ""}`,
  );
}

// v1.51 — Birthdays of the week (Personio raw_json -> Geburtsdatum).
export interface BirthdayEntry {
  employee_id: number;
  first_name: string | null;
  last_name: string | null;
  department: string | null;
  birthday: string;     // YYYY-MM-DD
  weekday: number;      // 0 = Monday … 6 = Sunday
  occurs_on: string;    // this year's anniversary date (YYYY-MM-DD)
  age_turning: number;
  has_photo: boolean;   // true => GET /api/hr/employees/{id}/photo returns an image
}

export async function fetchBirthdaysThisWeek(): Promise<BirthdayEntry[]> {
  return apiClient<BirthdayEntry[]>("/api/hr/birthdays/this-week");
}

// Unauthenticated mirror for the /embed/birthdays signage view. Same shape as
// the auth'd endpoint but skips apiClient's 401-retry/silent-refresh dance,
// which we don't want firing on a kiosk that never had a Directus session.
export async function fetchBirthdaysThisWeekPublic(): Promise<BirthdayEntry[]> {
  const r = await fetch("/api/hr/embed/birthdays/this-week", { credentials: "omit" });
  if (!r.ok) throw new Error(`birthdays embed fetch failed: ${r.status}`);
  return (await r.json()) as BirthdayEntry[];
}

// v1.51 — Joiners of the last 2 weeks (active employees only).
export interface JoinerEntry {
  employee_id: number;
  first_name: string | null;
  last_name: string | null;
  department: string | null;
  hire_date: string;          // YYYY-MM-DD
  days_with_company: number;  // today - hire_date
  has_photo: boolean;
}

export async function fetchJoinersRecent(): Promise<JoinerEntry[]> {
  return apiClient<JoinerEntry[]>("/api/hr/joiners/recent");
}

export async function fetchJoinersRecentPublic(): Promise<JoinerEntry[]> {
  const r = await fetch("/api/hr/embed/joiners/recent", { credentials: "omit" });
  if (!r.ok) throw new Error(`joiners embed fetch failed: ${r.status}`);
  return (await r.json()) as JoinerEntry[];
}

// --- World Cup signage embed (v1.57) ---------------------------------------

export interface WorldCupTeam {
  name: string;
  short_name: string | null;
  crest: string | null;
}

export interface WorldCupMatch {
  id: number;
  home: WorldCupTeam;
  away: WorldCupTeam;
  score_home: number | null;
  score_away: number | null;
  status: string; // SCHEDULED/TIMED/IN_PLAY/PAUSED/FINISHED/...
  minute: number | null;
  kickoff_utc: string;
}

export interface WorldCupFeed {
  refresh_seconds: number;
  stale_since: string | null;
  error: string | null; // "not_configured" | "upstream_unavailable"
  matches: WorldCupMatch[];
  next_matchday: string | null;
  next_matches: WorldCupMatch[];
}

// Unauthenticated fetcher for the /embed/worldcup signage view — same
// credentials-omit pattern as the HR embed fetchers above.
export async function fetchWorldCupTodayPublic(): Promise<WorldCupFeed> {
  const r = await fetch("/api/worldcup/embed/today", { credentials: "omit" });
  if (!r.ok) throw new Error(`worldcup embed fetch failed: ${r.status}`);
  return (await r.json()) as WorldCupFeed;
}

export interface StandingsRow {
  position: number;
  team: WorldCupTeam;
  played: number;
  won: number;
  draw: number;
  lost: number;
  goal_difference: number;
  points: number;
}
export interface StandingsGroup {
  group: string;
  table: StandingsRow[];
}
export interface StandingsFeed {
  refresh_seconds: number;
  stale_since: string | null;
  error: string | null;
  groups: StandingsGroup[];
}
export interface MatchesWindowFeed {
  refresh_seconds: number;
  stale_since: string | null;
  error: string | null;
  yesterday: WorldCupMatch[];
  today: WorldCupMatch[];
  tomorrow: WorldCupMatch[];
}
export interface KnockoutStage {
  stage: string;
  matches: WorldCupMatch[];
}
export interface KnockoutFeed {
  refresh_seconds: number;
  stale_since: string | null;
  error: string | null;
  stages: KnockoutStage[];
}
export interface ScorerRow {
  rank: number;
  player_name: string;
  team: WorldCupTeam;
  goals: number;
}
export interface ScorersFeed {
  refresh_seconds: number;
  stale_since: string | null;
  error: string | null;
  scorers: ScorerRow[];
}

async function fetchWorldCupPublic<T>(path: string): Promise<T> {
  const r = await fetch(path, { credentials: "omit" });
  if (!r.ok) throw new Error(`worldcup embed fetch failed: ${r.status}`);
  return (await r.json()) as T;
}
export const fetchWorldCupStandingsPublic = () =>
  fetchWorldCupPublic<StandingsFeed>("/api/worldcup/embed/standings");
export const fetchWorldCupMatchesPublic = () =>
  fetchWorldCupPublic<MatchesWindowFeed>("/api/worldcup/embed/matches");
export const fetchWorldCupKnockoutPublic = () =>
  fetchWorldCupPublic<KnockoutFeed>("/api/worldcup/embed/knockout");
export const fetchWorldCupScorersPublic = () =>
  fetchWorldCupPublic<ScorersFeed>("/api/worldcup/embed/scorers");

export interface TippspielRankRow {
  rank: number;
  department: string;
  last_points: number;
  total_points: number;
}
export interface TippspielFeed {
  refresh_seconds: number;
  error: string | null;
  ranking: TippspielRankRow[];
}
export const fetchWorldCupTippspielPublic = () =>
  fetchWorldCupPublic<TippspielFeed>("/api/worldcup/embed/tippspiel");

// ---------------------------------------------------------------------------
// v1.49 — Quality (8D audit findings)
// ---------------------------------------------------------------------------

export const AUDIT_TYPE_CODES = ["BH AUD", "EX AUD", "IN AUD", "KU AUD"] as const;
export type AuditTypeCode = (typeof AUDIT_TYPE_CODES)[number];

export interface QualityUploadResponse {
  rows_inserted: number;
  rows_updated: number;
  errors: ValidationErrorDetail[];
}

export interface AuditFindingsValue {
  level_1: number;
  level_2: number;
  previous_period_level_1: number | null;
  previous_period_level_2: number | null;
  previous_year_level_1: number | null;
  previous_year_level_2: number | null;
}

export interface AuditFindingsHistoryPoint {
  month: string;
  level_1: number;
  level_2: number;
  // Variable-key (level, art) breakdown — one field per active filter code,
  // e.g. `level_1_BH_AUD`, `level_2_KU_AUD`. The set of keys is governed by
  // the active audit_types query param; keys absent from the response are
  // *not* present at all (not zero-filled). Render code should fall back to
  // 0 on missing lookups.
  [key: `level_${1 | 2}_${string}`]: number | string;
}

export async function uploadQualityFile(file: File): Promise<QualityUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient<QualityUploadResponse>("/api/upload-quality", {
    method: "POST",
    body: formData,
  });
}

// v1.51 — Interessenten (prospect master-data) upload.
export interface InteressentenUploadResponse {
  rows_inserted: number;
  rows_updated: number;
  errors: ValidationErrorDetail[];
}

export async function uploadInteressentenFile(
  file: File,
): Promise<InteressentenUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient<InteressentenUploadResponse>("/api/upload-interessenten", {
    method: "POST",
    body: formData,
  });
}

// v1.52 — Angebote (sales-offer) upload from AswKpf_ANG.txt.
export interface AngeboteUploadResponse {
  rows_inserted: number;
  rows_updated: number;
  errors: ValidationErrorDetail[];
}

export async function uploadAngeboteFile(
  file: File,
): Promise<AngeboteUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient<AngeboteUploadResponse>("/api/upload-angebote", {
    method: "POST",
    body: formData,
  });
}

// v1.53 — Umsatz (Rechnungsausgang RG/GS) upload from AswKpf_RG.txt.
export interface RevenueUploadResponse {
  rows_inserted: number;
  rows_updated: number;
  errors: ValidationErrorDetail[];
}

export async function uploadUmsatzFile(
  file: File,
): Promise<RevenueUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient<RevenueUploadResponse>("/api/upload-umsatz", {
    method: "POST",
    body: formData,
  });
}

// v1.54 — Aufträge (order book) upload from AswKpf_AUF.txt.
export interface AuftraegeUploadResponse {
  rows_inserted: number;
  rows_updated: number;
  errors: ValidationErrorDetail[];
}

export async function uploadAuftraegeFile(
  file: File,
): Promise<AuftraegeUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient<AuftraegeUploadResponse>("/api/upload-auftraege", {
    method: "POST",
    body: formData,
  });
}

// v1.76 — position-level AswKpf_AUF (Auftragspositionen) feeding the Verzug KPI.
export interface AuftragPositionenUploadResponse {
  rows_inserted: number;
  rows_updated: number;
  errors: ValidationErrorDetail[];
}

export async function uploadAuftragPositionenFile(
  file: File,
): Promise<AuftragPositionenUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient<AuftragPositionenUploadResponse>(
    "/api/upload-auftrag-positionen",
    { method: "POST", body: formData },
  );
}

function _buildQualityQuery(params?: {
  date_from?: string;
  date_to?: string;
  audit_types?: readonly AuditTypeCode[];
}): string {
  const q = new URLSearchParams();
  if (params?.date_from) q.set("date_from", params.date_from);
  if (params?.date_to) q.set("date_to", params.date_to);
  if (params?.audit_types && params.audit_types.length > 0) {
    q.set("audit_types", params.audit_types.join(","));
  }
  const qs = q.toString();
  return qs ? `?${qs}` : "";
}

export async function fetchAuditFindings(params?: {
  date_from?: string;
  date_to?: string;
  audit_types?: readonly AuditTypeCode[];
}): Promise<AuditFindingsValue> {
  return apiClient<AuditFindingsValue>(
    `/api/quality/audit-findings${_buildQualityQuery(params)}`,
  );
}

export async function fetchAuditFindingsHistory(params?: {
  date_from?: string;
  date_to?: string;
  audit_types?: readonly AuditTypeCode[];
  granularity?: BucketGranularity;
}): Promise<AuditFindingsHistoryPoint[]> {
  const q = new URLSearchParams();
  if (params?.date_from) q.set("date_from", params.date_from);
  if (params?.date_to) q.set("date_to", params.date_to);
  if (params?.audit_types && params.audit_types.length > 0) {
    q.set("audit_types", params.audit_types.join(","));
  }
  if (params?.granularity) q.set("granularity", params.granularity);
  const qs = q.toString();
  return apiClient<AuditFindingsHistoryPoint[]>(
    `/api/quality/audit-findings/history${qs ? `?${qs}` : ""}`,
  );
}

export interface AuditFindingRow {
  report_nr: string;
  report_date: string | null;
  art: AuditTypeCode | null;
  level: 1 | 2 | null;
  issuer: string | null;
  customer_name: string | null;
  customer_id: string | null;
  designation: string | null;
  status_code: string | null;
}

export async function fetchAuditFindingsList(params?: {
  date_from?: string;
  date_to?: string;
  audit_types?: readonly AuditTypeCode[];
}): Promise<AuditFindingRow[]> {
  return apiClient<AuditFindingRow[]>(
    `/api/quality/audit-findings/list${_buildQualityQuery(params)}`,
  );
}

// ---------------------------------------------------------------------------
// v1.58 — Customer complaint rate
// ---------------------------------------------------------------------------

export type QtyMode = "total" | "accepted";
export type ComplaintType =
  | "customer"
  | "internal"
  | "supplier"
  | "subcontractor";
export type BucketGranularity =
  | "weekly"
  | "monthly"
  | "quarterly"
  | "yearly";

export interface DeliveryUploadResponse {
  rows_inserted: number;
  rows_updated: number;
  errors: ValidationErrorDetail[];
}

export interface ComplaintRateValue {
  rate: number | null;
  complaint_qty: number;
  delivered_qty: number;
  previous_period: number | null;
  previous_year: number | null;
}

export interface ComplaintRateHistoryPoint {
  month: string;
  rate: number | null;
  complaint_qty: number;
  delivered_qty: number;
}

export interface CustomerComplaintRow {
  report_nr: string;
  report_date: string | null;
  art: string | null;
  issuer: string | null;
  customer_name: string | null;
  customer_id: string | null;
  designation: string | null;
  status_code: string | null;
  quantity: number | null;
  accepted_quantity: number | null;
}

export interface GoodsReceiptUploadResponse {
  rows_inserted: number;
  rows_updated: number;
  errors: ValidationErrorDetail[];
}

export async function uploadGoodsReceiptFile(
  file: File,
): Promise<GoodsReceiptUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient<GoodsReceiptUploadResponse>("/api/upload-goods-receipts", {
    method: "POST",
    body: formData,
  });
}

// v1.79 — Qualitätsprüfung (AswQs2151 inspection log) upload
export interface InspectionsUploadResponse {
  rows_inserted: number;
  rows_replaced: number;
  small_count: number;
  large_count: number;
  date_range_from: string | null;
  date_range_to: string | null;
  errors: ValidationErrorDetail[];
}

export async function uploadInspectionsFile(
  file: File,
): Promise<InspectionsUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient<InspectionsUploadResponse>("/api/upload-inspections", {
    method: "POST",
    body: formData,
  });
}

export async function uploadDeliveryFile(file: File): Promise<DeliveryUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient<DeliveryUploadResponse>("/api/upload-deliveries", {
    method: "POST",
    body: formData,
  });
}

function _buildComplaintQuery(params?: {
  date_from?: string;
  date_to?: string;
  qty_mode?: QtyMode;
  complaint_type?: ComplaintType;
}): string {
  const q = new URLSearchParams();
  if (params?.date_from) q.set("date_from", params.date_from);
  if (params?.date_to) q.set("date_to", params.date_to);
  if (params?.qty_mode) q.set("qty_mode", params.qty_mode);
  if (params?.complaint_type) q.set("complaint_type", params.complaint_type);
  const qs = q.toString();
  return qs ? `?${qs}` : "";
}

export async function fetchComplaintRate(params?: {
  date_from?: string;
  date_to?: string;
  qty_mode?: QtyMode;
  complaint_type?: ComplaintType;
}): Promise<ComplaintRateValue> {
  return apiClient<ComplaintRateValue>(
    `/api/quality/complaint-rate${_buildComplaintQuery(params)}`,
  );
}

export async function fetchComplaintRateHistory(params?: {
  date_from?: string;
  date_to?: string;
  qty_mode?: QtyMode;
  complaint_type?: ComplaintType;
  granularity?: BucketGranularity;
}): Promise<ComplaintRateHistoryPoint[]> {
  const q = new URLSearchParams();
  if (params?.date_from) q.set("date_from", params.date_from);
  if (params?.date_to) q.set("date_to", params.date_to);
  if (params?.qty_mode) q.set("qty_mode", params.qty_mode);
  if (params?.complaint_type) q.set("complaint_type", params.complaint_type);
  if (params?.granularity) q.set("granularity", params.granularity);
  const qs = q.toString();
  return apiClient<ComplaintRateHistoryPoint[]>(
    `/api/quality/complaint-rate/history${qs ? `?${qs}` : ""}`,
  );
}

// v1.70 — Inspections (Qualitätsprüfung: Große / Kleine Produkte)

export interface InspectionsValue {
  large_count: number;
  small_count: number;
  previous_period_large: number | null;
  previous_period_small: number | null;
  previous_year_large: number | null;
  previous_year_small: number | null;
}

export interface InspectionsHistoryPoint {
  month: string;
  large_count: number;
  small_count: number;
}

function _buildInspectionsQuery(params?: {
  date_from?: string;
  date_to?: string;
  granularity?: BucketGranularity;
}): string {
  const q = new URLSearchParams();
  if (params?.date_from) q.set("date_from", params.date_from);
  if (params?.date_to) q.set("date_to", params.date_to);
  if (params?.granularity) q.set("granularity", params.granularity);
  const qs = q.toString();
  return qs ? `?${qs}` : "";
}

export async function fetchInspections(params?: {
  date_from?: string;
  date_to?: string;
}): Promise<InspectionsValue> {
  return apiClient<InspectionsValue>(
    `/api/quality/inspections${_buildInspectionsQuery(params)}`,
  );
}

export async function fetchInspectionsHistory(params?: {
  date_from?: string;
  date_to?: string;
  granularity?: BucketGranularity;
}): Promise<InspectionsHistoryPoint[]> {
  return apiClient<InspectionsHistoryPoint[]>(
    `/api/quality/inspections/history${_buildInspectionsQuery(params)}`,
  );
}

export interface InspectionListRow {
  bezeichnung: string | null;
  size_class: "large" | "small";
  produktgruppe: string | null;
  bookings: number;
  total_qty: number;
  scrap_qty: number;
  scrap_rate: number | null;
  inspectors: number;
  first_date: string | null;
  last_date: string | null;
}

export async function fetchInspectionsList(params?: {
  date_from?: string;
  date_to?: string;
}): Promise<InspectionListRow[]> {
  return apiClient<InspectionListRow[]>(
    `/api/quality/inspections/list${_buildInspectionsQuery(params)}`,
  );
}

// v1.80 — individual bookings + per-row exclude toggle
export interface InspectionBookingRow {
  id: number;
  pruef_datum: string | null;
  pruef_zeit: string | null;
  benutzer: string | null;
  fa: string | null;
  artikel: string | null;
  bezeichnung: string | null;
  size_class: "large" | "small";
  produktgruppe: string | null;
  buchungs_menge: number;
  ausschuss_menge: number;
  excluded: boolean;
}

export async function fetchInspectionBookings(params?: {
  date_from?: string;
  date_to?: string;
}): Promise<InspectionBookingRow[]> {
  return apiClient<InspectionBookingRow[]>(
    `/api/quality/inspections/bookings${_buildInspectionsQuery(params)}`,
  );
}

export async function updateInspectionBooking(
  id: number,
  excluded: boolean,
): Promise<InspectionBookingRow> {
  return apiClient<InspectionBookingRow>(
    `/api/quality/inspections/bookings/${id}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ excluded }),
    },
  );
}

export async function fetchCustomerComplaintsList(params?: {
  date_from?: string;
  date_to?: string;
  complaint_type?: ComplaintType;
}): Promise<CustomerComplaintRow[]> {
  const q = new URLSearchParams();
  if (params?.date_from) q.set("date_from", params.date_from);
  if (params?.date_to) q.set("date_to", params.date_to);
  if (params?.complaint_type) q.set("complaint_type", params.complaint_type);
  const qs = q.toString();
  return apiClient<CustomerComplaintRow[]>(
    `/api/quality/complaints/list${qs ? `?${qs}` : ""}`,
  );
}

// --------------------------------------------------------------------------
// Einkauf / OTD (Liefertermintreue) — v1.60
// --------------------------------------------------------------------------

export interface DeliveryReliabilityUploadResponse {
  rows_inserted: number;
  rows_updated: number;
  period_from: string | null;
  period_to: string | null;
  errors: ValidationErrorDetail[];
}

export interface OtdValue {
  rate: number | null;
  punctual_count: number;
  total_count: number;
  avg_delay: number | null;
  previous_period: number | null;
  previous_year: number | null;
}

export interface OtdHistoryPoint {
  month: string;
  rate: number | null;
  punctual_count: number;
  total_count: number;
}

export interface OtdRow {
  auftrag: string;
  pos: number;
  upos: number;
  adr_nr: string | null;
  supplier_name: string | null;
  delivered_date: string | null;
  target_date: string | null;
  verzug_tage: number | null;
  quantity: number | null;
  unit: string | null;
  article_number: string | null;
  article_name: string | null;
}

export async function uploadDeliveryReliabilityFile(
  file: File,
): Promise<DeliveryReliabilityUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient<DeliveryReliabilityUploadResponse>(
    "/api/upload-delivery-reliability",
    { method: "POST", body: formData },
  );
}

function _buildOtdQuery(params?: {
  date_from?: string;
  date_to?: string;
  granularity?: BucketGranularity;
}): string {
  const q = new URLSearchParams();
  if (params?.date_from) q.set("date_from", params.date_from);
  if (params?.date_to) q.set("date_to", params.date_to);
  if (params?.granularity) q.set("granularity", params.granularity);
  const qs = q.toString();
  return qs ? `?${qs}` : "";
}

export async function fetchOtd(params?: {
  date_from?: string;
  date_to?: string;
}): Promise<OtdValue> {
  return apiClient<OtdValue>(`/api/procurement/otd${_buildOtdQuery(params)}`);
}

export async function fetchOtdHistory(params?: {
  date_from?: string;
  date_to?: string;
  granularity?: BucketGranularity;
}): Promise<OtdHistoryPoint[]> {
  return apiClient<OtdHistoryPoint[]>(
    `/api/procurement/otd/history${_buildOtdQuery(params)}`,
  );
}

export async function fetchOtdList(params?: {
  date_from?: string;
  date_to?: string;
}): Promise<OtdRow[]> {
  return apiClient<OtdRow[]>(
    `/api/procurement/otd/list${_buildOtdQuery(params)}`,
  );
}

// v1.106 — Bestellung auf Lager: Top-N Ladenhüter (L-Artikel) nach Wert.
export interface StockOrderTopRow {
  rank: number;
  article_number: string;
  article_name: string | null;
  stock_qty: number;
  unit_price: number;
  value: number;
  last_movement: string | null;
}

export async function fetchTopStockOrders(params?: {
  limit?: number;
}): Promise<StockOrderTopRow[]> {
  const q = new URLSearchParams();
  if (params?.limit) q.set("limit", String(params.limit));
  const qs = q.toString();
  return apiClient<StockOrderTopRow[]>(
    `/api/procurement/stock-orders/top${qs ? `?${qs}` : ""}`,
  );
}

// --------------------------------------------------------------------------
// Produktion / Aufträge in Verzug (Seriengeschäft) — v1.76
// --------------------------------------------------------------------------

export interface ProductionVerzugValue {
  rate: number | null;
  in_verzug_count: number;
  total_count: number;
  avg_delay: number | null;
  previous_period: number | null;
  previous_year: number | null;
}

export interface ProductionVerzugHistoryPoint {
  month: string;
  rate: number | null;
  in_verzug_count: number;
  total_count: number;
}

export interface ProductionVerzugRow {
  vorgang_nr: string;
  customer_name: string | null;
  adr_nr: string | null;
  target_date: string | null;
  actual_date: string | null;
  verzug_tage: number | null;
}

export async function fetchProductionVerzug(params?: {
  date_from?: string;
  date_to?: string;
}): Promise<ProductionVerzugValue> {
  return apiClient<ProductionVerzugValue>(
    `/api/production/verzug${_buildOtdQuery(params)}`,
  );
}

export async function fetchProductionVerzugHistory(params?: {
  date_from?: string;
  date_to?: string;
  granularity?: BucketGranularity;
}): Promise<ProductionVerzugHistoryPoint[]> {
  return apiClient<ProductionVerzugHistoryPoint[]>(
    `/api/production/verzug/history${_buildOtdQuery(params)}`,
  );
}

export async function fetchProductionVerzugList(params?: {
  date_from?: string;
  date_to?: string;
}): Promise<ProductionVerzugRow[]> {
  return apiClient<ProductionVerzugRow[]>(
    `/api/production/verzug/list${_buildOtdQuery(params)}`,
  );
}

export interface ProductionOverdueRow {
  vorgang_nr: string;
  customer_name: string | null;
  adr_nr: string | null;
  target_date: string | null;
  days_overdue: number | null;
}

export async function fetchProductionOverdueList(params?: {
  date_from?: string;
  date_to?: string;
}): Promise<ProductionOverdueRow[]> {
  return apiClient<ProductionOverdueRow[]>(
    `/api/production/verzug/overdue${_buildOtdQuery(params)}`,
  );
}

// --------------------------------------------------------------------------
// Finanzperspektive / Materialkostenquote — v1.70
// --------------------------------------------------------------------------

export interface MaterialMovementsUploadResponse {
  rows_inserted: number;
  rows_replaced: number;
  date_range_from: string | null;
  date_range_to: string | null;
  errors: ValidationErrorDetail[];
}

export interface MaterialPricesUploadResponse {
  rows_inserted: number;
  rows_updated: number;
  errors: ValidationErrorDetail[];
}

export interface StockPriceUploadResponse {
  rows_inserted: number;
  errors: ValidationErrorDetail[];
}

export async function uploadStockPricesFile(
  file: File,
): Promise<StockPriceUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient<StockPriceUploadResponse>("/api/upload-stock-prices", {
    method: "POST",
    body: formData,
  });
}

export interface MaterialCostRatioValue {
  ratio: number | null;
  material_cost: number;
  revenue: number;
  matched_articles: number;
  unmatched_articles: number;
  previous_period: number | null;
  previous_year: number | null;
}

export interface MaterialCostRatioHistoryPoint {
  month: string;
  ratio: number | null;
  material_cost: number;
  revenue: number;
}

export interface MaterialCostRatioRow {
  artikelnr: string;
  article_name: string | null;
  consumed_qty: number;
  unit_price: number | null;
  material_cost: number | null;
  has_price: boolean;
}

export async function uploadMaterialMovementsFile(
  file: File,
): Promise<MaterialMovementsUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient<MaterialMovementsUploadResponse>(
    "/api/upload-material-movements",
    { method: "POST", body: formData },
  );
}

export async function uploadMaterialPricesFile(
  file: File,
): Promise<MaterialPricesUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  return apiClient<MaterialPricesUploadResponse>(
    "/api/upload-material-prices",
    { method: "POST", body: formData },
  );
}

function _buildFinanceQuery(params?: {
  date_from?: string;
  date_to?: string;
  granularity?: BucketGranularity;
}): string {
  const q = new URLSearchParams();
  if (params?.date_from) q.set("date_from", params.date_from);
  if (params?.date_to) q.set("date_to", params.date_to);
  if (params?.granularity) q.set("granularity", params.granularity);
  const qs = q.toString();
  return qs ? `?${qs}` : "";
}

export async function fetchMaterialCostRatio(params?: {
  date_from?: string;
  date_to?: string;
}): Promise<MaterialCostRatioValue> {
  return apiClient<MaterialCostRatioValue>(
    `/api/finance/material-cost-ratio${_buildFinanceQuery(params)}`,
  );
}

export async function fetchMaterialCostRatioHistory(params?: {
  date_from?: string;
  date_to?: string;
  granularity?: BucketGranularity;
}): Promise<MaterialCostRatioHistoryPoint[]> {
  return apiClient<MaterialCostRatioHistoryPoint[]>(
    `/api/finance/material-cost-ratio/history${_buildFinanceQuery(params)}`,
  );
}

export async function fetchMaterialCostRatioList(params?: {
  date_from?: string;
  date_to?: string;
}): Promise<MaterialCostRatioRow[]> {
  return apiClient<MaterialCostRatioRow[]>(
    `/api/finance/material-cost-ratio/list${_buildFinanceQuery(params)}`,
  );
}

export interface PersonnelCostRatioValue {
  ratio: number | null;
  personnel_cost: number;
  revenue: number;
  headcount: number;
  previous_period: number | null;
  previous_year: number | null;
}

export interface PersonnelCostRatioHistoryPoint {
  month: string;
  ratio: number | null;
  personnel_cost: number;
  revenue: number;
}

export interface PersonnelCostRatioRow {
  department: string;
  headcount: number;
  personnel_cost: number;
}

export async function fetchPersonnelCostRatio(params?: {
  date_from?: string;
  date_to?: string;
}): Promise<PersonnelCostRatioValue> {
  return apiClient<PersonnelCostRatioValue>(
    `/api/finance/personnel-cost-ratio${_buildFinanceQuery(params)}`,
  );
}

export async function fetchPersonnelCostRatioHistory(params?: {
  date_from?: string;
  date_to?: string;
  granularity?: BucketGranularity;
}): Promise<PersonnelCostRatioHistoryPoint[]> {
  return apiClient<PersonnelCostRatioHistoryPoint[]>(
    `/api/finance/personnel-cost-ratio/history${_buildFinanceQuery(params)}`,
  );
}

export async function fetchPersonnelCostRatioList(params?: {
  date_from?: string;
  date_to?: string;
}): Promise<PersonnelCostRatioRow[]> {
  return apiClient<PersonnelCostRatioRow[]>(
    `/api/finance/personnel-cost-ratio/list${_buildFinanceQuery(params)}`,
  );
}

// --------------------------------------------------------------------------
// Data table types and fetchers
// --------------------------------------------------------------------------

export interface SalesRecordRow {
  id: number;
  order_number: string;
  customer_name: string | null;
  city: string | null;
  order_date: string | null;
  total_value: number | null;
  remaining_value: number | null;
  responsible_person: string | null;
  project_name: string | null;
  status_code: number | null;
}

export async function fetchSalesRecords(params?: {
  start_date?: string;
  end_date?: string;
  customer?: string;
  search?: string;
}): Promise<SalesRecordRow[]> {
  // Phase 67 MIG-DATA-01: Directus SDK replacement for GET /api/data/sales.
  // Filter translation per CONTEXT D-10 (date range), D-11 (customer),
  // D-12 (multi-field search), D-13 (sort), D-14 (limit). Fields list
  // mirrors the Viewer allowlist in directus/bootstrap-roles.sh:179 and
  // Pydantic SalesRecordRead — keep all three in lockstep.
  const filter: Record<string, unknown> = {};

  if (params?.start_date && params?.end_date) {
    filter.order_date = { _between: [params.start_date, params.end_date] };
  } else if (params?.start_date) {
    filter.order_date = { _gte: params.start_date };
  } else if (params?.end_date) {
    filter.order_date = { _lte: params.end_date };
  }

  if (params?.customer) {
    filter.customer_name = { _icontains: params.customer };
  }

  if (params?.search) {
    filter._or = [
      { order_number: { _icontains: params.search } },
      { customer_name: { _icontains: params.search } },
      { project_name: { _icontains: params.search } },
    ];
  }

  let rows: unknown;
  try {
    rows = await directus.request(
      readItems("sales_records", {
        filter,
        sort: ["-order_date"],
        limit: 500,
        fields: [
          "id",
          "order_number",
          "customer_name",
          "city",
          "order_date",
          "total_value",
          "remaining_value",
          "responsible_person",
          "project_name",
          "status_code",
        ],
      }),
    );
  } catch (e) { throw toApiError(e); }
  return rows as SalesRecordRow[];
}

export interface EmployeeRow {
  id: number;
  first_name: string | null;
  last_name: string | null;
  status: string | null;
  department: string | null;
  position: string | null;
  hire_date: string | null;
  termination_date: string | null;
  weekly_working_hours: number | null;
  total_hours: number;
  overtime_hours: number;
  overtime_ratio: number | null;
}

export async function fetchEmployees(params?: {
  department?: string;
  status?: string;
  search?: string;
}): Promise<EmployeeRow[]> {
  // Phase 67 MIG-DATA-02: Directus SDK replacement for GET /api/data/employees
  // row-data portion. date_from/date_to dropped from this signature (D-15) —
  // they drive only fetchEmployeesOvertime now.
  // Filter translation per CONTEXT D-15. Fields list = 9 column-backed
  // fields (total_hours/overtime_hours/overtime_ratio are compute-only,
  // hydrated by useEmployeesWithOvertime merge).
  const filter: Record<string, unknown> = {};

  if (params?.department) {
    filter.department = { _icontains: params.department };
  }
  if (params?.status) {
    filter.status = { _eq: params.status };
  }
  if (params?.search) {
    filter._or = [
      { first_name: { _icontains: params.search } },
      { last_name: { _icontains: params.search } },
      { position: { _icontains: params.search } },
    ];
  }

  let rows: unknown;
  try {
    rows = await directus.request(
      readItems("personio_employees", {
        filter,
        sort: ["last_name"],
        limit: 500,
        fields: [
          "id",
          "first_name",
          "last_name",
          "status",
          "department",
          "position",
          "hire_date",
          "termination_date",
          "weekly_working_hours",
        ],
      }),
    );
  } catch (e) { throw toApiError(e); }

  // Zero-fill compute fields until the merge hook replaces them. Keeps
  // EmployeeRow's contract intact for any consumer calling fetchEmployees
  // directly without the merge hook.
  return (rows as Array<Omit<EmployeeRow, "total_hours" | "overtime_hours" | "overtime_ratio">>)
    .map((r) => ({
      ...r,
      total_hours: 0,
      overtime_hours: 0,
      overtime_ratio: null,
    }));
}

// Phase 67 MIG-DATA-03: FastAPI compute endpoint for per-employee overtime
// roll-up. Shape per backend/app/routers/hr_overtime.py (CONTEXT D-04).
export interface OvertimeEntry {
  employee_id: number;
  total_hours: number;
  overtime_hours: number;
  overtime_ratio: number | null;
}

export async function fetchEmployeesOvertime(
  date_from: string,
  date_to: string,
): Promise<OvertimeEntry[]> {
  const q = new URLSearchParams({ date_from, date_to });
  return apiClient<OvertimeEntry[]>(
    `/api/data/employees/overtime?${q.toString()}`,
  );
}

/**
 * Phase 67 MIG-DATA-02 + MIG-DATA-03: composite hook that fetches employee
 * rows from Directus and overtime roll-up from FastAPI, then merges them
 * by employee_id. Zero-fills overtime fields for employees absent from
 * the overtime response (e.g. no attendance in the window). Mirrors the
 * v1.21 data.py behavior where every employee appears in the table,
 * with 0h values when there is no attendance in the requested window.
 *
 * QueryKeys (Claude's Discretion per CONTEXT):
 *  - rows: ["directus", "personio_employees", { search }]
 *    (deliberately new namespace — avoids cache-collision with legacy
 *    hrKpiKeys.employees per Pitfall 4)
 *  - overtime: ["employeesOvertime", date_from, date_to]
 *    (invalidates on date-range change only; search edits don't refetch)
 */
export function useEmployeesWithOvertime(params: {
  search?: string;
  date_from: string | undefined;
  date_to: string | undefined;
}): { data: EmployeeRow[] | undefined; isLoading: boolean } {
  const rowsQ = useQuery({
    queryKey: ["directus", "personio_employees", { search: params.search }] as const,
    queryFn: () => fetchEmployees({ search: params.search }),
  });

  const datesReady = !!params.date_from && !!params.date_to;
  const otQ = useQuery({
    queryKey: ["employeesOvertime", params.date_from, params.date_to] as const,
    queryFn: () => fetchEmployeesOvertime(params.date_from!, params.date_to!),
    enabled: datesReady,
  });

  const data = useMemo<EmployeeRow[] | undefined>(() => {
    if (!rowsQ.data) return undefined;
    const byId = new Map<number, OvertimeEntry>(
      (otQ.data ?? []).map((e) => [e.employee_id, e]),
    );
    return rowsQ.data.map((r) => {
      const ot = byId.get(r.id);
      return {
        ...r,
        total_hours: ot?.total_hours ?? 0,
        overtime_hours: ot?.overtime_hours ?? 0,
        overtime_ratio: ot?.overtime_ratio ?? null,
      };
    });
  }, [rowsQ.data, otQ.data]);

  return {
    data,
    isLoading: rowsQ.isLoading || otQ.isLoading,
  };
}

// ---------------------------------------------------------------------------
// Phase 39 — Sensor Monitor (dashboard read path)
// Mirrors backend/app/schemas.py SensorRead / SensorReadingRead / SensorStatusEntry
// / PollNowResult. Decimal fields are serialized as string by Pydantic and must
// be parsed via Number(...) at render time (never stored as number).
// ---------------------------------------------------------------------------

export interface SensorRead {
  id: number;
  name: string;
  host: string;
  port: number;
  temperature_oid: string | null;
  humidity_oid: string | null;
  temperature_scale: string; // Decimal serialized
  humidity_scale: string;
  enabled: boolean;
  /** v1.39: optional `#rrggbb` chart color override; null → palette fallback. */
  chart_color: string | null;
  created_at: string;
  updated_at: string;
}

export interface SensorReadingRead {
  // `id` is null when the backend returns a downsampled bucket average for
  // long windows (hours > 24). Raw rows carry a real id.
  id: number | null;
  sensor_id: number;
  recorded_at: string; // ISO8601
  temperature: string | null; // Decimal, may be null on gaps
  humidity: string | null;
  error_code: string | null;
}

export interface SensorStatusEntry {
  sensor_id: number;
  last_attempt_at: string | null;
  last_success_at: string | null;
  consecutive_failures: number;
  offline: boolean; // consecutive_failures >= 3
}

export interface PollNowResult {
  sensors_polled: number;
  errors: string[];
}

export async function fetchSensors(): Promise<SensorRead[]> {
  return apiClient<SensorRead[]>("/api/sensors");
}

export async function fetchSensorReadings(
  sensorId: number,
  hours: number,
): Promise<SensorReadingRead[]> {
  return apiClient<SensorReadingRead[]>(
    `/api/sensors/${sensorId}/readings?hours=${hours}`,
  );
}

export async function fetchSensorStatus(): Promise<SensorStatusEntry[]> {
  return apiClient<SensorStatusEntry[]>("/api/sensors/status");
}

/**
 * POST /api/sensors/poll-now — triggers an on-demand poll of all enabled sensors.
 * Exported now (interface-first) so 39-02 can wire the Poll-now button without
 * re-touching api.ts.
 */
export async function pollSensorsNow(): Promise<PollNowResult> {
  return apiClient<PollNowResult>("/api/sensors/poll-now", { method: "POST" });
}

// ---------------------------------------------------------------------------
// Phase 40-01 — Sensor admin CRUD (mirrors backend SensorCreate / SensorUpdate)
// community is SecretStr server-side — write-only; OMIT from PATCH body to
// preserve the stored ciphertext (PITFALLS C-3). Decimals travel as strings
// (matches Pydantic input coercion; consistent with Phase 39 read shape).
// ---------------------------------------------------------------------------

export interface SensorCreatePayload {
  name: string;
  host: string;
  port: number;
  community: string;              // plaintext on create — backend encrypts via Fernet
  temperature_oid: string | null;
  humidity_oid: string | null;
  temperature_scale: string;      // Decimal
  humidity_scale: string;         // Decimal
  enabled: boolean;
  /** v1.39: optional `#rrggbb` chart color; null → palette fallback. */
  chart_color?: string | null;
}

export interface SensorUpdatePayload {
  name?: string;
  host?: string;
  port?: number;
  // Omit to keep stored ciphertext; set to a non-empty string to reset.
  community?: string;
  temperature_oid?: string | null;
  humidity_oid?: string | null;
  temperature_scale?: string;
  humidity_scale?: string;
  enabled?: boolean;
  chart_color?: string | null;
}

export async function createSensor(body: SensorCreatePayload): Promise<SensorRead> {
  return apiClient<SensorRead>("/api/sensors", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function updateSensor(
  id: number,
  body: SensorUpdatePayload,
): Promise<SensorRead> {
  return apiClient<SensorRead>(`/api/sensors/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export async function deleteSensor(id: number): Promise<void> {
  await apiClient<void>(`/api/sensors/${id}`, { method: "DELETE" });
}

// ---------------------------------------------------------------------------
// Phase 40-02 — SNMP Probe + Walk (admin tooling)
// Backend endpoints live since Phase 38-02; both admin-gated at router level.
// Server-side: asyncio.wait_for(timeout=30). Clients mirror with Promise.race(30_000)
// at the call site (see SensorProbeButton.tsx, SnmpWalkCard.tsx).
// ---------------------------------------------------------------------------

export interface SnmpProbeRequestPayload {
  host: string;
  port: number;
  community: string;
  temperature_oid: string | null;
  humidity_oid: string | null;
  temperature_scale: string;
  humidity_scale: string;
}

export interface SnmpProbeResult {
  temperature: number | null;
  humidity: number | null;
}

export async function runSnmpProbe(
  body: SnmpProbeRequestPayload,
): Promise<SnmpProbeResult> {
  return apiClient<SnmpProbeResult>("/api/sensors/snmp-probe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export interface SnmpWalkRequestPayload {
  host: string;
  port: number;
  community: string;
  base_oid: string;
  max_results?: number;
}

export interface SnmpWalkEntry {
  oid: string;
  value: string;
  type: string;
}

export async function runSnmpWalk(
  body: SnmpWalkRequestPayload,
): Promise<SnmpWalkEntry[]> {
  return apiClient<SnmpWalkEntry[]>("/api/sensors/snmp-walk", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// ATR Phase C — fileserver connection test
// ---------------------------------------------------------------------------

export async function testAtrFileserver(): Promise<{ ok: boolean; error: string | null }> {
  return apiClient<{ ok: boolean; error: string | null }>("/api/atr/fileserver/test", { method: "POST" });
}

// --- v1.83 E-Mail background module (Office 365 / Microsoft Graph) ----------

export interface EmailSendPayload {
  to: string[];
  subject: string;
  body_html: string;
  body_text?: string | null;
  cc?: string[] | null;
}

/** POST /api/email/test — send a probe mail to verify the O365 setup. */
export async function sendTestEmail(
  to: string,
): Promise<{ ok: boolean; error: string | null }> {
  return apiClient<{ ok: boolean; error: string | null }>("/api/email/test", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ to }),
  });
}

/** POST /api/email/send — generic send for reminders/reports. */
export async function sendEmail(
  payload: EmailSendPayload,
): Promise<{ ok: boolean; error: string | null }> {
  return apiClient<{ ok: boolean; error: string | null }>("/api/email/send", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export interface DeviceCodeStart {
  device_code: string;
  user_code: string;
  verification_uri: string;
  expires_in: number;
  interval: number;
  message: string;
}

export interface DeviceCodePollResult {
  status: "pending" | "complete" | "error";
  account: string | null;
  error: string | null;
}

/** POST /api/email/delegated/start — begin device-code sign-in. */
export async function startDelegatedLogin(): Promise<DeviceCodeStart> {
  return apiClient<DeviceCodeStart>("/api/email/delegated/start", { method: "POST" });
}

/** POST /api/email/delegated/poll — poll once for completion. */
export async function pollDelegatedLogin(
  deviceCode: string,
): Promise<DeviceCodePollResult> {
  return apiClient<DeviceCodePollResult>("/api/email/delegated/poll", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ device_code: deviceCode }),
  });
}

/** POST /api/email/delegated/disconnect — forget the delegated sign-in. */
export async function disconnectDelegatedLogin(): Promise<{ ok: boolean; error: string | null }> {
  return apiClient<{ ok: boolean; error: string | null }>("/api/email/delegated/disconnect", {
    method: "POST",
  });
}

// ---------------------------------------------------------------------------
// Seiten-Feedback (v1.105) — global feedback/problem-report widget.
// ---------------------------------------------------------------------------

export type FeedbackStatus = "new" | "resolved";

export interface FeedbackItem {
  id: string;
  created_at: string;
  created_by_id: string | null;
  reporter_email: string | null;
  page_url: string;
  description: string;
  has_screenshot: boolean;
  screenshot_mime: string | null;
  user_agent: string | null;
  viewport: string | null;
  status: FeedbackStatus;
  viewed_at: string | null;
}

/** POST /api/feedback — submit a report (open to every authenticated role). */
export async function submitFeedback(input: {
  description: string;
  pageUrl: string;
  userAgent?: string;
  viewport?: string;
  reporterEmail?: string;
  screenshot?: Blob | null;
}): Promise<{ id: string }> {
  const fd = new FormData();
  fd.append("description", input.description);
  fd.append("page_url", input.pageUrl);
  if (input.userAgent) fd.append("user_agent", input.userAgent);
  if (input.viewport) fd.append("viewport", input.viewport);
  if (input.reporterEmail) fd.append("reporter_email", input.reporterEmail);
  if (input.screenshot) fd.append("screenshot", input.screenshot, "screenshot.jpg");
  return apiClient<{ id: string }>("/api/feedback", { method: "POST", body: fd });
}

/** GET /api/feedback — admin: list all reports, newest first. */
export async function getFeedbackList(): Promise<FeedbackItem[]> {
  return apiClient<FeedbackItem[]>("/api/feedback");
}

/** PATCH /api/feedback/{id} — admin: set status. */
export async function updateFeedbackStatus(
  id: string,
  status: FeedbackStatus,
): Promise<FeedbackItem> {
  return apiClient<FeedbackItem>(`/api/feedback/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

/** DELETE /api/feedback/{id} — admin: delete a report. */
export async function deleteFeedback(id: string): Promise<void> {
  await apiClient<void>(`/api/feedback/${id}`, { method: "DELETE" });
}

/** GET /api/feedback/unread-count — admin: number of not-yet-viewed reports. */
export async function getFeedbackUnreadCount(): Promise<number> {
  const r = await apiClient<{ count: number }>("/api/feedback/unread-count");
  return r.count;
}

/** POST /api/feedback/{id}/view — admin: mark one report as viewed. */
export async function markFeedbackViewed(id: string): Promise<FeedbackItem> {
  return apiClient<FeedbackItem>(`/api/feedback/${id}/view`, { method: "POST" });
}

// ---------------------------------------------------------------------------
// KPI-Bewertung & Maßnahmen (v1.107)
// ---------------------------------------------------------------------------

export type KpiRating = "red" | "yellow" | "green";
export type KpiMeasurePriority = "low" | "medium" | "high";
export type KpiMeasureStatus = "open" | "in_progress" | "done" | "dropped";

export interface KpiRegistryItem {
  key: string;
  domain: string;
}

export interface KpiSummaryItem {
  kpi_key: string;
  domain: string;
  comment_count: number;
  open_measure_count: number;
  last_rating: KpiRating | null;
}

export interface KpiComment {
  id: string;
  kpi_key: string;
  body: string;
  rating: KpiRating | null;
  author_id: string | null;
  author_name: string | null;
  created_at: string;
  // NULL = bubble not yet viewed by an admin (feeds the top-right counter).
  viewed_at: string | null;
  // Bubble on the chart: contiguous number + normalized region (0..1). Null = plain comment.
  number: number | null;
  region_x: number | null;
  region_y: number | null;
  region_w: number | null;
  region_h: number | null;
}

export interface KpiMeasure {
  id: string;
  kpi_key: string;
  comment_id: string | null;
  title: string;
  description: string;
  assignee_personio_id: string | null;
  assignee_name: string | null;
  due_date: string | null;
  priority: KpiMeasurePriority;
  status: KpiMeasureStatus;
  created_by_id: string | null;
  created_at: string;
  done_at: string | null;
}

export async function fetchKpiReviewSummary(): Promise<KpiSummaryItem[]> {
  return apiClient<KpiSummaryItem[]>("/api/kpi-review/summary");
}

export async function fetchKpiComments(kpiKey: string): Promise<KpiComment[]> {
  return apiClient<KpiComment[]>(
    `/api/kpi-review/comments?kpi_key=${encodeURIComponent(kpiKey)}`,
  );
}

export async function createKpiComment(input: {
  kpi_key: string;
  body: string;
  rating?: KpiRating | null;
  author_name?: string;
  region_x?: number;
  region_y?: number;
  region_w?: number;
  region_h?: number;
}): Promise<KpiComment> {
  return apiClient<KpiComment>("/api/kpi-review/comments", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function deleteKpiComment(id: string): Promise<void> {
  await apiClient<void>(`/api/kpi-review/comments/${id}`, { method: "DELETE" });
}

/** GET /api/kpi-review/bubbles — admin: all bubbles across KPIs. */
export async function getBubbles(): Promise<KpiComment[]> {
  return apiClient<KpiComment[]>("/api/kpi-review/bubbles");
}

/** GET /api/kpi-review/bubbles/unread — admin: bubbles not yet viewed. */
export async function getUnreadBubbles(): Promise<KpiComment[]> {
  return apiClient<KpiComment[]>("/api/kpi-review/bubbles/unread");
}

/** POST /api/kpi-review/comments/{id}/view — admin: mark a bubble viewed. */
export async function markBubbleViewed(id: string): Promise<KpiComment> {
  return apiClient<KpiComment>(`/api/kpi-review/comments/${id}/view`, {
    method: "POST",
  });
}

export async function fetchKpiMeasures(params?: {
  kpi_key?: string;
  status?: KpiMeasureStatus;
}): Promise<KpiMeasure[]> {
  const q = new URLSearchParams();
  if (params?.kpi_key) q.set("kpi_key", params.kpi_key);
  if (params?.status) q.set("status", params.status);
  const qs = q.toString();
  return apiClient<KpiMeasure[]>(`/api/kpi-review/measures${qs ? `?${qs}` : ""}`);
}

export async function createKpiMeasure(input: {
  kpi_key: string;
  comment_id?: string | null;
  title: string;
  description?: string;
  assignee_personio_id?: string | null;
  assignee_name?: string | null;
  due_date?: string | null;
  priority?: KpiMeasurePriority;
}): Promise<KpiMeasure> {
  return apiClient<KpiMeasure>("/api/kpi-review/measures", {
    method: "POST",
    body: JSON.stringify(input),
  });
}

export async function updateKpiMeasure(
  id: string,
  patch: Partial<{
    title: string;
    description: string;
    assignee_personio_id: string | null;
    assignee_name: string | null;
    due_date: string | null;
    priority: KpiMeasurePriority;
    status: KpiMeasureStatus;
  }>,
): Promise<KpiMeasure> {
  return apiClient<KpiMeasure>(`/api/kpi-review/measures/${id}`, {
    method: "PATCH",
    body: JSON.stringify(patch),
  });
}

export async function deleteKpiMeasure(id: string): Promise<void> {
  await apiClient<void>(`/api/kpi-review/measures/${id}`, { method: "DELETE" });
}
