import { parse, formatHex, converter, wcagContrast as _wcagContrast } from "culori";

const toOklch = converter("oklch");

/**
 * Convert a hex color string (e.g. "#4466cc") to a canonical oklch string
 * in the exact format the backend validator accepts: `oklch(L C H)` — three
 * numbers, space-separated, no alpha slash.
 * Throws on unparseable input so callers fail loudly at save time rather
 * than silently PUT an invalid color.
 */
export function hexToOklch(hex: string): string {
  const color = parse(hex);
  if (!color) throw new Error(`Invalid hex color: ${hex}`);
  const oklch = toOklch(color);
  if (!oklch) throw new Error(`Could not convert to oklch: ${hex}`);
  const L = Math.min(1, Math.max(0, oklch.l ?? 0));
  const C = Math.max(0, oklch.c ?? 0);
  const H = Number.isFinite(oklch.h) ? (oklch.h as number) : 0;
  return `oklch(${L.toFixed(4)} ${C.toFixed(4)} ${H.toFixed(2)})`;
}

/**
 * Convert an oklch string (as stored server-side, e.g. "oklch(0.55 0.15 250)")
 * to a 6-digit hex string (e.g. "#4466cc") for display in a HexColorPicker.
 * Returns "#000000" on parse failure — a visible-but-safe fallback.
 */
export function oklchToHex(oklch: string): string {
  const color = parse(oklch);
  if (!color) return "#000000";
  const hex = formatHex(color);
  return hex ?? "#000000";
}

/**
 * WCAG contrast ratio between two CSS color strings in ANY color space
 * culori can parse (hex, rgb, oklch, named). Returns 0 on parse failure.
 * Used by the contrast-badge logic (BRAND-08) with a 4.5:1 threshold.
 */
export function wcagContrast(colorA: string, colorB: string): number {
  const a = parse(colorA);
  const b = parse(colorB);
  if (!a || !b) return 0;
  return _wcagContrast(a, b);
}

/**
 * The literal "white" value the BRAND-08 destructive/white pair compares
 * against, in oklch form. Matches the CSS default in index.css. Exported
 * so components don't hardcode the string.
 */
export const WHITE_OKLCH = "oklch(1 0 0)";
