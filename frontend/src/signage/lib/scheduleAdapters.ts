// Phase 52 Plan 02 — pure adapters for signage schedules.
// Bit positions: bit0 = Monday .. bit6 = Sunday.
// Time on-the-wire: integer HHMM (0..2359); display format: "HH:MM" (24h zero-padded).

export function weekdayMaskToArray(mask: number): boolean[] {
  return Array.from({ length: 7 }, (_, i) => ((mask >> i) & 1) === 1);
}

export function weekdayMaskFromArray(arr: boolean[]): number {
  return arr.reduce((m, on, i) => (on ? m | (1 << i) : m), 0);
}

/**
 * Parse a strict "HH:MM" string (24h) into an integer HHMM (0..2359).
 * Returns null on empty, malformed, or out-of-range inputs.
 */
export function hhmmFromString(s: string): number | null {
  const m = /^([0-1]\d|2[0-3]):([0-5]\d)$/.exec(s);
  if (!m) return null;
  return parseInt(m[1], 10) * 100 + parseInt(m[2], 10);
}

/**
 * Render an integer HHMM (0..2359) as zero-padded "HH:MM".
 * Returns "" for out-of-range or non-integer inputs (including mm > 59).
 */
export function hhmmToString(n: number): string {
  if (!Number.isInteger(n) || n < 0 || n > 2359) return "";
  const hh = Math.floor(n / 100);
  const mm = n % 100;
  if (mm > 59) return "";
  return `${String(hh).padStart(2, "0")}:${String(mm).padStart(2, "0")}`;
}
