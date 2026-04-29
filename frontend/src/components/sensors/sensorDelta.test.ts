import { describe, it, expect } from "vitest";
import { computeSensorDelta } from "./sensorDelta";
import type { SensorReadingRead } from "@/lib/api";

const HOUR_MS = 3_600_000;
const BASE_MS = Date.UTC(2026, 3, 17, 12, 0, 0); // 2026-04-17T12:00:00Z

function mk(
  offsetMs: number,
  temperature: string | null,
  humidity: string | null = "50",
): SensorReadingRead {
  return {
    id: offsetMs,
    sensor_id: 1,
    recorded_at: new Date(BASE_MS + offsetMs).toISOString(),
    temperature,
    humidity,
    error_code: null,
  };
}

describe("computeSensorDelta", () => {
  it("returns null for empty readings", () => {
    expect(computeSensorDelta([], "temperature", 1)).toBeNull();
  });

  it("returns null when no reading falls within the ±0.5h tolerance window", () => {
    // Latest at t=0, only sibling at t=-5h → nothing near t=-1h.
    const readings = [mk(0, "22"), mk(-5 * HOUR_MS, "18")];
    expect(computeSensorDelta(readings, "temperature", 1)).toBeNull();
  });

  it("computes temperature delta vs 1h baseline", () => {
    const readings = [
      mk(0, "22"),
      mk(-1 * HOUR_MS, "20"),
      mk(-24 * HOUR_MS, "18"),
    ];
    const delta = computeSensorDelta(readings, "temperature", 1);
    expect(delta).not.toBeNull();
    expect(delta!).toBeCloseTo(2.0, 6);
  });

  it("computes temperature delta vs 24h baseline", () => {
    const readings = [
      mk(0, "22"),
      mk(-1 * HOUR_MS, "20"),
      mk(-24 * HOUR_MS, "18"),
    ];
    const delta = computeSensorDelta(readings, "temperature", 24);
    expect(delta).not.toBeNull();
    expect(delta!).toBeCloseTo(4.0, 6);
  });

  it("returns null when baseline reading has null for the requested metric", () => {
    const readings = [
      mk(0, "22", "50"),
      mk(-1 * HOUR_MS, null, "48"), // temp null at baseline
    ];
    expect(computeSensorDelta(readings, "temperature", 1)).toBeNull();
    // humidity pair is fine though:
    expect(computeSensorDelta(readings, "humidity", 1)).toBeCloseTo(2.0, 6);
  });

  it("picks the closest reading to (latest - offset) within the ±0.5h tolerance", () => {
    // Readings at t=0, t=-0.75h (outside ±0.5h of -1h? |−0.75 − (−1)|=0.25h → inside),
    // and t=-1.1h (|−1.1 − (−1)|=0.1h → closer). Expect baseline = t=-1.1h.
    const readings = [
      mk(0, "25"),
      mk(-0.75 * HOUR_MS, "22"),
      mk(-1.1 * HOUR_MS, "20"),
    ];
    const delta = computeSensorDelta(readings, "temperature", 1);
    expect(delta).not.toBeNull();
    expect(delta!).toBeCloseTo(5.0, 6); // 25 − 20
  });

  it("returns null when latest metric value is null", () => {
    const readings = [mk(0, null), mk(-1 * HOUR_MS, "20")];
    expect(computeSensorDelta(readings, "temperature", 1)).toBeNull();
  });
});
