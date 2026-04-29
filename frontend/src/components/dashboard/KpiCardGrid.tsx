/**
 * KpiCardGrid — dashboard KPI summary with dual-baseline delta badges.
 *
 * Phase 24 — delta labels unified under the shared kpi.delta.* i18n
 * namespace; allTime / custom-range presets hide the delta badge row
 * entirely (per D-12 — no em-dash, no placeholder).
 */
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { KpiCard } from "./KpiCard";
import { DeltaBadgeStack } from "./DeltaBadgeStack";
import type { DateRangeValue } from "./DateRangeFilter";
import {
  fetchKpiSummary,
  type KpiSummaryComparison,
} from "@/lib/api";
import { kpiKeys } from "@/lib/queryKeys";
import { computePrevBounds } from "@/lib/prevBounds";
import { computeDelta } from "@/lib/delta";
import { formatPrevPeriodDeltaLabels } from "@/lib/periodLabels";
import type { Preset } from "@/lib/dateUtils";

interface KpiCardGridProps {
  startDate?: string;
  endDate?: string;
  preset: Preset | null;
  range: DateRangeValue;
}

export function KpiCardGrid({
  startDate,
  endDate,
  preset,
  range,
}: KpiCardGridProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const shortLocale: "de" | "en" = i18n.language === "de" ? "de" : "en";

  const prevBounds = useMemo(
    () => computePrevBounds(preset, range),
    [preset, range.from, range.to],
  );

  const { data, isLoading, isError } = useQuery({
    queryKey: kpiKeys.summary(startDate, endDate, prevBounds),
    queryFn: () => fetchKpiSummary(startDate, endDate, prevBounds),
  });

  const formatCurrency = (n: number) =>
    new Intl.NumberFormat(locale, {
      style: "currency",
      currency: "EUR",
    }).format(n);
  const formatCount = (n: number) =>
    new Intl.NumberFormat(locale).format(n);

  // Phase 24 follow-up: concrete prior-period labels (e.g. "vs. Februar 2026"
  // / "vs. Q1 2026" / "vs. 2025") instead of generic "vs. prev. month".
  // Returns null for allTime / custom range — caller hides the badges.
  const deltaLabels = formatPrevPeriodDeltaLabels(preset, range, shortLocale, t);
  const prevPeriodLabel = deltaLabels?.prevPeriod ?? null;
  const prevYearLabel = deltaLabels?.prevYear ?? null;

  const noBaselineTooltip = t("dashboard.delta.noBaselineTooltip");

  const kpiDeltas = (
    key: keyof KpiSummaryComparison,
    current: number | undefined,
  ): { prevPeriodDelta: number | null; prevYearDelta: number | null } => {
    if (current === undefined) {
      return { prevPeriodDelta: null, prevYearDelta: null };
    }
    const pp = data?.previous_period?.[key] ?? null;
    const py = data?.previous_year?.[key] ?? null;
    return {
      prevPeriodDelta: computeDelta(current, pp),
      prevYearDelta: computeDelta(current, py),
    };
  };

  if (isError) {
    return (
      <div className="rounded-md border border-destructive bg-destructive/10 p-6">
        <p className="text-sm font-semibold">{t("dashboard.error.heading")}</p>
        <p className="text-sm text-muted-foreground">
          {t("dashboard.error.body")}
        </p>
      </div>
    );
  }

  const rawRevenueDeltas = kpiDeltas(
    "total_revenue",
    data ? Number(data.total_revenue) : undefined,
  );
  const rawAovDeltas = kpiDeltas(
    "avg_order_value",
    data ? Number(data.avg_order_value) : undefined,
  );
  const rawOrdersDeltas = kpiDeltas(
    "total_orders",
    data ? Number(data.total_orders) : undefined,
  );

  // thisYear collapses to a single top-row badge showing the YTD-vs-YTD delta
  // labeled "vs. <prior year>". Remap prevYearDelta into the top slot for
  // that preset only; all other presets keep the original dual-baseline
  // semantics. prevYearLabel is null for thisYear (DeltaBadgeStack hides the
  // bottom row), so the unused bottom value is inert.
  const remap = (d: { prevPeriodDelta: number | null; prevYearDelta: number | null }) =>
    preset === "thisYear"
      ? { prevPeriodDelta: d.prevYearDelta, prevYearDelta: null }
      : d;

  const revenueDeltas = remap(rawRevenueDeltas);
  const aovDeltas = remap(rawAovDeltas);
  const ordersDeltas = remap(rawOrdersDeltas);

  // Gate is prevPeriodLabel only — prevYearLabel is intentionally null for
  // thisYear (collapsed single-row). deltaLabels itself is null for
  // allTime / null preset, which already sets both locals to null.
  const showBadges = prevPeriodLabel !== null;

  return (
    <div>
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        <KpiCard
          label={t("dashboard.kpi.totalRevenue.label")}
          value={data ? formatCurrency(Number(data.total_revenue)) : undefined}
          isLoading={isLoading}
          delta={
            data && showBadges ? (
              <DeltaBadgeStack
                prevPeriodDelta={revenueDeltas.prevPeriodDelta}
                prevYearDelta={revenueDeltas.prevYearDelta}
                prevPeriodLabel={prevPeriodLabel!}
                prevYearLabel={prevYearLabel}
                locale={shortLocale}
                noBaselineTooltip={noBaselineTooltip}
              />
            ) : undefined
          }
        />
        <KpiCard
          label={t("dashboard.kpi.averageOrderValue.label")}
          value={
            data ? formatCurrency(Number(data.avg_order_value)) : undefined
          }
          isLoading={isLoading}
          delta={
            data && showBadges ? (
              <DeltaBadgeStack
                prevPeriodDelta={aovDeltas.prevPeriodDelta}
                prevYearDelta={aovDeltas.prevYearDelta}
                prevPeriodLabel={prevPeriodLabel!}
                prevYearLabel={prevYearLabel}
                locale={shortLocale}
                noBaselineTooltip={noBaselineTooltip}
              />
            ) : undefined
          }
        />
        <KpiCard
          label={t("dashboard.kpi.totalOrders.label")}
          value={data ? formatCount(Number(data.total_orders)) : undefined}
          isLoading={isLoading}
          delta={
            data && showBadges ? (
              <DeltaBadgeStack
                prevPeriodDelta={ordersDeltas.prevPeriodDelta}
                prevYearDelta={ordersDeltas.prevYearDelta}
                prevPeriodLabel={prevPeriodLabel!}
                prevYearLabel={prevYearLabel}
                locale={shortLocale}
                noBaselineTooltip={noBaselineTooltip}
              />
            ) : undefined
          }
        />
      </div>
      <p className="text-xs text-muted-foreground mt-2">
        {t("dashboard.kpi.exclusionNote")}
      </p>
    </div>
  );
}
