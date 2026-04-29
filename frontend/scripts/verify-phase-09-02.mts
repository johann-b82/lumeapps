/**
 * Throwaway runtime verification harness for Phase 9 Plan 2.
 *
 * Asserts presentational behavior of DeltaBadge without pulling in
 * a test framework (no vitest/jest). Follows the 09-01 pattern:
 * `node --experimental-strip-types frontend/scripts/verify-phase-09-02.mts`
 *
 * DeltaBadge.tsx is a React component so we cannot import it under
 * `--experimental-strip-types` (JSX not supported by the strip-types
 * loader). Instead we factor the pure locale/sign/percent formatting
 * logic into `deltaFormat.ts` and assert its outputs here.
 *
 * Exit 0 = all green. Any failure throws.
 */
import { formatDeltaText } from "../src/components/dashboard/deltaFormat.ts";

const NBSP = "\u00A0";

type Case = {
  name: string;
  value: number | null;
  locale: "de" | "en";
  expected: string;
};

const cases: Case[] = [
  // positive — EN (regular ASCII)
  { name: "EN positive 0.124", value: 0.124, locale: "en", expected: "▲ +12.4%" },
  // positive — DE: Intl emits NBSP (U+00A0) between number and %
  { name: "DE positive 0.124", value: 0.124, locale: "de", expected: `▲ +12,4${NBSP}%` },
  // negative — EN, U+2212 proper minus
  { name: "EN negative -0.081", value: -0.081, locale: "en", expected: "▼ −8.1%" },
  // negative — DE
  { name: "DE negative -0.081", value: -0.081, locale: "de", expected: `▼ −8,1${NBSP}%` },
  // zero — EN: no arrow, no sign
  { name: "EN zero", value: 0, locale: "en", expected: "0.0%" },
  // zero — DE: no arrow, no sign
  { name: "DE zero", value: 0, locale: "de", expected: `0,0${NBSP}%` },
  // null — em-dash, both locales
  { name: "EN null", value: null, locale: "en", expected: "—" },
  { name: "DE null", value: null, locale: "de", expected: "—" },
];

let failed = 0;
for (const c of cases) {
  const actual = formatDeltaText(c.value, c.locale);
  if (actual !== c.expected) {
    console.error(
      `FAIL ${c.name}: expected ${JSON.stringify(c.expected)}, got ${JSON.stringify(actual)}`,
    );
    failed++;
  } else {
    console.log(`PASS ${c.name}: ${JSON.stringify(actual)}`);
  }
}

if (failed > 0) {
  console.error(`\n09-02 verify: ${failed} failing case(s)`);
  process.exit(1);
}
console.log("\n09-02 Task 1 assertions passed");
console.log("ALL GREEN");
