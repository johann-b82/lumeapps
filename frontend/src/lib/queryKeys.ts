import type { PrevBounds } from "./prevBounds.ts";
import type { ComparisonMode } from "./chartComparisonMode.ts";

export const kpiKeys = {
  all: ["kpis"] as const,
  /**
   * Phase 9: the cache key now embeds prev bounds so TanStack Query
   * invalidates whenever the user changes preset or custom range. The
   * `prev` argument is optional so existing v1.1 callers continue to
   * compile; plan 09-03 upgrades KpiCardGrid to pass it.
   */
  summary: (start?: string, end?: string, prev?: PrevBounds) =>
    ["kpis", "summary", { start, end, prev }] as const,
  /**
   * Phase 10: embed comparison mode + prev bounds so TanStack Query
   * invalidates whenever the user changes preset or the derived prior
   * window shifts. Lock-step with KpiCardGrid's summary key (SC5).
   */
  chart: (
    start: string | undefined,
    end: string | undefined,
    granularity: string,
    comparison?: ComparisonMode,
    prevStart?: string,
    prevEnd?: string,
  ) =>
    [
      "kpis",
      "chart",
      { start, end, granularity, comparison, prevStart, prevEnd },
    ] as const,
  latestUpload: () => ["kpis", "latest-upload"] as const,
};

export const syncKeys = {
  meta: () => ["sync", "meta"] as const,
};

export const hrKpiKeys = {
  all: () => ["hr", "kpis"] as const,
  summary: (from?: string, to?: string) =>
    ["hr", "kpis", "summary", { from, to }] as const,
  history: (from?: string, to?: string) =>
    ["hr", "kpis", "history", { from, to }] as const,
  employees: (from?: string, to?: string, search?: string) =>
    ["hr", "employees", { from, to, search }] as const,
  birthdaysThisWeek: () => ["hr", "birthdays", "this-week"] as const,
  joinersRecent: () => ["hr", "joiners", "recent"] as const,
  orgChart: () => ["hr", "org-chart"] as const,
  schulungen: () => ["hr", "schulungen"] as const,
  schulungAbteilungen: () => ["hr", "schulungen", "abteilungen"] as const,
  schulungPflicht: (ebene: string) => ["hr", "schulungen", "pflicht", ebene] as const,
  schulungOffen: () => ["hr", "schulungen", "offen"] as const,
  schulungZuweisbar: () => ["hr", "schulungen", "zuweisbar"] as const,
  kompetenzMatrizen: () => ["hr", "kompetenzen", "matrizen"] as const,
  kompetenzMatrix: (id: number) => ["hr", "kompetenzen", "matrix", id] as const,
  kompetenzVerfuegbar: (id: number) => ["hr", "kompetenzen", "verfuegbar", id] as const,
  onboardingEintritte: () => ["hr", "onboarding", "eintritte"] as const,
  onboardingPlan: (id: number) => ["hr", "onboarding", "plan", id] as const,
  onboardingRollen: () => ["hr", "onboarding", "rollen"] as const,
  onboardingKuerzel: () => ["hr", "onboarding", "kuerzel"] as const,
  onboardingAbteilungen: () => ["hr", "onboarding", "abteilungen"] as const,
  onboardingDokumente: () => ["hr", "onboarding", "dokumente"] as const,
  einarbeitungMatrix: () => ["hr", "einarbeitung", "matrix"] as const,
  einarbeitungAbteilungen: () => ["hr", "einarbeitung", "abteilungen"] as const,
  einarbeitungAnsprechpartner: () => ["hr", "einarbeitung", "ansprechpartner"] as const,
  schulungMitarbeiter: () => ["hr", "schulungen", "mitarbeiter"] as const,
  schulungMitarbeiterDetail: (persnr: string) =>
    ["hr", "schulungen", "mitarbeiter", persnr] as const,
};

/**
 * Phase 39 — sensor query keys. `readings` embeds the hours window so TanStack
 * Query invalidates automatically when the SegmentedControl changes.
 */
export const sensorKeys = {
  all: ["sensors"] as const,
  list: () => ["sensors", "list"] as const,
  readings: (sensorId: number, hours: number) =>
    ["sensors", "readings", { sensorId, hours }] as const,
  status: () => ["sensors", "status"] as const,
};

/**
 * Phase 73 (CACHE-01) — signage admin query keys.
 *
 * Returns post-v1.22 namespaces:
 *   - `['directus', '<collection>', ...]` for Directus-backed reads
 *     (media, playlists, devices, tags, schedules) — collection name
 *     matches the Directus collection slug exactly (D-01a).
 *   - `['fastapi', 'analytics', 'devices']` for `deviceAnalytics()` —
 *     /api/signage/analytics/devices is a FastAPI surface, not a
 *     Directus collection (D-02).
 *
 * Item-level keys preserve the (id) suffix for per-row invalidation.
 * `signageKeys.all` was removed — `['directus']` would be too broad a
 * prefix to invalidate.
 */
export const signageKeys = {
  media: () => ["directus", "signage_media"] as const,
  mediaItem: (id: string) => ["directus", "signage_media", id] as const,
  playlists: () => ["directus", "signage_playlists"] as const,
  playlistItem: (id: string) => ["directus", "signage_playlists", id] as const,
  devices: () => ["directus", "signage_devices"] as const,
  deviceAnalytics: () => ["fastapi", "analytics", "devices"] as const,
  tags: () => ["directus", "signage_tags"] as const,
  schedules: () => ["directus", "signage_schedules"] as const,
  scheduleItem: (id: string) => ["directus", "signage_schedules", id] as const,
};

// v1.49 — Quality (8D audit findings + later complaints).
export const qualityKeys = {
  all: ["quality"] as const,
  auditFindings: (from?: string, to?: string, types?: readonly string[]) =>
    ["quality", "audit-findings", { from, to, types }] as const,
  auditFindingsHistory: (
    from?: string,
    to?: string,
    types?: readonly string[],
    granularity?: string,
  ) =>
    [
      "quality",
      "audit-findings",
      "history",
      { from, to, types, granularity },
    ] as const,
  auditFindingsList: (from?: string, to?: string, types?: readonly string[]) =>
    ["quality", "audit-findings", "list", { from, to, types }] as const,
  complaintRate: (
    from?: string,
    to?: string,
    qtyMode?: string,
    complaintType?: string,
  ) =>
    ["quality", "complaint-rate", { from, to, qtyMode, complaintType }] as const,
  complaintRateHistory: (
    from?: string,
    to?: string,
    qtyMode?: string,
    complaintType?: string,
    granularity?: string,
  ) =>
    [
      "quality",
      "complaint-rate",
      "history",
      { from, to, qtyMode, complaintType, granularity },
    ] as const,
  complaintsList: (from?: string, to?: string, complaintType?: string) =>
    ["quality", "complaints", "list", { from, to, complaintType }] as const,
  inspections: (from?: string, to?: string) =>
    ["quality", "inspections", { from, to }] as const,
  inspectionsHistory: (from?: string, to?: string, granularity?: string) =>
    ["quality", "inspections", "history", { from, to, granularity }] as const,
  inspectionsList: (from?: string, to?: string) =>
    ["quality", "inspections", "list", { from, to }] as const,
  inspectionsBookings: (from?: string, to?: string) =>
    ["quality", "inspections", "bookings", { from, to }] as const,
};

// v1.60 — Einkauf (procurement): Liefertermintreue / OTD.
export const procurementKeys = {
  all: ["procurement"] as const,
  otd: (from?: string, to?: string) =>
    ["procurement", "otd", { from, to }] as const,
  otdHistory: (from?: string, to?: string, granularity?: string) =>
    ["procurement", "otd", "history", { from, to, granularity }] as const,
  otdList: (from?: string, to?: string) =>
    ["procurement", "otd", "list", { from, to }] as const,
};

// v1.76 — Produktion: Aufträge in Verzug (Seriengeschäft).
export const productionKeys = {
  all: ["production"] as const,
  verzug: (from?: string, to?: string) =>
    ["production", "verzug", { from, to }] as const,
  verzugHistory: (from?: string, to?: string, granularity?: string) =>
    ["production", "verzug", "history", { from, to, granularity }] as const,
  verzugList: (from?: string, to?: string) =>
    ["production", "verzug", "list", { from, to }] as const,
  verzugOverdue: (from?: string, to?: string) =>
    ["production", "verzug", "overdue", { from, to }] as const,
};

// v1.70 — Finanzperspektive: Materialkostenquote.
export const financeKeys = {
  all: ["finance"] as const,
  materialCostRatio: (from?: string, to?: string) =>
    ["finance", "material-cost-ratio", { from, to }] as const,
  materialCostRatioHistory: (from?: string, to?: string, granularity?: string) =>
    ["finance", "material-cost-ratio", "history", { from, to, granularity }] as const,
  materialCostRatioList: (from?: string, to?: string) =>
    ["finance", "material-cost-ratio", "list", { from, to }] as const,
  personnelCostRatio: (from?: string, to?: string) =>
    ["finance", "personnel-cost-ratio", { from, to }] as const,
  personnelCostRatioHistory: (from?: string, to?: string, granularity?: string) =>
    ["finance", "personnel-cost-ratio", "history", { from, to, granularity }] as const,
  personnelCostRatioList: (from?: string, to?: string) =>
    ["finance", "personnel-cost-ratio", "list", { from, to }] as const,
};

// v1.73 — FAIR drawing ballooning (Erstmusterprüfung).
export const fairKeys = {
  all: ["fair"] as const,
  projects: () => ["fair", "projects"] as const,
  project: (id: string) => ["fair", "projects", id] as const,
};

// v1.41 — Sales activity / orders distribution.
export const salesKeys = {
  all: ["sales"] as const,
  contactsWeekly: (from: string, to: string) =>
    ["sales", "contacts-weekly", from, to] as const,
  ordersDistribution: (from: string, to: string) =>
    ["sales", "orders-distribution", from, to] as const,
  customerShare: (source: "auftraege" | "revenues", from: string, to: string) =>
    ["sales", "customer-share", source, from, to] as const,
  aliases: () => ["sales", "aliases"] as const,
};
