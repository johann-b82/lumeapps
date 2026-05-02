// Shared Recharts token defaults per 21-UI-SPEC.md §"Recharts Contract (DM-03)".
// All values reference CSS variables so charts auto-adapt when `.dark` toggles.

export const gridProps = {
  strokeDasharray: "3 3",
  stroke: "var(--color-border)",
} as const;

export const axisProps = {
  stroke: "var(--color-border)",
  tick: { fill: "var(--color-muted-foreground)", fontSize: 12 },
  tickLine: { stroke: "var(--color-border)" },
  axisLine: { stroke: "var(--color-border)" },
} as const;

export const tooltipStyle = {
  background: "var(--color-popover)",
  color: "var(--color-popover-foreground)",
  border: "1px solid var(--color-border)",
  borderRadius: "var(--radius-md)",
} as const;

export const tooltipLabelStyle = {
  color: "var(--color-popover-foreground)",
} as const;

export const tooltipItemStyle = {
  color: "var(--color-popover-foreground)",
} as const;

export const tooltipCursorProps = {
  fill: "var(--color-accent)",
  opacity: 0.3,
} as const;

export const legendWrapperStyle = {
  color: "var(--color-muted-foreground)",
} as const;

/**
 * sensorPalette — DOCUMENTED EXCEPTION to the token-only rule (v1.9 D-05).
 *
 * Multi-series sensor charts need ≥8 visually distinct hues; the CSS custom
 * property tokens (primary/accent/muted/destructive/foreground) only supply
 * the semantic 4–5. Each sensor uses the SAME color index across the
 * temperature and humidity charts so the legend stays consistent across the
 * two stacked charts. Cycle with modulo if sensor count > palette length.
 *
 * This is the ONLY hex-literal block allowed under `frontend/src/`. Grep
 * bans check everywhere else; this file is the allow-listed escape hatch.
 */
export const sensorPalette = [
  "#3b82f6", // blue-500
  "#ef4444", // red-500
  "#10b981", // emerald-500
  "#f59e0b", // amber-500
  "#8b5cf6", // violet-500
  "#ec4899", // pink-500
  "#14b8a6", // teal-500
  "#f97316", // orange-500
] as const;

/**
 * primaryPalette — eight monochromatic shades of the dashboard's primary
 * blue. Index 0 is the actual primary token (#2563eb / blue-600); the
 * rest are variations that step out from it (lighter first, then darker)
 * so a chart with many series reads as a coherent gradient anchored on
 * the primary. Same allow-listed-hex exception as sensorPalette above.
 */
export const primaryPalette = [
  "#2563eb", // blue-600  — primary (matches --color-primary)
  "#60a5fa", // blue-400  — primary, lighter
  "#1d4ed8", // blue-700  — primary, darker
  "#93c5fd", // blue-300  — primary, very light (shared with --color-chart-prior)
  "#1e3a8a", // blue-900  — primary, very dark
  "#3b82f6", // blue-500
  "#0284c7", // sky-600
  "#0ea5e9", // sky-500
] as const;
