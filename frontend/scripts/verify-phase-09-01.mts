#!/usr/bin/env node
// Phase 9 Plan 01 — pure-function verification script.
//
// Run:
//   node --experimental-strip-types frontend/scripts/verify-phase-09-01.mts
//
// This file is intentionally a throwaway/bridge: no vitest or jest is
// installed (see 09-01-PLAN.md test_strategy). We assert with plain
// `throw` + a small helper. Exit code 0 on success.

import { computeDelta } from "../src/lib/delta.ts";
import { computePrevBounds } from "../src/lib/prevBounds.ts";
import {
  formatPrevPeriodLabel,
  formatPrevYearLabel,
} from "../src/lib/periodLabels.ts";
import { getPresetRange, toApiDate } from "../src/lib/dateUtils.ts";

function assertEq<T>(actual: T, expected: T, label: string): void {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) {
    throw new Error(`[FAIL] ${label}\n  expected: ${e}\n  actual:   ${a}`);
  }
}

// ────────────────────────────────────────────────────────────────
// Task 1: computeDelta
// ────────────────────────────────────────────────────────────────
assertEq(computeDelta(110, 100), 0.1, "computeDelta(110, 100) === 0.1");
assertEq(
  Number(computeDelta(90, 100)?.toFixed(10)),
  -0.1,
  "computeDelta(90, 100) === -0.1",
);
assertEq(computeDelta(0, 100), -1, "computeDelta(0, 100) === -1");
assertEq(computeDelta(100, null), null, "computeDelta(100, null) === null");
assertEq(computeDelta(100, 0), null, "computeDelta(100, 0) === null");
assertEq(computeDelta(0, 0), null, "computeDelta(0, 0) === null");

// ────────────────────────────────────────────────────────────────
// Task 1: computePrevBounds
// ────────────────────────────────────────────────────────────────
const TODAY = new Date("2026-04-11T12:00:00Z");

assertEq(
  computePrevBounds("thisMonth", {}, TODAY),
  {
    prev_period_start: "2026-03-01",
    prev_period_end: "2026-03-11",
    prev_year_start: "2025-04-01",
    prev_year_end: "2025-04-11",
  },
  "computePrevBounds thisMonth @ 2026-04-11",
);

assertEq(
  computePrevBounds("thisQuarter", {}, TODAY),
  {
    prev_period_start: "2026-01-01",
    prev_period_end: "2026-01-11",
    prev_year_start: "2025-04-01",
    prev_year_end: "2025-04-11",
  },
  "computePrevBounds thisQuarter @ 2026-04-11",
);

assertEq(
  computePrevBounds("thisYear", {}, TODAY),
  {
    prev_year_start: "2025-01-01",
    prev_year_end: "2025-04-11",
  },
  "computePrevBounds thisYear @ 2026-04-11 (prev_period collapsed)",
);

assertEq(
  computePrevBounds("allTime", {}, TODAY),
  {},
  "computePrevBounds allTime → {}",
);

assertEq(
  computePrevBounds(
    null,
    {
      from: new Date("2026-04-01T00:00:00"),
      to: new Date("2026-04-07T00:00:00"),
    },
    TODAY,
  ),
  {
    prev_period_start: "2026-03-25",
    prev_period_end: "2026-03-31",
    prev_year_start: "2025-04-01",
    prev_year_end: "2025-04-07",
  },
  "computePrevBounds custom 7-day window",
);

console.log("09-01 Task 1 assertions passed");

// ────────────────────────────────────────────────────────────────
// Task 2: formatPrevPeriodLabel
// ────────────────────────────────────────────────────────────────
const PREV_MONTH = new Date("2026-03-01T12:00:00");
const PREV_QUARTER = new Date("2026-01-01T12:00:00");
const PREV_CUSTOM = new Date("2026-04-04T12:00:00");
const PREV_CUSTOM_GENERIC = new Date("2026-01-01T12:00:00");

assertEq(
  formatPrevPeriodLabel("thisMonth", PREV_MONTH, "de"),
  "vs. März",
  "formatPrevPeriodLabel thisMonth de",
);
assertEq(
  formatPrevPeriodLabel("thisMonth", PREV_MONTH, "en"),
  "vs. March",
  "formatPrevPeriodLabel thisMonth en",
);
assertEq(
  formatPrevPeriodLabel("thisQuarter", PREV_QUARTER, "de"),
  "vs. Q1",
  "formatPrevPeriodLabel thisQuarter de",
);
assertEq(
  formatPrevPeriodLabel("thisQuarter", PREV_QUARTER, "en"),
  "vs. Q1",
  "formatPrevPeriodLabel thisQuarter en",
);
assertEq(
  formatPrevPeriodLabel("thisYear", null, "de"),
  "—",
  "formatPrevPeriodLabel thisYear de → em-dash",
);
assertEq(
  formatPrevPeriodLabel("thisYear", null, "en"),
  "—",
  "formatPrevPeriodLabel thisYear en → em-dash",
);
assertEq(
  formatPrevPeriodLabel("allTime", null, "de"),
  "—",
  "formatPrevPeriodLabel allTime de → em-dash",
);
assertEq(
  formatPrevPeriodLabel(null, PREV_CUSTOM, "de", 7),
  "vs. Vorperiode",
  "formatPrevPeriodLabel custom N=7 de → generic (N is not < 7)",
);
// Short range (< 7 days) branch
assertEq(
  formatPrevPeriodLabel(null, PREV_CUSTOM, "de", 3),
  "vs. 3 Tage zuvor",
  "formatPrevPeriodLabel custom N=3 de",
);
assertEq(
  formatPrevPeriodLabel(null, PREV_CUSTOM, "en", 3),
  "vs. 3 days earlier",
  "formatPrevPeriodLabel custom N=3 en",
);
assertEq(
  formatPrevPeriodLabel(null, PREV_CUSTOM, "en", 1),
  "vs. 1 day earlier",
  "formatPrevPeriodLabel custom N=1 en",
);
assertEq(
  formatPrevPeriodLabel(null, PREV_CUSTOM_GENERIC, "de", 60),
  "vs. Vorperiode",
  "formatPrevPeriodLabel custom N=60 de → generic fallback",
);
assertEq(
  formatPrevPeriodLabel(null, PREV_CUSTOM_GENERIC, "en", 60),
  "vs. previous period",
  "formatPrevPeriodLabel custom N=60 en → generic fallback",
);

// ────────────────────────────────────────────────────────────────
// Task 2: formatPrevYearLabel
// ────────────────────────────────────────────────────────────────
const PREV_YEAR_APR = new Date("2025-04-01T12:00:00");
const PREV_YEAR_JAN = new Date("2025-01-01T12:00:00");

assertEq(
  formatPrevYearLabel(PREV_YEAR_APR, "de"),
  "vs. Apr. 2025",
  "formatPrevYearLabel Apr de",
);
assertEq(
  formatPrevYearLabel(PREV_YEAR_APR, "en"),
  "vs. Apr 2025",
  "formatPrevYearLabel Apr en",
);
assertEq(
  formatPrevYearLabel(PREV_YEAR_JAN, "de"),
  "vs. Jan. 2025",
  "formatPrevYearLabel Jan de",
);
assertEq(
  formatPrevYearLabel(null, "de"),
  "—",
  "formatPrevYearLabel null de",
);
assertEq(
  formatPrevYearLabel(null, "en"),
  "—",
  "formatPrevYearLabel null en",
);

console.log("09-01 Task 2 assertions passed");

// ────────────────────────────────────────────────────────────────
// Task 3: getPresetRange — to-date (MTD/QTD/YTD) semantics
// ────────────────────────────────────────────────────────────────
const TODAY3 = new Date("2026-04-11T12:00:00");

function rangeToApi(
  r: { from?: Date; to?: Date },
): { from?: string; to?: string } {
  return { from: toApiDate(r.from), to: toApiDate(r.to) };
}

assertEq(
  rangeToApi(getPresetRange("thisMonth", TODAY3)),
  { from: "2026-04-01", to: "2026-04-11" },
  "getPresetRange thisMonth @ 2026-04-11 (MTD)",
);
assertEq(
  rangeToApi(getPresetRange("thisQuarter", TODAY3)),
  { from: "2026-04-01", to: "2026-04-11" },
  "getPresetRange thisQuarter @ 2026-04-11 (Q2 QTD)",
);
assertEq(
  rangeToApi(getPresetRange("thisYear", TODAY3)),
  { from: "2026-01-01", to: "2026-04-11" },
  "getPresetRange thisYear @ 2026-04-11 (YTD)",
);
assertEq(
  rangeToApi(getPresetRange("allTime", TODAY3)),
  { from: undefined, to: undefined },
  "getPresetRange allTime → both undefined",
);

console.log("09-01 Task 3 assertions passed. ALL GREEN.");
