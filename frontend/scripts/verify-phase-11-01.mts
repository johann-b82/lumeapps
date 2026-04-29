// Phase 11-01 verification — run with:
//   node --experimental-strip-types frontend/scripts/verify-phase-11-01.mts
//
// Asserts:
//   - getLocalizedMonthName (4 cases)
//   - formatPrevPeriodLabel with injected t (11 cases, de + en)
//   - formatChartSeriesLabel with fakeT_de for thisMonth
//
// No vitest — matches Phase 9/10 "no new deps" invariant.

import {
  getLocalizedMonthName,
  formatPrevPeriodLabel,
  formatChartSeriesLabel,
} from "../src/lib/periodLabels.ts";

function assertEq<T>(actual: T, expected: T, label: string): void {
  if (JSON.stringify(actual) !== JSON.stringify(expected)) {
    throw new Error(
      `[FAIL] ${label}\n  expected: ${JSON.stringify(expected)}\n  actual:   ${JSON.stringify(actual)}`,
    );
  }
}

// --- Fake t() implementations for DE and EN ---

const fakeT_de = (key: string, opts?: Record<string, unknown>): string => {
  const templates: Record<string, string> = {
    "dashboard.chart.series.revenue": "Umsatz",
    "dashboard.chart.series.revenueMonth": "Umsatz {{month}}",
    "dashboard.chart.series.revenueQuarter": "Umsatz Q{{quarter}}",
    "dashboard.chart.series.revenueYear": "Umsatz {{year}}",
    "dashboard.delta.vsShortPeriod": "vs. {{count}} Tage zuvor",
    "dashboard.delta.vsShortPeriod_one": "vs. 1 Tag zuvor",
    "dashboard.delta.vsCustomPeriod": "vs. Vorperiode",
    "dashboard.delta.vsYear": "vs. {{year}}",
  };
  // i18next-style plural resolution for the short-period key: when count===1
  // prefer the _one suffix. This mirrors what real i18next does at runtime.
  let resolvedKey = key;
  if (opts && typeof opts.count === "number" && opts.count === 1) {
    if (templates[`${key}_one`]) resolvedKey = `${key}_one`;
  }
  let out = templates[resolvedKey] ?? resolvedKey;
  if (opts) {
    for (const [k, v] of Object.entries(opts)) {
      out = out.replace(`{{${k}}}`, String(v));
    }
  }
  return out;
};

const fakeT_en = (key: string, opts?: Record<string, unknown>): string => {
  const templates: Record<string, string> = {
    "dashboard.chart.series.revenue": "Revenue",
    "dashboard.chart.series.revenueMonth": "Revenue {{month}}",
    "dashboard.chart.series.revenueQuarter": "Revenue Q{{quarter}}",
    "dashboard.chart.series.revenueYear": "Revenue {{year}}",
    "dashboard.delta.vsShortPeriod": "vs. {{count}} days earlier",
    "dashboard.delta.vsShortPeriod_one": "vs. 1 day earlier",
    "dashboard.delta.vsCustomPeriod": "vs. previous period",
    "dashboard.delta.vsYear": "vs. {{year}}",
  };
  // i18next-style plural resolution: when count===1 prefer the _one suffix
  let resolvedKey = key;
  if (opts && typeof opts.count === "number" && opts.count === 1) {
    if (templates[`${key}_one`]) resolvedKey = `${key}_one`;
  }
  let out = templates[resolvedKey] ?? resolvedKey;
  if (opts) {
    for (const [k, v] of Object.entries(opts)) {
      out = out.replace(`{{${k}}}`, String(v));
    }
  }
  return out;
};

// --- getLocalizedMonthName assertions (4 cases) ---

assertEq(getLocalizedMonthName(3, "de"), "April", "getLocalizedMonthName(3, 'de') === 'April'");
assertEq(getLocalizedMonthName(2, "de"), "März", "getLocalizedMonthName(2, 'de') === 'März'");
assertEq(getLocalizedMonthName(2, "en"), "March", "getLocalizedMonthName(2, 'en') === 'March'");
assertEq(getLocalizedMonthName(0, "de"), "Januar", "getLocalizedMonthName(0, 'de') === 'Januar'");

// --- formatPrevPeriodLabel assertions (11 cases) ---

// thisMonth — DE: "vs. März", EN: "vs. March"
assertEq(
  formatPrevPeriodLabel("thisMonth", new Date(2026, 2, 1), "de", fakeT_de),
  "vs. März",
  "formatPrevPeriodLabel thisMonth de",
);
assertEq(
  formatPrevPeriodLabel("thisMonth", new Date(2026, 2, 1), "en", fakeT_en),
  "vs. March",
  "formatPrevPeriodLabel thisMonth en",
);

// thisQuarter — locale-invariant "vs. Q1"
assertEq(
  formatPrevPeriodLabel("thisQuarter", new Date(2026, 0, 1), "de", fakeT_de),
  "vs. Q1",
  "formatPrevPeriodLabel thisQuarter de",
);
assertEq(
  formatPrevPeriodLabel("thisQuarter", new Date(2026, 0, 1), "en", fakeT_en),
  "vs. Q1",
  "formatPrevPeriodLabel thisQuarter en",
);

// custom short 3 days — DE: "vs. 3 Tage zuvor", EN: "vs. 3 days earlier"
assertEq(
  formatPrevPeriodLabel(null, new Date(2026, 3, 1), "de", fakeT_de, 3),
  "vs. 3 Tage zuvor",
  "formatPrevPeriodLabel custom 3d de",
);
assertEq(
  formatPrevPeriodLabel(null, new Date(2026, 3, 1), "en", fakeT_en, 3),
  "vs. 3 days earlier",
  "formatPrevPeriodLabel custom 3d en",
);

// custom short 1 day — plural _one: DE: "vs. 1 Tag zuvor", EN: "vs. 1 day earlier"
assertEq(
  formatPrevPeriodLabel(null, new Date(2026, 3, 1), "de", fakeT_de, 1),
  "vs. 1 Tag zuvor",
  "formatPrevPeriodLabel custom 1d de (_one plural)",
);
assertEq(
  formatPrevPeriodLabel(null, new Date(2026, 3, 1), "en", fakeT_en, 1),
  "vs. 1 day earlier",
  "formatPrevPeriodLabel custom 1d en (_one plural)",
);

// custom generic (no rangeLengthDays) — DE: "vs. Vorperiode", EN: "vs. previous period"
assertEq(
  formatPrevPeriodLabel(null, new Date(2026, 3, 1), "de", fakeT_de),
  "vs. Vorperiode",
  "formatPrevPeriodLabel custom generic de",
);
assertEq(
  formatPrevPeriodLabel(null, new Date(2026, 3, 1), "en", fakeT_en),
  "vs. previous period",
  "formatPrevPeriodLabel custom generic en",
);

// em-dash cases — thisYear and allTime
assertEq(
  formatPrevPeriodLabel("thisYear", null, "de", fakeT_de),
  "—",
  "formatPrevPeriodLabel thisYear → em-dash",
);
assertEq(
  formatPrevPeriodLabel("allTime", null, "de", fakeT_de),
  "—",
  "formatPrevPeriodLabel allTime → em-dash",
);

// --- formatChartSeriesLabel with fakeT_de for thisMonth ---

const apr15 = new Date(2026, 3, 15); // April 2026
assertEq(
  formatChartSeriesLabel("thisMonth", { from: undefined, to: apr15 }, "de", fakeT_de),
  { current: "Umsatz April", prior: "Umsatz März" },
  "formatChartSeriesLabel thisMonth de (April/März)",
);

console.log("Phase 11-01: locale parity + periodLabels t() routing — ALL GREEN");
