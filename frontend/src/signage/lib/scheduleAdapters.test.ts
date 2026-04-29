import { describe, it, expect } from "vitest";
import {
  hhmmFromString,
  hhmmToString,
  weekdayMaskToArray,
  weekdayMaskFromArray,
} from "./scheduleAdapters";

describe("hhmmFromString parses valid HH:MM", () => {
  it("07:30 -> 730", () => expect(hhmmFromString("07:30")).toBe(730));
  it("00:00 -> 0", () => expect(hhmmFromString("00:00")).toBe(0));
  it("23:59 -> 2359", () => expect(hhmmFromString("23:59")).toBe(2359));
  it("09:00 -> 900", () => expect(hhmmFromString("09:00")).toBe(900));
});

describe("hhmmFromString rejects out-of-range hour/minute", () => {
  it("25:00 -> null", () => expect(hhmmFromString("25:00")).toBeNull());
  it("12:60 -> null", () => expect(hhmmFromString("12:60")).toBeNull());
  it("24:00 -> null", () => expect(hhmmFromString("24:00")).toBeNull());
});

describe("hhmmFromString rejects malformed input", () => {
  it("empty -> null", () => expect(hhmmFromString("")).toBeNull());
  it("bad -> null", () => expect(hhmmFromString("bad")).toBeNull());
  it("7:30 (single digit hour) -> null", () =>
    expect(hhmmFromString("7:30")).toBeNull());
});

describe("hhmmToString pads single digits", () => {
  it("730 -> 07:30", () => expect(hhmmToString(730)).toBe("07:30"));
  it("0 -> 00:00", () => expect(hhmmToString(0)).toBe("00:00"));
  it("900 -> 09:00", () => expect(hhmmToString(900)).toBe("09:00"));
  it("1430 -> 14:30", () => expect(hhmmToString(1430)).toBe("14:30"));
  it("2359 -> 23:59", () => expect(hhmmToString(2359)).toBe("23:59"));
});

describe("hhmmToString rejects out-of-range", () => {
  it("-1 -> empty", () => expect(hhmmToString(-1)).toBe(""));
  it("2400 -> empty", () => expect(hhmmToString(2400)).toBe(""));
});

describe("hhmmToString rejects non-integer minute overflow", () => {
  it("960 (mm=60) -> empty", () => expect(hhmmToString(960)).toBe(""));
  it("1.5 (non-int) -> empty", () => expect(hhmmToString(1.5)).toBe(""));
});

describe("weekday adapters roundtrip bit0=Mo..bit6=So", () => {
  it("mask 0b0011111 -> Mo-Fr on, Sa/So off", () => {
    expect(weekdayMaskToArray(0b0011111)).toEqual([
      true,
      true,
      true,
      true,
      true,
      false,
      false,
    ]);
  });
  it("[Mo-Fr] -> 31", () => {
    expect(
      weekdayMaskFromArray([true, true, true, true, true, false, false]),
    ).toBe(31);
  });
  it("all false -> 0", () => {
    expect(weekdayMaskFromArray([false, false, false, false, false, false, false])).toBe(
      0,
    );
  });
  it("all true -> 127", () => {
    expect(weekdayMaskFromArray([true, true, true, true, true, true, true])).toBe(
      127,
    );
  });
  it("roundtrip preserves arbitrary masks", () => {
    for (const mask of [0, 1, 42, 64, 99, 127]) {
      expect(weekdayMaskFromArray(weekdayMaskToArray(mask))).toBe(mask);
    }
  });
  it("only Sunday (bit6) -> 64", () => {
    expect(
      weekdayMaskFromArray([false, false, false, false, false, false, true]),
    ).toBe(64);
  });
});
