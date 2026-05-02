import { useTranslation } from "react-i18next";

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
  const { t } = useTranslation();
  const q = useOrdersDistribution(startDate ?? "", endDate ?? "");

  const data = q.data;
  const isLoading = q.isLoading;

  // No outer Card / border per v1.43 — the three KpiCard tiles read as
  // a peer of KpiCardGrid above them on the dashboard.
  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
      <KpiCard
        label={t("sales.orders_distribution.per_rep")}
        subtitle={t("dashboard.kpi.exclusionNote")}
        isLoading={isLoading}
        value={
          data ? data.orders_per_week_per_rep.toFixed(1).replace(".", ",") : undefined
        }
      />
      <KpiCard
        label={t("sales.orders_distribution.top3")}
        subtitle={
          data?.top3_customers.length
            ? data.top3_customers.join(", ")
            : t("sales.orders_distribution.top3_empty")
        }
        isLoading={isLoading}
        value={data ? formatPct(data.top3_share_pct) : undefined}
      />
      <KpiCard
        label={t("sales.orders_distribution.remaining")}
        subtitle={t("sales.orders_distribution.remaining_subtitle")}
        isLoading={isLoading}
        value={data ? formatPct(data.remaining_share_pct) : undefined}
      />
    </div>
  );
}
