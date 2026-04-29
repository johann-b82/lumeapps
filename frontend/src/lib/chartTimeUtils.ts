import {
  addDays,
  addMonths,
  addQuarters,
  differenceInCalendarDays,
  endOfISOWeek,
  endOfMonth,
  endOfQuarter,
  format,
  getISOWeek,
  getISOWeekYear,
  getQuarter,
  startOfISOWeek,
  startOfMonth,
  startOfQuarter,
} from "date-fns";

import type { ChartPoint } from "@/lib/api";

/**
 * Generate an array of YYYY-MM-01 date strings from startDate to endDate (inclusive),
 * advancing one month at a time.
 */
export function buildMonthSpine(startDate: string, endDate: string): string[] {
  const [startYear, startMonth] = startDate.split("-").map(Number);
  const [endYear, endMonth] = endDate.split("-").map(Number);

  const spine: string[] = [];
  let year = startYear;
  let month = startMonth;

  while (year < endYear || (year === endYear && month <= endMonth)) {
    const mm = String(month).padStart(2, "0");
    spine.push(`${year}-${mm}-01`);
    month++;
    if (month > 12) {
      month = 1;
      year++;
    }
  }

  return spine;
}

/**
 * Merge API data points into a spine, filling gaps with revenue: null.
 */
export function mergeIntoSpine(spine: string[], points: ChartPoint[]): ChartPoint[] {
  const map = new Map<string, number | null>();
  for (const p of points) {
    map.set(p.date.slice(0, 7), p.revenue);
  }
  return spine.map((date) => ({
    date,
    revenue: map.get(date.slice(0, 7)) ?? null,
  }));
}

/**
 * Format a YYYY-MM-DD date string as "Mon 'YY" (e.g. "Nov '25") for the given locale.
 */
export function formatMonthYear(dateStr: string, locale: string): string {
  const date = new Date(dateStr);
  const month = new Intl.DateTimeFormat(locale, { month: "short" }).format(date);
  const year = String(date.getFullYear()).slice(-2);
  return `${month} '${year}`;
}

/**
 * Return only the dates from the spine that fall in January (year boundary markers).
 */
export function yearBoundaryDates(spine: string[]): string[] {
  return spine.filter((d) => d.slice(5, 7) === "01");
}

// ---------------------------------------------------------------------------
// Phase 60 — D-06 HR chart bucket derivation
// Pure utility: given an inclusive [from, to] range, pick a granularity per
// D-06 thresholds and emit bucket descriptors with clipped edges + formatted
// labels. Consumed by HrKpiCharts in Plan 60-03.
// ---------------------------------------------------------------------------

export type HrBucketGranularity =
  | "daily"
  | "weekly"
  | "monthly"
  | "quarterly";

export interface HrBucket {
  label: string;
  start: Date;
  end: Date;
}

export interface HrBucketPlan {
  granularity: HrBucketGranularity;
  buckets: HrBucket[];
}

/**
 * Format a bucket's start date according to its granularity.
 * - daily     → "YYYY-MM-DD"
 * - weekly    → "YYYY-Www" (ISO week year + zero-padded ISO week number)
 * - monthly   → "YYYY-MM"
 * - quarterly → "YYYY-Qn"
 */
export function formatBucketLabel(
  granularity: HrBucketGranularity,
  d: Date,
): string {
  switch (granularity) {
    case "daily":
      return format(d, "yyyy-MM-dd");
    case "weekly": {
      const week = String(getISOWeek(d)).padStart(2, "0");
      return `${getISOWeekYear(d)}-W${week}`;
    }
    case "monthly":
      return format(d, "yyyy-MM");
    case "quarterly":
      return `${d.getFullYear()}-Q${getQuarter(d)}`;
  }
}

function pickGranularity(lengthDays: number): HrBucketGranularity {
  if (lengthDays <= 31) return "daily";
  if (lengthDays <= 91) return "weekly";
  if (lengthDays <= 731) return "monthly";
  return "quarterly";
}

/**
 * Derive the bucket plan (granularity + clipped bucket list) for an inclusive
 * [from, to] range. If `from > to` returns `{ granularity: "daily", buckets: [] }`.
 * Granularity thresholds (inclusive):
 *   - length_days ≤ 31   → daily
 *   - length_days ≤ 91   → weekly (ISO week)
 *   - length_days ≤ 731  → monthly
 *   - otherwise           → quarterly
 */
export function deriveHrBuckets(from: Date, to: Date): HrBucketPlan {
  if (from.getTime() > to.getTime()) {
    return { granularity: "daily", buckets: [] };
  }
  const lengthDays = differenceInCalendarDays(to, from) + 1;
  const granularity = pickGranularity(lengthDays);
  const buckets: HrBucket[] = [];

  const clipStart = (d: Date): Date => (d.getTime() < from.getTime() ? from : d);
  const clipEnd = (d: Date): Date => (d.getTime() > to.getTime() ? to : d);

  switch (granularity) {
    case "daily": {
      let cursor = from;
      while (cursor.getTime() <= to.getTime()) {
        buckets.push({
          label: formatBucketLabel("daily", cursor),
          start: cursor,
          end: cursor,
        });
        cursor = addDays(cursor, 1);
      }
      break;
    }
    case "weekly": {
      let cursor = startOfISOWeek(from);
      while (cursor.getTime() <= to.getTime()) {
        const weekEnd = endOfISOWeek(cursor);
        buckets.push({
          label: formatBucketLabel("weekly", cursor),
          start: clipStart(cursor),
          end: clipEnd(weekEnd),
        });
        cursor = addDays(weekEnd, 1);
      }
      break;
    }
    case "monthly": {
      let cursor = startOfMonth(from);
      while (cursor.getTime() <= to.getTime()) {
        const monthEnd = endOfMonth(cursor);
        buckets.push({
          label: formatBucketLabel("monthly", cursor),
          start: clipStart(cursor),
          end: clipEnd(monthEnd),
        });
        cursor = addMonths(cursor, 1);
      }
      break;
    }
    case "quarterly": {
      let cursor = startOfQuarter(from);
      while (cursor.getTime() <= to.getTime()) {
        const qEnd = endOfQuarter(cursor);
        buckets.push({
          label: formatBucketLabel("quarterly", cursor),
          start: clipStart(cursor),
          end: clipEnd(qEnd),
        });
        cursor = addQuarters(cursor, 1);
      }
      break;
    }
  }

  return { granularity, buckets };
}
