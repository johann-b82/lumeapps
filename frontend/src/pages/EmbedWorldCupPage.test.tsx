import { describe, it, expect } from "vitest";
import { shouldPostCycle } from "./EmbedWorldCupPage";

describe("worldcup overview cycle gating", () => {
  it("defers the cycle while a goal overlay is queued", () => {
    expect(shouldPostCycle(true, 1)).toBe(false);  // timer elapsed, goal queued
    expect(shouldPostCycle(true, 0)).toBe(true);    // timer elapsed, queue empty
    expect(shouldPostCycle(false, 0)).toBe(false);  // timer not elapsed
  });
});
