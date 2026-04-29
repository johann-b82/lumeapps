/**
 * Phase 10 — Chart prior-period overlay.
 *
 * Deterministic preset → comparison-mode mapping (D-01, D-02, D-03).
 * Pure function; no null branch (custom ranges were removed in
 * Phase 9-03 so `preset` is always one of the 4 enum values).
 *
 * Consumed by RevenueChart.tsx in plan 10-02 to drive fetchChartData's
 * `comparison` query param and to gate prior-series rendering.
 */
import type { Preset } from "./dateUtils.ts";

export type ComparisonMode = "previous_period" | "previous_year" | "none";

export function selectComparisonMode(preset: Preset): ComparisonMode {
  switch (preset) {
    case "thisMonth":
      return "previous_period";
    case "thisQuarter":
      return "previous_period";
    case "thisYear":
      return "previous_year";
    case "allTime":
      return "none";
  }
}
