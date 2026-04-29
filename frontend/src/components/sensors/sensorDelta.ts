import type { SensorReadingRead } from "@/lib/api";

/**
 * DIFF-01 — Client-side sensor delta computation.
 *
 * Sales / HR compute deltas server-side because they're aggregated KPIs.
 * Sensors are raw time-series that are already sitting in the TanStack
 * Query cache, so computing here is both simpler (no new endpoint) and
 * faster (no round-trip). See 39-02 PLAN D-11.
 *
 * Algorithm:
 *   1. Sort readings descending by `recorded_at`.
 *   2. Pick latest reading; return null if its metric value is null.
 *   3. Target baseline = latest.recorded_at − offsetHours.
 *   4. Among earlier readings within ±0.5h of the target, pick the CLOSEST.
 *   5. Return latestValue − baselineValue, or null if no baseline in window.
 */
export type SensorMetric = "temperature" | "humidity";

const TOLERANCE_MS = 0.5 * 3_600_000; // ±30 minutes

export function computeSensorDelta(
  readings: SensorReadingRead[],
  metric: SensorMetric,
  offsetHours: number,
): number | null {
  if (readings.length === 0) return null;

  const sorted = [...readings].sort(
    (a, b) =>
      new Date(b.recorded_at).getTime() - new Date(a.recorded_at).getTime(),
  );

  const latest = sorted[0];
  const latestRaw = latest[metric];
  if (latestRaw === null) return null;
  const latestVal = Number(latestRaw);
  if (!Number.isFinite(latestVal)) return null;

  const latestMs = new Date(latest.recorded_at).getTime();
  const targetMs = latestMs - offsetHours * 3_600_000;

  const baseline = sorted
    .slice(1)
    .map((r) => ({
      r,
      diff: Math.abs(new Date(r.recorded_at).getTime() - targetMs),
    }))
    .filter((x) => x.diff <= TOLERANCE_MS)
    .sort((a, b) => a.diff - b.diff)[0]?.r;

  if (!baseline) return null;
  const baselineRaw = baseline[metric];
  if (baselineRaw === null) return null;
  const baselineVal = Number(baselineRaw);
  if (!Number.isFinite(baselineVal)) return null;

  return latestVal - baselineVal;
}
