import { describe, it, expect } from "vitest";
import {
  buildMonthSpine,
  mergeIntoSpine,
  formatMonthYear,
  yearBoundaryDates,
  deriveHrBuckets,
  formatBucketLabel,
} from "./chartTimeUtils";

describe("buildMonthSpine", () => {
  it("returns 6 entries from Oct 2024 to Mar 2025", () => {
    const result = buildMonthSpine("2024-10-01", "2025-03-01");
    expect(result).toEqual([
      "2024-10-01",
      "2024-11-01",
      "2024-12-01",
      "2025-01-01",
      "2025-02-01",
      "2025-03-01",
    ]);
  });

  it("returns a single entry for a single month", () => {
    expect(buildMonthSpine("2025-06-01", "2025-06-01")).toEqual(["2025-06-01"]);
  });

  it("returns entries within the same year", () => {
    const result = buildMonthSpine("2025-03-01", "2025-05-01");
    expect(result).toEqual(["2025-03-01", "2025-04-01", "2025-05-01"]);
  });
});

describe("mergeIntoSpine", () => {
  it("fills missing months with revenue: null", () => {
    const spine = ["2025-01-01", "2025-02-01", "2025-03-01"];
    const points = [
      { date: "2025-01-01", revenue: 100 },
      { date: "2025-03-01", revenue: 300 },
    ];
    expect(mergeIntoSpine(spine, points)).toEqual([
      { date: "2025-01-01", revenue: 100 },
      { date: "2025-02-01", revenue: null },
      { date: "2025-03-01", revenue: 300 },
    ]);
  });

  it("returns all nulls when points array is empty", () => {
    const spine = ["2025-01-01", "2025-02-01"];
    expect(mergeIntoSpine(spine, [])).toEqual([
      { date: "2025-01-01", revenue: null },
      { date: "2025-02-01", revenue: null },
    ]);
  });

  it("returns empty array for empty spine", () => {
    expect(mergeIntoSpine([], [{ date: "2025-01-01", revenue: 100 }])).toEqual([]);
  });
});

describe("formatMonthYear", () => {
  it("formats en-US Nov 2025 as \"Nov '25\"", () => {
    expect(formatMonthYear("2025-11-01", "en-US")).toBe("Nov '25");
  });

  it("formats en-US Jan 2025 as \"Jan '25\"", () => {
    expect(formatMonthYear("2025-01-01", "en-US")).toBe("Jan '25");
  });

  it("formats de-DE Jan 2025 as \"Jan '25\"", () => {
    // German abbreviated month for January is "Jan"
    expect(formatMonthYear("2025-01-01", "de-DE")).toBe("Jan '25");
  });
});

describe("yearBoundaryDates", () => {
  it("returns only January dates from a mixed spine", () => {
    const spine = ["2024-11-01", "2024-12-01", "2025-01-01", "2025-02-01"];
    expect(yearBoundaryDates(spine)).toEqual(["2025-01-01"]);
  });

  it("returns empty array when no January in spine", () => {
    expect(yearBoundaryDates(["2025-03-01", "2025-04-01"])).toEqual([]);
  });

  it("returns multiple January dates across years", () => {
    const spine = ["2024-01-01", "2024-06-01", "2025-01-01"];
    expect(yearBoundaryDates(spine)).toEqual(["2024-01-01", "2025-01-01"]);
  });
});

describe("deriveHrBuckets — D-06 thresholds", () => {
  it("15-day range → daily, 15 buckets, labels YYYY-MM-DD", () => {
    const from = new Date("2026-04-01T00:00:00");
    const to = new Date("2026-04-15T00:00:00");
    const plan = deriveHrBuckets(from, to);
    expect(plan.granularity).toBe("daily");
    expect(plan.buckets).toHaveLength(15);
    expect(plan.buckets[0].label).toBe("2026-04-01");
    expect(plan.buckets[14].label).toBe("2026-04-15");
  });

  it("31-day range → daily (threshold edge)", () => {
    const from = new Date("2026-04-01T00:00:00");
    const to = new Date("2026-05-01T00:00:00"); // 31 days inclusive
    const plan = deriveHrBuckets(from, to);
    expect(plan.granularity).toBe("daily");
    expect(plan.buckets).toHaveLength(31);
  });

  it("60-day range → weekly, labels YYYY-Www (ISO week, zero-padded)", () => {
    const from = new Date("2026-04-01T00:00:00");
    const to = new Date("2026-05-30T00:00:00"); // 60 days
    const plan = deriveHrBuckets(from, to);
    expect(plan.granularity).toBe("weekly");
    expect(plan.buckets.length).toBeGreaterThanOrEqual(9);
    expect(plan.buckets.length).toBeLessThanOrEqual(10);
    for (const b of plan.buckets) {
      expect(b.label).toMatch(/^\d{4}-W\d{2}$/);
    }
    // First bucket clipped to from
    expect(plan.buckets[0].start.getTime()).toBe(from.getTime());
    // Last bucket clipped to to
    expect(plan.buckets[plan.buckets.length - 1].end.getTime()).toBe(to.getTime());
  });

  it("ISO week 15 of 2026 → label '2026-W15'", () => {
    // 2026-04-06 is a Monday — start of ISO week 15 of 2026
    const d = new Date("2026-04-06T00:00:00");
    expect(formatBucketLabel("weekly", d)).toBe("2026-W15");
  });

  it("1-year range (365d) → monthly, labels YYYY-MM, clipped edges", () => {
    const from = new Date("2025-06-15T00:00:00");
    const to = new Date("2026-06-14T00:00:00"); // 365 days
    const plan = deriveHrBuckets(from, to);
    expect(plan.granularity).toBe("monthly");
    expect(plan.buckets.length).toBeGreaterThanOrEqual(12);
    expect(plan.buckets.length).toBeLessThanOrEqual(13);
    for (const b of plan.buckets) {
      expect(b.label).toMatch(/^\d{4}-\d{2}$/);
    }
    expect(plan.buckets[0].start.getTime()).toBe(from.getTime());
    expect(plan.buckets[plan.buckets.length - 1].end.getTime()).toBe(to.getTime());
  });

  it("731-day range → monthly (threshold edge)", () => {
    const from = new Date("2024-01-01T00:00:00");
    const to = new Date("2025-12-31T00:00:00"); // 731 days inclusive
    const plan = deriveHrBuckets(from, to);
    expect(plan.granularity).toBe("monthly");
  });

  it("5-year range → quarterly, labels YYYY-Qn", () => {
    const from = new Date("2021-01-01T00:00:00");
    const to = new Date("2025-12-31T00:00:00");
    const plan = deriveHrBuckets(from, to);
    expect(plan.granularity).toBe("quarterly");
    for (const b of plan.buckets) {
      expect(b.label).toMatch(/^\d{4}-Q[1-4]$/);
    }
  });

  it("quarterly label for bucket starting 2024-04-01 → '2024-Q2'", () => {
    const d = new Date("2024-04-01T00:00:00");
    expect(formatBucketLabel("quarterly", d)).toBe("2024-Q2");
  });

  it("from > to → returns daily with empty buckets (no throw)", () => {
    const from = new Date("2026-05-01T00:00:00");
    const to = new Date("2026-04-01T00:00:00");
    const plan = deriveHrBuckets(from, to);
    expect(plan.granularity).toBe("daily");
    expect(plan.buckets).toEqual([]);
  });

  it("from == to (1-day range) → daily, 1 bucket", () => {
    const d = new Date("2026-04-15T00:00:00");
    const plan = deriveHrBuckets(d, d);
    expect(plan.granularity).toBe("daily");
    expect(plan.buckets).toHaveLength(1);
    expect(plan.buckets[0].label).toBe("2026-04-15");
  });

  it("daily label format", () => {
    const d = new Date("2026-04-15T00:00:00");
    expect(formatBucketLabel("daily", d)).toBe("2026-04-15");
  });

  it("monthly label format", () => {
    const d = new Date("2026-04-01T00:00:00");
    expect(formatBucketLabel("monthly", d)).toBe("2026-04");
  });
});
