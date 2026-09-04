/**
 * ProductionVerzugCardGrid — KPI cards for "Aufträge in Verzug (Seriengeschäft)".
 *
 * - Verzugsquote (%) = orders in Verzug / total, with delta badges vs.
 *   Vorperiode / Vorjahr. LOWER is better, so — like the complaint rate — the
 *   deltas are computed in Termintreue-complement space (1 − rate) so that a
 *   reduction in delays reads as a positive (green) delta.
 * - Aufträge in Verzug (numerator) and Aufträge gesamt (denominator).
 * - Ø Verzug (Tage) — mean signed delay across the window's orders.
 */
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { KpiCard } from "./KpiCard";
import { DeltaBadgeStack } from "./DeltaBadgeStack";
import { computeDelta } from "@/lib/delta";
import { fetchProductionVerzug } from "@/lib/api";
import { productionKeys } from "@/lib/queryKeys";
import { formatPrevPeriodDeltaLabels } from "@/lib/periodLabels";
import { useDateRange } from "@/contexts/DateRangeContext";
import { toApiDate } from "@/lib/dateUtils";

export function ProductionVerzugCardGrid() {
  const { t, i18n } = useTranslation();
  const shortLocale: "de" | "en" = i18n.language === "de" ? "de" : "en";
  const locale = i18n.language === "de" ? "de-DE" : "en-US";

  const { preset, range } = useDateRange();
  const date_from = toApiDate(range.from);
  const date_to = toApiDate(range.to);

  const deltaLabels = formatPrevPeriodDeltaLabels(preset, range, shortLocale, t);
  const prevPeriodLabel = deltaLabels?.prevPeriod ?? null;
  const prevYearLabel = deltaLabels?.prevYear ?? null;
  const showBadges = prevPeriodLabel !== null;

  const { data, isLoading, isError } = useQuery({
    queryKey: productionKeys.verzug(date_from, date_to),
    queryFn: () => fetchProductionVerzug({ date_from, date_to }),
  });

  const formatPercent = (n: number) =>
    new Intl.NumberFormat(locale, {
      style: "percent",
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }).format(n);

  const formatCount = (n: number) =>
    new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(n);

  const formatDays = (n: number) =>
    new Intl.NumberFormat(locale, {
      maximumFractionDigits: 1,
      signDisplay: "exceptZero",
    }).format(n);

  if (isError) {
    return (
      <div className="rounded-md border border-destructive bg-destructive/10 p-6">
        <p className="text-sm font-semibold">{t("production.kpi.error.heading")}</p>
        <p className="text-sm text-muted-foreground">
          {t("production.kpi.error.body")}
        </p>
      </div>
    );
  }

  // Deltas in Termintreue-complement space (1 − Verzugsquote) so a drop in
  // delays reads as a positive (good) delta — same convention as complaint rate.
  const onTime = data?.rate != null ? 1 - data.rate : null;
  const onTimePrevPeriod =
    data?.previous_period != null ? 1 - data.previous_period : null;
  const onTimePrevYear =
    data?.previous_year != null ? 1 - data.previous_year : null;

  const rawPrevPeriod =
    onTime != null ? computeDelta(onTime, onTimePrevPeriod) : null;
  const rawPrevYear = onTime != null ? computeDelta(onTime, onTimePrevYear) : null;
  const prevPeriodDelta = preset === "thisYear" ? rawPrevYear : rawPrevPeriod;
  const prevYearDelta = preset === "thisYear" ? null : rawPrevYear;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
      <KpiCard
        label={t("production.verzug.label")}
        infoKey="production.verzug"
        subtitle={t("production.verzug.subtitle")}
        value={
          isLoading
            ? undefined
            : data?.rate != null
            ? formatPercent(data.rate)
            : "—"
        }
        isLoading={isLoading}
        delta={
          showBadges && data?.rate != null ? (
            <DeltaBadgeStack
              prevPeriodDelta={prevPeriodDelta}
              prevYearDelta={prevYearDelta}
              prevPeriodLabel={prevPeriodLabel!}
              prevYearLabel={prevYearLabel}
              locale={shortLocale}
              noBaselineTooltip={t("hr.kpi.noBaselineTooltip")}
            />
          ) : undefined
        }
      />
      <KpiCard
        label={t("production.inVerzugCount.label")}
        infoKey="production.in_verzug_count"
        value={isLoading ? undefined : formatCount(data?.in_verzug_count ?? 0)}
        isLoading={isLoading}
      />
      <KpiCard
        label={t("production.totalCount.label")}
        infoKey="production.total_count"
        value={isLoading ? undefined : formatCount(data?.total_count ?? 0)}
        isLoading={isLoading}
      />
      <KpiCard
        label={t("production.avgDelay.label")}
        infoKey="production.avg_delay"
        subtitle={t("production.avgDelay.subtitle")}
        value={
          isLoading
            ? undefined
            : data?.avg_delay != null
            ? formatDays(data.avg_delay)
            : "—"
        }
        isLoading={isLoading}
      />
    </div>
  );
}
