import {
  startOfYear,
  startOfMonth,
  startOfQuarter,
  format,
} from "date-fns";

export type Preset = "thisMonth" | "thisQuarter" | "thisYear" | "allTime";

/**
 * Resolve a preset name to an actual date range.
 *
 * Phase 9: switched to to-date (MTD/QTD/YTD) semantics so current and
 * prior windows can be compared day-for-day in the dual-delta KPI cards.
 * A `today` override parameter is accepted for deterministic testing.
 *
 * Before v1.2 this returned full calendar periods
 * (`[startOfMonth, endOfMonth]`); comparing 11 days of April against a
 * full 30-day March would distort deltas, so thisMonth/thisQuarter/
 * thisYear now clamp the upper bound to `today`.
 */
export function getPresetRange(
  preset: Preset,
  today: Date = new Date(),
): { from?: Date; to?: Date } {
  switch (preset) {
    case "thisMonth":
      return { from: startOfMonth(today), to: today };
    case "thisQuarter":
      return { from: startOfQuarter(today), to: today };
    case "thisYear":
      return { from: startOfYear(today), to: today };
    case "allTime":
      return { from: undefined, to: undefined };
  }
}

export function toApiDate(d: Date | undefined): string | undefined {
  return d ? format(d, "yyyy-MM-dd") : undefined;
}
