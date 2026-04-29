import { AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { wcagContrast } from "@/lib/color";

export interface ContrastBadgeProps {
  /** First color — any CSS color string culori can parse. */
  colorA: string;
  /** Second color — any CSS color string culori can parse. */
  colorB: string;
}

/**
 * Renders a destructive-variant Badge when the WCAG 2.1 contrast ratio
 * between colorA and colorB falls below 4.5:1. Returns null otherwise —
 * BRAND-08 is warn-only, never blocks Save.
 *
 * Copy: "Contrast {ratio} : 1 — needs 4.5 : 1" with ratio formatted to
 * one decimal place, per 06-UI-SPEC line 204.
 */
export function ContrastBadge({ colorA, colorB }: ContrastBadgeProps) {
  const ratio = wcagContrast(colorA, colorB);
  if (ratio >= 4.5) return null;
  return (
    <Badge variant="destructive" className="gap-1 mt-1 w-fit">
      <AlertTriangle className="h-3 w-3" aria-hidden="true" />
      <span>Contrast {ratio.toFixed(1)} : 1 — needs 4.5 : 1</span>
    </Badge>
  );
}
