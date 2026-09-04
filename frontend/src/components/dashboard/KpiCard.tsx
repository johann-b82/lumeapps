import { type ReactNode } from "react";
import { Card } from "@/components/ui/card";
import { KpiInfoButton } from "./KpiInfoButton";
import type { KpiInfoKey } from "@/lib/kpiInfo";

interface KpiCardProps {
  label: string;
  subtitle?: string;
  value?: string;
  isLoading: boolean;
  delta?: ReactNode;
  /** When set, renders an "i" button next to the label that opens the
   *  calculation notes for this KPI (see `lib/kpiInfo.ts`). */
  infoKey?: KpiInfoKey;
}

export function KpiCard({ label, subtitle, value, isLoading, delta, infoKey }: KpiCardProps) {
  if (isLoading) {
    return (
      <Card className="p-6">
        <div className="h-4 w-24 bg-muted rounded animate-pulse mb-4" />
        <div className="h-9 w-36 bg-muted rounded animate-pulse" />
      </Card>
    );
  }
  return (
    <Card className="p-6">
      <div className="flex items-start justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        {infoKey && (
          <KpiInfoButton infoKey={infoKey} label={label} className="-mt-1.5 -mr-1.5" />
        )}
      </div>
      <div className="mt-2 flex items-center justify-between gap-4">
        <p className="text-3xl font-semibold tabular-nums">{value ?? "—"}</p>
        {delta != null && (
          <div className="flex-shrink-0 text-right">{delta}</div>
        )}
      </div>
      {subtitle && (
        <p className="mt-2 text-xs text-muted-foreground/70">{subtitle}</p>
      )}
    </Card>
  );
}
