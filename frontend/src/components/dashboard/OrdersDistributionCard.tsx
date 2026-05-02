import { useTranslation } from "react-i18next";

import { Card } from "@/components/ui/card";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { primaryPalette } from "@/lib/chartDefaults";
import { useOrdersDistribution } from "@/hooks/useOrdersDistribution";

interface Props {
  startDate?: string;
  endDate?: string;
}

function formatPct(n: number): string {
  return `${n.toFixed(1).replace(".", ",")} %`;
}

export function OrdersDistributionCard({ startDate, endDate }: Props) {
  const { t } = useTranslation();
  const q = useOrdersDistribution(startDate ?? "", endDate ?? "");

  const data = q.data;
  const isLoading = q.isLoading;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* Left tile: orders / week / rep */}
      <KpiCard
        label={t("sales.orders_distribution.per_rep")}
        subtitle={t("dashboard.kpi.exclusionNote")}
        isLoading={isLoading}
        value={
          data ? data.orders_per_week_per_rep.toFixed(1).replace(".", ",") : undefined
        }
      />

      {/* Right widget: stacked share bar + numbered top-3 list. Spans the
          remaining two columns on md+ so it has room to breathe. */}
      <Card className="p-6 md:col-span-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {t("sales.orders_distribution.share_title")}
        </p>

        {isLoading ? (
          <div className="mt-4 h-9 w-full bg-muted rounded animate-pulse" />
        ) : (
          <div className="mt-4 grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-6 items-center">
            <ShareBar
              top3Pct={data?.top3_share_pct ?? 0}
              remainingPct={data?.remaining_share_pct ?? 0}
              top3Label={t("sales.orders_distribution.top3")}
              remainingLabel={t("sales.orders_distribution.remaining")}
            />
            <ol className="text-sm space-y-1 list-none p-0 min-w-[200px]">
              {(data?.top3_customers ?? []).map((c, i) => (
                <li key={c} className="flex gap-2">
                  <span className="text-muted-foreground tabular-nums">
                    {i + 1}.
                  </span>
                  <span className="font-medium">{c}</span>
                </li>
              ))}
              {!data?.top3_customers.length && (
                <li className="text-muted-foreground italic">
                  {t("sales.orders_distribution.top3_empty")}
                </li>
              )}
            </ol>
          </div>
        )}
      </Card>
    </div>
  );
}

function ShareBar({
  top3Pct,
  remainingPct,
  top3Label,
  remainingLabel,
}: {
  top3Pct: number;
  remainingPct: number;
  top3Label: string;
  remainingLabel: string;
}) {
  // The two stacked segments use shades from primaryPalette so the chart
  // matches the SalesActivityCard bars above. Top-3 is the darker
  // (heavier) shade so it visually anchors the dominant slice.
  const top3Color = primaryPalette[2]; // blue-600
  const remainingColor = primaryPalette[5]; // blue-300
  const total = top3Pct + remainingPct || 1;
  const top3Width = (top3Pct / total) * 100;
  const remainingWidth = 100 - top3Width;

  return (
    <div className="flex flex-col gap-2">
      <div
        className="flex h-9 w-full rounded-md overflow-hidden ring-1 ring-border"
        role="img"
        aria-label={`${top3Label} ${top3Pct}% / ${remainingLabel} ${remainingPct}%`}
      >
        <div
          className="flex items-center justify-center text-xs font-medium text-white"
          style={{ width: `${top3Width}%`, background: top3Color }}
        >
          {top3Width >= 8 && formatPct(top3Pct)}
        </div>
        <div
          className="flex items-center justify-center text-xs font-medium text-foreground"
          style={{ width: `${remainingWidth}%`, background: remainingColor }}
        >
          {remainingWidth >= 8 && formatPct(remainingPct)}
        </div>
      </div>
      <div className="flex gap-4 text-xs text-muted-foreground">
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 w-2.5 rounded-sm"
            style={{ background: top3Color }}
          />
          {top3Label}
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 w-2.5 rounded-sm"
            style={{ background: remainingColor }}
          />
          {remainingLabel}
        </span>
      </div>
    </div>
  );
}
