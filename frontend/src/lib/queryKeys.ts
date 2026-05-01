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

// v1.41 — Sales activity / orders distribution.
export const salesKeys = {
  all: ["sales"] as const,
  contactsWeekly: (from: string, to: string) =>
    ["sales", "contacts-weekly", from, to] as const,
  ordersDistribution: (from: string, to: string) =>
    ["sales", "orders-distribution", from, to] as const,
  aliases: () => ["sales", "aliases"] as const,
};
