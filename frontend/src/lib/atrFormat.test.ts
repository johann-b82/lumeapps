import { describe, it, expect } from "vitest";
import { formatPoPos } from "./atrApi";

describe("formatPoPos", () => {
  it("pads pure numbers to 3 digits with leading zeros", () => {
    expect(formatPoPos("5")).toBe("005");
    expect(formatPoPos("50")).toBe("050");
    expect(formatPoPos("500")).toBe("500");
    expect(formatPoPos(" 50 ")).toBe("050");
  });

  it("leaves empty / null / undefined as empty string", () => {
    expect(formatPoPos("")).toBe("");
    expect(formatPoPos(null)).toBe("");
    expect(formatPoPos(undefined)).toBe("");
  });

  it("leaves non-numeric or >3-digit values unchanged", () => {
    expect(formatPoPos("A12")).toBe("A12");
    expect(formatPoPos("1234")).toBe("1234");
    expect(formatPoPos("12/3")).toBe("12/3");
  });
});
