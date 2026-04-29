/**
 * Chart series label helper for RevenueChart.
 *
 * Phase 24 — stripped of the dual-delta badge formatters (formatPrevPeriodLabel,
 * formatPrevYearLabel) after those consumers migrated to the shared
 * kpi.delta.* i18n namespace. `formatChartSeriesLabel` remains because
 * RevenueChart.tsx still consumes it for its two-series legend.
 *
 * This file deliberately does NOT import i18next — it stays a pure
 * utility module; callers inject t() from their own useTranslation() hook.
 */
import { subMonths } from "date-fns";
import type { DateRangeValue } from "../components/dashboard/DateRangeFilter.tsx";
import type { Preset } from "./dateUtils.ts";

export type SupportedLocale = "de" | "en";

type ChartLabelT = (
  key: string,
  options?: Record<string, unknown>,
) => string;

/**
 * Locale-aware month name helper.
 *
 * Wraps Intl.DateTimeFormat with a fixed year-2000 seed date to avoid
 * DST/day-boundary edge cases.
 */
export function getLocalizedMonthName(
  monthIndex: number,
  locale: SupportedLocale,
): string {
  return new Intl.DateTimeFormat(locale, { month: "long" }).format(
    new Date(2000, monthIndex, 1),
  );
}

export interface ChartSeriesLabels {
  current: string;
  prior: string;
}

/**
 * Phase 10 — contextual legend labels for RevenueChart's two series.
 *
 * Returns `{ current, prior }` strings resolved via the injected
 * `t()` function (keeps this file i18next-free — caller passes
 * `t` from its own useTranslation() hook). Locale is needed for
 * month-name formatting via Intl.DateTimeFormat.
 *
 * Decision table (CONTEXT §C D-10):
 *   thisMonth   → "Revenue April" / "Revenue March"
 *   thisQuarter → "Revenue Q2"    / "Revenue Q1"    (Q1 rolls to Q4)
 *   thisYear    → "Revenue 2026"  / "Revenue 2025"
 *   allTime     → "Revenue"       / ""  (prior empty — overlay suppressed)
 */
export function formatChartSeriesLabel(
  preset: Preset,
  range: DateRangeValue,
  locale: SupportedLocale,
  t: ChartLabelT,
): ChartSeriesLabels {
  const anchor = range.to ?? new Date();

  if (preset === "thisMonth") {
    return {
      current: t("dashboard.chart.series.revenueMonth", {
        month: getLocalizedMonthName(anchor.getMonth(), locale),
      }),
      prior: t("dashboard.chart.series.revenueMonth", {
        month: getLocalizedMonthName(subMonths(anchor, 1).getMonth(), locale),
      }),
    };
  }

  if (preset === "thisQuarter") {
    const currentQ = Math.floor(anchor.getMonth() / 3) + 1;
    const priorQ = currentQ === 1 ? 4 : currentQ - 1;
    return {
      current: t("dashboard.chart.series.revenueQuarter", {
        quarter: currentQ,
      }),
      prior: t("dashboard.chart.series.revenueQuarter", {
        quarter: priorQ,
      }),
    };
  }

  if (preset === "thisYear") {
    const currentYear = anchor.getFullYear();
    const priorYear = currentYear - 1;
    return {
      current: t("dashboard.chart.series.revenueYear", {
        year: currentYear,
      }),
      prior: t("dashboard.chart.series.revenueYear", {
        year: priorYear,
      }),
    };
  }

  // preset === "allTime"
  return {
    current: t("dashboard.chart.series.revenue"),
    prior: "",
  };
}

/**
 * Phase 24 follow-up — concrete prior-period delta-badge labels.
 *
 * The KPI delta badges previously showed generic strings ("vs. prev. month").
 * Per user feedback the badges must name the concrete prior period, e.g.
 * "vs. February 2026" / "vs. Februar 2026", "vs. Q1 2026", "vs. 2025".
 *
 * Returns `{ prevPeriod, prevYear }` strings resolved via the injected
 * `t()` function. Returns `null` for `allTime` / null preset — caller
 * hides the badge row entirely (D-12).
 *
 * Decision table (mirrors formatChartSeriesLabel anchoring):
 *   thisMonth   → prevPeriod = "vs. <prior month name> <prior month year>"
 *                 prevYear   = "vs. <prior year>"
 *   thisQuarter → prevPeriod = "vs. Q<prior quarter> <prior quarter year>"
 *                 prevYear   = "vs. <prior year>"
 *   thisYear    → prevPeriod = "vs. <prior year>"  (top row — caller maps the
 *                                                    YTD-vs-YTD delta here)
 *                 prevYear   = null                 (bottom row hidden)
 *   allTime/null → null      (caller hides badges)
 */
export interface DeltaPeriodLabels {
  prevPeriod: string;
  // null = hide the bottom badge row entirely (thisYear collapses to a
  // single top-row YTD-vs-YTD badge per user request, 24-01 follow-up).
  prevYear: string | null;
}

export function formatPrevPeriodDeltaLabels(
  preset: Preset | null,
  range: DateRangeValue,
  locale: SupportedLocale,
  t: ChartLabelT,
): DeltaPeriodLabels | null {
  if (preset === null || preset === "allTime") return null;

  const anchor = range.to ?? new Date();
  const currentYear = anchor.getFullYear();
  const priorYear = currentYear - 1;
  const prevYearLabel = t("kpi.delta.vsYear", { year: priorYear });

  if (preset === "thisMonth") {
    const priorMonthDate = subMonths(anchor, 1);
    return {
      prevPeriod: t("kpi.delta.vsMonth", {
        month: getLocalizedMonthName(priorMonthDate.getMonth(), locale),
        year: priorMonthDate.getFullYear(),
      }),
      // Bottom row for thisMonth: SAME month, PRIOR year (e.g. April 2026 → April 2025).
      // Not "vs. {priorYear}" — users want month-over-month YoY comparability,
      // matching the thisQuarter same-quarter-prior-year pattern below.
      prevYear: t("kpi.delta.vsMonth", {
        month: getLocalizedMonthName(anchor.getMonth(), locale),
        year: priorYear,
      }),
    };
  }

  if (preset === "thisQuarter") {
    const currentQ = Math.floor(anchor.getMonth() / 3) + 1;
    const priorQ = currentQ === 1 ? 4 : currentQ - 1;
    const priorQYear = currentQ === 1 ? currentYear - 1 : currentYear;
    return {
      prevPeriod: t("kpi.delta.vsQuarter", {
        quarter: priorQ,
        year: priorQYear,
      }),
      // Bottom row for thisQuarter: SAME quarter, PRIOR year (e.g. Q2 2026 → Q2 2025).
      // Not "vs. {priorYear}" — users want quarter-over-quarter YoY comparability.
      prevYear: t("kpi.delta.vsQuarter", {
        quarter: currentQ,
        year: priorYear,
      }),
    };
  }

  // preset === "thisYear" — collapse to a single top-row badge labeled
  // "vs. <prior year>". Bottom row is suppressed (null). KpiCardGrid maps
  // the YTD-vs-YTD delta (prevYearDelta) into the top slot for this preset.
  return {
    prevPeriod: prevYearLabel,
    prevYear: null,
  };
}

/**
 * HR variant — HR dashboard has no preset/range; comparisons are always
 * "vs. previous month" (anchored at today) and "vs. previous year".
 * Returns concrete labels, e.g. "vs. March 2026" + "vs. 2025".
 */
export function formatHrDeltaLabels(
  locale: SupportedLocale,
  t: ChartLabelT,
  today: Date = new Date(),
): DeltaPeriodLabels {
  const priorMonthDate = subMonths(today, 1);
  const priorYear = today.getFullYear() - 1;
  return {
    prevPeriod: t("kpi.delta.vsMonth", {
      month: getLocalizedMonthName(priorMonthDate.getMonth(), locale),
      year: priorMonthDate.getFullYear(),
    }),
    // Bottom row: SAME month, PRIOR year (e.g. April 2026 → April 2025).
    // Matches Sales thisMonth pattern for month-over-month YoY comparability.
    prevYear: t("kpi.delta.vsMonth", {
      month: getLocalizedMonthName(today.getMonth(), locale),
      year: priorYear,
    }),
  };
}
