import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { KpiCard } from "@/components/dashboard/KpiCard";
import { DeltaBadgeStack } from "@/components/dashboard/DeltaBadgeStack";
import type { DateRangeValue } from "@/components/dashboard/DateRangeFilter";
import { useOrdersDistribution } from "@/hooks/useOrdersDistribution";
import { computePrevBounds } from "@/lib/prevBounds";
import { computeDelta } from "@/lib/delta";
import { formatPrevPeriodDeltaLabels } from "@/lib/periodLabels";
import type { Preset } from "@/lib/dateUtils";

interface Props {
  startDate?: string;
  endDate?: string;
  preset?: Preset | null;
  range?: DateRangeValue;
}

export function OrdersDistributionCard({
  startDate,
  endDate,
  preset,
  range,
}: Props) {
  const { t, i18n } = useTranslation();
  const q = useOrdersDistribution(startDate ?? "", endDate ?? "");
  const shortLocale: "de" | "en" = i18n.language === "de" ? "de" : "en";

  const prevBounds = useMemo(
    () => (preset != null && range ? computePrevBounds(preset, range) : null),
    [preset, range?.from, range?.to],
  );
  const prevYearQ = useOrdersDistribution(
    prevBounds?.prev_year_start ?? "",
    prevBounds?.prev_year_end ?? "",
  );
  const prevPeriodQ = useOrdersDistribution(
    prevBounds?.prev_period_start ?? "",
    prevBounds?.prev_period_end ?? "",
  );

  const deltaLabels =
    preset != null && range
      ? formatPrevPeriodDeltaLabels(preset, range, shortLocale, t)
      : null;
  const prevPeriodLabel = deltaLabels?.prevPeriod ?? null;
  const prevYearLabel = deltaLabels?.prevYear ?? null;
  const noBaselineTooltip = t("dashboard.delta.noBaselineTooltip");

  const current = q.data?.orders_per_week_per_rep;
  const rawDelta =
    current === undefined
      ? { prevPeriodDelta: null, prevYearDelta: null }
      : {
          prevPeriodDelta: computeDelta(
            current,
            prevPeriodQ.data?.orders_per_week_per_rep ?? null,
          ),
          prevYearDelta: computeDelta(
            current,
            prevYearQ.data?.orders_per_week_per_rep ?? null,
          ),
        };
  // Match KpiCardGrid's thisYear collapse: single badge "vs. <prior year>".
  const perRepDelta =
    preset === "thisYear"
      ? { prevPeriodDelta: rawDelta.prevYearDelta, prevYearDelta: null }
      : rawDelta;
  const showBadges = prevPeriodLabel !== null;

  const data = q.data;
  const isLoading = q.isLoading;

  return (
    <KpiCard
      label={t("sales.orders_distribution.per_rep")}
      isLoading={isLoading}
      value={
        data ? data.orders_per_week_per_rep.toFixed(1).replace(".", ",") : undefined
      }
      delta={
        data && showBadges ? (
          <DeltaBadgeStack
            prevPeriodDelta={perRepDelta.prevPeriodDelta}
            prevYearDelta={perRepDelta.prevYearDelta}
            prevPeriodLabel={prevPeriodLabel!}
            prevYearLabel={prevYearLabel}
            locale={shortLocale}
            noBaselineTooltip={noBaselineTooltip}
          />
        ) : undefined
      }
    />
  );
}
