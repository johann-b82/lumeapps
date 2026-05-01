import { useTranslation } from "react-i18next";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
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

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("sales.orders_distribution.title")}</CardTitle>
      </CardHeader>
      <CardContent className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <KpiCard
          label={t("sales.orders_distribution.per_rep")}
          subtitle={t("sales.orders_distribution.per_rep_subtitle")}
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
      </CardContent>
    </Card>
  );
}
