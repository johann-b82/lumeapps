/**
 * Phase 9 — Dual-delta KPI cards.
 *
 * Pure delta math. Implements the null-baseline branch for CARD-04
 * (em-dash fallback when no comparison period exists) and the
 * percentage-math for CARD-05 (dual delta badges).
 *
 * Rules:
 *   - `prior === null` → `null` (no baseline available)
 *   - `prior === 0`    → `null` (divide-by-zero guard; never render ∞%)
 *   - otherwise        → `(current - prior) / prior`
 *
 * The consumer renders `null` as `—` (em-dash) with a tooltip; see
 * `DeltaBadge` in plan 09-02.
 */
export function computeDelta(
  current: number,
  prior: number | null,
): number | null {
  if (prior === null || prior === 0) return null;
  return (current - prior) / prior;
}
