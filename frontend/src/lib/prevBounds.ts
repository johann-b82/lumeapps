/**
 * Phase 9 — Dual-delta KPI cards.
 *
 * Pure function that maps `(preset, range)` → the four optional
 * `prev_period_*` / `prev_year_*` query params the Phase 8 backend
 * `/api/kpis` endpoint expects.
 *
 * Implements CARD-04 / CARD-05 bounds math per 09-CONTEXT.md section C
 * and the Phase 8 decision D collapse (prev_period is deliberately
 * undefined for `thisYear`, since it would overlap with prev_year and
 * render the same badge twice).
 *
 * Returns `undefined` (not `null`) so the API layer can simply skip
 * unset keys in `URLSearchParams.set()`.
 */
import {
  addDays,
  differenceInDays,
  startOfMonth,
  startOfQuarter,
  startOfYear,
  subMonths,
  subQuarters,
  subYears,
} from "date-fns";

import { toApiDate } from "./dateUtils.ts";
import type { Preset } from "./dateUtils.ts";

export interface PrevBounds {
  prev_period_start?: string; // YYYY-MM-DD
  prev_period_end?: string;
  prev_year_start?: string;
  prev_year_end?: string;
}

/**
 * Compute prior-window bounds for the given preset + current range.
 *
 * The `today` parameter is injectable so the throwaway verification
 * script (`frontend/scripts/verify-phase-09-01.mts`) can pin time
 * without mocks.
 */
export function computePrevBounds(
  preset: Preset | null,
  range: { from?: Date; to?: Date },
  today: Date = new Date(),
): PrevBounds {
  // allTime → no comparison window at all
  if (preset === "allTime") {
    return {};
  }

  // thisMonth: prev_period = previous month, same day offset
  if (preset === "thisMonth") {
    const thisStart = startOfMonth(today);
    const offset = differenceInDays(today, thisStart);
    const prevStart = startOfMonth(subMonths(today, 1));
    const prevEnd = addDays(prevStart, offset);
    return {
      prev_period_start: toApiDate(prevStart),
      prev_period_end: toApiDate(prevEnd),
      prev_year_start: toApiDate(subYears(thisStart, 1)),
      prev_year_end: toApiDate(subYears(today, 1)),
    };
  }

  // thisQuarter: prev_period = previous quarter, same day offset
  if (preset === "thisQuarter") {
    const thisStart = startOfQuarter(today);
    const offset = differenceInDays(today, thisStart);
    const prevStart = startOfQuarter(subQuarters(today, 1));
    const prevEnd = addDays(prevStart, offset);
    return {
      prev_period_start: toApiDate(prevStart),
      prev_period_end: toApiDate(prevEnd),
      prev_year_start: toApiDate(subYears(thisStart, 1)),
      prev_year_end: toApiDate(subYears(today, 1)),
    };
  }

  // thisYear: prev_period collapses with prev_year (Phase 8 decision D)
  if (preset === "thisYear") {
    const thisStart = startOfYear(today);
    return {
      // prev_period_* intentionally undefined
      prev_year_start: toApiDate(subYears(thisStart, 1)),
      prev_year_end: toApiDate(subYears(today, 1)),
    };
  }

  // Custom (preset === null): uses explicit range
  if (preset === null && range.from && range.to) {
    const n = differenceInDays(range.to, range.from) + 1;
    const prevPeriodStart = addDays(range.from, -n);
    const prevPeriodEnd = addDays(range.to, -n);
    const prevYearStart = subYears(range.from, 1);
    const prevYearEnd = subYears(range.to, 1);
    return {
      prev_period_start: toApiDate(prevPeriodStart),
      prev_period_end: toApiDate(prevPeriodEnd),
      prev_year_start: toApiDate(prevYearStart),
      prev_year_end: toApiDate(prevYearEnd),
    };
  }

  // Fallback: no bounds
  return {};
}
