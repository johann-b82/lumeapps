import { describe, expect, it } from "vitest";
import type { WorldCupMatch } from "@/lib/api";
import { detectGoals } from "./goalDetection";

function m(id: number, h: number | null, a: number | null): WorldCupMatch {
  return {
    id,
    home: { name: "Heim", short_name: "HEI", crest: null },
    away: { name: "Gast", short_name: "GAS", crest: null },
    score_home: h,
    score_away: a,
    status: "IN_PLAY",
    minute: 10,
    kickoff_utc: "2026-06-11T19:00:00Z",
  };
}

function asMap(...matches: WorldCupMatch[]): Map<number, WorldCupMatch> {
  return new Map(matches.map((x) => [x.id, x]));
}

describe("detectGoals", () => {
  it("returns no events on the first poll (prev null)", () => {
    expect(detectGoals(null, [m(1, 3, 1)])).toEqual([]);
  });

  it("detects a home goal", () => {
    const events = detectGoals(asMap(m(1, 0, 0)), [m(1, 1, 0)]);
    expect(events).toHaveLength(1);
    expect(events[0].team.name).toBe("Heim");
    expect(events[0].scoreHome).toBe(1);
    expect(events[0].scoreAway).toBe(0);
  });

  it("detects goals on both sides between polls", () => {
    const events = detectGoals(asMap(m(1, 0, 0)), [m(1, 1, 1)]);
    expect(events.map((e) => e.team.name).sort()).toEqual(["Gast", "Heim"]);
  });

  it("treats null scores as 0 (no event when null -> 0)", () => {
    expect(detectGoals(asMap(m(1, null, null)), [m(1, 0, 0)])).toEqual([]);
  });

  it("ignores downward score corrections", () => {
    expect(detectGoals(asMap(m(1, 2, 0)), [m(1, 1, 0)])).toEqual([]);
  });

  it("ignores matches not present in the previous poll", () => {
    expect(detectGoals(asMap(m(1, 0, 0)), [m(2, 1, 0)])).toEqual([]);
  });
});
