/**
 * OtdCardGrid — KPI cards for the Liefertermintreue / OTD section.
 *
 * - OTD-Quote (%) with delta badges vs. Vorperiode / Vorjahr. Higher is
 *   better, so a positive delta renders in the primary (good) colour — the
 *   raw delta is passed straight through (DeltaBadge already maps + → primary).
 * - Pünktliche Positionen (numerator) and Gesamt-Positionen (denominator).
 * - Ø Verzug (Tage) — mean delay across the window's positions.
 */
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { KpiCard } from "./KpiCard";
import { DeltaBadgeStack } from "./DeltaBadgeStack";
import { computeDelta } from "@/lib/delta";
import { fetchOtd } from "@/lib/api";
import { procurementKeys } from "@/lib/queryKeys";
import { formatPrevPeriodDeltaLabels } from "@/lib/periodLabels";
import { useDateRange } from "@/contexts/DateRangeContext";
import { toApiDate } from "@/lib/dateUtils";

export function OtdCardGrid() {
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
    queryKey: procurementKeys.otd(date_from, date_to),
    queryFn: () => fetchOtd({ date_from, date_to }),
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
        <p className="text-sm font-semibold">{t("procurement.kpi.error.heading")}</p>
        <p className="text-sm text-muted-foreground">
          {t("procurement.kpi.error.body")}
        </p>
      </div>
    );
  }

  const rawPrevPeriod =
    data?.rate != null ? computeDelta(data.rate, data.previous_period) : null;
  const rawPrevYear =
    data?.rate != null ? computeDelta(data.rate, data.previous_year) : null;
  const prevPeriodDelta = preset === "thisYear" ? rawPrevYear : rawPrevPeriod;
  const prevYearDelta = preset === "thisYear" ? null : rawPrevYear;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
      <KpiCard
        label={t("procurement.otd.label")}
        infoKey="procurement.otd"
        subtitle={t("procurement.otd.subtitle")}
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
        label={t("procurement.punctualCount.label")}
        infoKey="procurement.punctual_count"
        value={isLoading ? undefined : formatCount(data?.punctual_count ?? 0)}
        isLoading={isLoading}
      />
      <KpiCard
        label={t("procurement.totalCount.label")}
        infoKey="procurement.total_count"
        value={isLoading ? undefined : formatCount(data?.total_count ?? 0)}
        isLoading={isLoading}
      />
      <KpiCard
        label={t("procurement.avgDelay.label")}
        infoKey="procurement.avg_delay"
        subtitle={t("procurement.avgDelay.subtitle")}
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
