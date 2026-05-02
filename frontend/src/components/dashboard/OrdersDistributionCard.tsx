import { useTranslation } from "react-i18next";

import { Card } from "@/components/ui/card";
import { KpiCard } from "@/components/dashboard/KpiCard";
import { useOrdersDistribution } from "@/hooks/useOrdersDistribution";

interface Props {
  startDate?: string;
  endDate?: string;
}

function formatPct(n: number): string {
  return `${n.toFixed(1).replace(".", ",")} %`;
}

export function OrdersDistributionCard({ startDate, endDate }: Props) {
  const { t, i18n } = useTranslation();
  const q = useOrdersDistribution(startDate ?? "", endDate ?? "");
  const locale = i18n.language || "de-DE";

  const formatCurrency = (n: number) =>
    new Intl.NumberFormat(locale, {
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 0,
    }).format(n);

  const data = q.data;
  const isLoading = q.isLoading;

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      {/* Col 1: orders / week / rep */}
      <KpiCard
        label={t("sales.orders_distribution.per_rep")}
        isLoading={isLoading}
        value={
          data ? data.orders_per_week_per_rep.toFixed(1).replace(".", ",") : undefined
        }
      />

      {/* Col 2: stacked share bar */}
      <Card className="p-6">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {t("sales.orders_distribution.share_title")}
        </p>
        {isLoading ? (
          <div className="mt-4 h-9 w-full bg-muted animate-pulse" />
        ) : (
          <ShareBar
            top3Pct={data?.top3_share_pct ?? 0}
            remainingPct={data?.remaining_share_pct ?? 0}
            top3Label={t("sales.orders_distribution.top3")}
            remainingLabel={t("sales.orders_distribution.remaining")}
          />
        )}
      </Card>

      {/* Col 3: numbered TOP-3 customers with order value */}
      <Card className="p-6">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          {t("sales.orders_distribution.top3_customers_title")}
        </p>
        {isLoading ? (
          <div className="mt-4 h-16 bg-muted animate-pulse" />
        ) : (
          <ol className="mt-4 text-sm space-y-1 list-none p-0">
            {(data?.top3_customers ?? []).map((c, i) => (
              <li
                key={c.name}
                className="flex items-baseline gap-2 text-muted-foreground"
              >
                <span className="tabular-nums">{i + 1}.</span>
                <span className="flex-1 truncate">{c.name}</span>
                <span className="tabular-nums whitespace-nowrap">
                  {formatCurrency(c.total_value)}
                </span>
              </li>
            ))}
            {!data?.top3_customers.length && (
              <li className="text-muted-foreground italic">
                {t("sales.orders_distribution.top3_empty")}
              </li>
            )}
          </ol>
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
  const top3Color = "var(--primary)";
  // v1.46: align with --color-chart-prior = var(--muted) so the share-bar
  // "Remaining customers" segment matches the previous-period bar on the
  // Order-value-over-time chart (both gedämpft surface gray).
  const remainingColor = "var(--muted)";
  const total = top3Pct + remainingPct || 1;
  const top3Width = (top3Pct / total) * 100;
  const remainingWidth = 100 - top3Width;

  return (
    <div className="mt-4 flex flex-col gap-2">
      <div
        className="flex h-9 w-full"
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
            className="inline-block h-2.5 w-2.5"
            style={{ background: top3Color }}
          />
          {top3Label}
        </span>
        <span className="flex items-center gap-1.5">
          <span
            className="inline-block h-2.5 w-2.5"
            style={{ background: remainingColor }}
          />
          {remainingLabel}
        </span>
      </div>
    </div>
  );
}
