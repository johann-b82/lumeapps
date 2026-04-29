/**
 * Pure locale-aware delta formatter.
 *
 * Implements CARD-02 (arrow glyph), CARD-03 (Intl locale percent
 * format) and CARD-04 (em-dash fallback) textual contract for
 * DeltaBadge.tsx. Factored out of the .tsx file so Node's
 * --experimental-strip-types loader can import and unit-test the
 * pure formatting logic without needing a JSX-capable runner.
 *
 * See frontend/scripts/verify-phase-09-02.mts for the assertion list.
 * See .planning/phases/09-frontend-kpi-card-dual-deltas/09-CONTEXT.md
 * section E for the display contract.
 */

export type DeltaLocale = "de" | "en";

const LOCALE_TAG: Record<DeltaLocale, string> = {
  de: "de-DE",
  en: "en-US",
};

/**
 * Format the visible text content of a DeltaBadge for a given numeric
 * delta and locale. Returns an em-dash when `value` is null.
 *
 * - value > 0 → `▲ +12.4%` (EN) / `▲ +12,4 %` (DE, NBSP before %)
 * - value < 0 → `▼ −8.1%`  (EN) / `▼ −8,1 %` (DE, U+2212 minus)
 * - value === 0 → `0.0%` / `0,0 %` (no arrow, no sign)
 * - value === null → `—` (em-dash, U+2014)
 *
 * Sign handling: we compute the Intl number via `signDisplay: 'never'`
 * on `Math.abs(value)` and then prepend a manual `+` or `−` (U+2212)
 * AFTER the arrow. This guarantees `▲ +X%` / `▼ −X%` layout regardless
 * of how Intl would otherwise render the native sign for a given locale.
 */
export function formatDeltaText(
  value: number | null,
  locale: DeltaLocale,
): string {
  if (value === null) return "—";

  const pct = new Intl.NumberFormat(LOCALE_TAG[locale], {
    style: "percent",
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
    signDisplay: "never",
  }).format(Math.abs(value));

  if (value > 0) return `▲ +${pct}`;
  if (value < 0) return `▼ −${pct}`; // U+2212 proper minus
  return pct; // zero: no arrow, no sign
}

/**
 * Tailwind class list for a DeltaBadge based on its numeric state.
 * The theme has no dedicated "success" token — positive deltas use
 * `text-primary` as the accepted v1.2 call per 09-CONTEXT section E.
 */
export function deltaClassName(value: number | null): string {
  if (value === null) return "text-muted-foreground tabular-nums";
  if (value > 0) return "text-primary tabular-nums";
  if (value < 0) return "text-destructive tabular-nums";
  return "text-muted-foreground tabular-nums"; // zero
}
