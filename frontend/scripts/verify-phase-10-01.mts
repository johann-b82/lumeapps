// Phase 10-01 verification — run with:
//   node --experimental-strip-types frontend/scripts/verify-phase-10-01.mts
//
// Pure-util verification for:
//   - selectComparisonMode (all 4 presets)
//   - formatChartSeriesLabel (all 4 presets, including Q1→Q4 wrap)
//
// No vitest — matches Phase 9 "no new deps" invariant.

import { selectComparisonMode } from "../src/lib/chartComparisonMode.ts";
import { formatChartSeriesLabel } from "../src/lib/periodLabels.ts";

function assertEq<T>(actual: T, expected: T, label: string): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(
      `[FAIL] ${label}\n  expected: ${JSON.stringify(expected)}\n  actual:   ${JSON.stringify(actual)}`,
    );
  }
}

// selectComparisonMode — D-02 table
assertEq(selectComparisonMode("thisMonth"), "previous_period", "mode thisMonth");
assertEq(selectComparisonMode("thisQuarter"), "previous_period", "mode thisQuarter");
assertEq(selectComparisonMode("thisYear"), "previous_year", "mode thisYear");
assertEq(selectComparisonMode("allTime"), "none", "mode allTime");

// Fake i18next t — minimal interpolation
const fakeT = (key: string, opts?: Record<string, unknown>): string => {
  const templates: Record<string, string> = {
    "dashboard.chart.series.revenue": "Revenue",
    "dashboard.chart.series.revenueMonth": "Revenue {{month}}",
    "dashboard.chart.series.revenueQuarter": "Revenue Q{{quarter}}",
    "dashboard.chart.series.revenueYear": "Revenue {{year}}",
  };
  let out = templates[key] ?? key;
  if (opts) {
    for (const [k, v] of Object.entries(opts)) {
      out = out.replace(`{{${k}}}`, String(v));
    }
  }
  return out;
};

// thisMonth — April 2026 anchor
const apr15 = new Date(2026, 3, 15); // month is 0-indexed → April
assertEq(
  formatChartSeriesLabel("thisMonth", { from: undefined, to: apr15 }, "en", fakeT),
  { current: "Revenue April", prior: "Revenue March" },
  "label thisMonth (Apr 2026)",
);

// thisQuarter — Q2 2026
assertEq(
  formatChartSeriesLabel("thisQuarter", { from: undefined, to: apr15 }, "en", fakeT),
  { current: "Revenue Q2", prior: "Revenue Q1" },
  "label thisQuarter (Q2)",
);

// thisYear — 2026
assertEq(
  formatChartSeriesLabel("thisYear", { from: undefined, to: apr15 }, "en", fakeT),
  { current: "Revenue 2026", prior: "Revenue 2025" },
  "label thisYear (2026)",
);

// allTime — no prior
assertEq(
  formatChartSeriesLabel("allTime", { from: undefined, to: undefined }, "en", fakeT),
  { current: "Revenue", prior: "" },
  "label allTime",
);

// Q1 rollover — January 2026 should yield Q1 / Q4
const jan15 = new Date(2026, 0, 15);
assertEq(
  formatChartSeriesLabel("thisQuarter", { from: undefined, to: jan15 }, "en", fakeT),
  { current: "Revenue Q1", prior: "Revenue Q4" },
  "label thisQuarter Q1→Q4 wrap",
);

console.log("Phase 10-01: selectComparisonMode + formatChartSeriesLabel — ALL GREEN");
