/**
 * HrKpiCardGrid -- HR KPI card grid with 5 cards in 3+2 layout.
 *
 * Fetches HR KPIs from GET /api/hr/kpis, renders each with dual delta
 * badges (vs. Vormonat + vs. Vorjahr), handles no-sync / error /
 * unconfigured states per UI-SPEC D-07, D-08, D-09.
 */
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Link } from "wouter";
import { KpiCard } from "./KpiCard";
import { DeltaBadgeStack } from "./DeltaBadgeStack";
import { computeDelta } from "@/lib/delta";
import { fetchHrKpis, type HrKpiValue } from "@/lib/api";
import { hrKpiKeys } from "@/lib/queryKeys";
import { formatPrevPeriodDeltaLabels } from "@/lib/periodLabels";
import { useDateRange } from "@/contexts/DateRangeContext";
import { toApiDate } from "@/lib/dateUtils";

export function HrKpiCardGrid() {
  const { t, i18n } = useTranslation();
  const shortLocale: "de" | "en" = i18n.language === "de" ? "de" : "en";
  const locale = i18n.language === "de" ? "de-DE" : "en-US";

  // Phase 60: HR shares DateRangeContext with Sales. Delta badge labels now
  // mirror Sales — preset-driven (thisMonth → "vs. <prior month>", thisQuarter
  // → "vs. Q<prior>", thisYear → collapsed single "vs. <prior year>", allTime
  // → badges hidden).
  const { preset, range } = useDateRange();
  const date_from = toApiDate(range.from);
  const date_to = toApiDate(range.to);

  const deltaLabels = formatPrevPeriodDeltaLabels(preset, range, shortLocale, t);
  const prevPeriodLabel = deltaLabels?.prevPeriod ?? null;
  const prevYearLabel = deltaLabels?.prevYear ?? null;
  const showBadges = prevPeriodLabel !== null;

  const { data, isLoading, isError } = useQuery({
    queryKey: hrKpiKeys.summary(date_from, date_to),
    queryFn: () => fetchHrKpis({ date_from, date_to }),
  });

  const formatPercent = (n: number) =>
    new Intl.NumberFormat(locale, {
      style: "percent",
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }).format(n);

  const formatCurrency = (n: number) =>
    new Intl.NumberFormat(locale, {
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 0,
    }).format(n);

  const noSyncYet =
    data &&
    [
      data.overtime_ratio,
      data.sick_leave_ratio,
      data.fluctuation,
      data.skill_development,
      data.revenue_per_production_employee,
    ].every((k) => k.value === null && k.is_configured);

  function renderCard(
    kpi: HrKpiValue | undefined,
    label: string,
    formatter: (n: number) => string,
    subtitle?: string,
  ) {
    if (isLoading) {
      return <KpiCard label={label} subtitle={subtitle} isLoading={true} />;
    }

    if (kpi === undefined) {
      return <KpiCard label={label} subtitle={subtitle} value={undefined} isLoading={false} />;
    }

    if (!kpi.is_configured) {
      return (
        <KpiCard
          label={label}
          subtitle={subtitle}
          value={"—"}
          isLoading={false}
          delta={
            <p className="text-xs text-muted-foreground">
              {t("hr.kpi.notConfigured")}{" "}
              <Link href="/settings" className="underline">
                {t("hr.kpi.openSettings")}
              </Link>
            </p>
          }
        />
      );
    }

    const rawPrevPeriod =
      kpi.value !== null ? computeDelta(kpi.value, kpi.previous_period) : null;
    const rawPrevYear =
      kpi.value !== null ? computeDelta(kpi.value, kpi.previous_year) : null;

    // thisYear collapses to a single top-row badge showing YTD-vs-YTD, mapping
    // previous_year into the top slot (matches Sales remap in KpiCardGrid).
    const prevPeriodDelta =
      preset === "thisYear" ? rawPrevYear : rawPrevPeriod;
    const prevYearDelta = preset === "thisYear" ? null : rawPrevYear;

    return (
      <KpiCard
        label={label}
        subtitle={subtitle}
        value={kpi.value !== null ? formatter(kpi.value) : "\u2014"}
        isLoading={false}
        delta={
          showBadges ? (
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
    );
  }

  // When error, render cards with undefined kpi values (em-dash, no deltas)
  const kpiData = isError ? undefined : data;

  return (
    <div>
      {/* Error banner (D-09) */}
      {isError && (
        <div className="rounded-md border border-destructive bg-destructive/10 p-6 mb-6">
          <p className="text-sm font-semibold">
            {t("hr.kpi.error.heading")}
          </p>
          <p className="text-sm text-muted-foreground">
            {t("hr.kpi.error.body")}
          </p>
        </div>
      )}

      {/* No-sync banner (D-07) */}
      {noSyncYet && (
        <div className="rounded-md border border-border bg-muted/40 p-4 mb-6">
          <p className="text-sm font-semibold">
            {t("hr.kpi.noSync.heading")}
          </p>
          <p className="text-sm text-muted-foreground">
            {t("hr.kpi.noSync.body")}
          </p>
        </div>
      )}

      {/* Top row: 3 cards */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {renderCard(
          kpiData?.overtime_ratio,
          t("hr.kpi.overtimeRatio.label"),
          formatPercent,
        )}
        {renderCard(
          kpiData?.sick_leave_ratio,
          t("hr.kpi.sickLeaveRatio.label"),
          formatPercent,
        )}
        {renderCard(
          kpiData?.fluctuation,
          t("hr.kpi.fluctuation.label"),
          formatPercent,
        )}
      </div>

      {/* Bottom row: 2 cards left-aligned */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 mt-8">
        {renderCard(
          kpiData?.skill_development,
          t("hr.kpi.skillDevelopment.label"),
          formatPercent,
        )}
        {renderCard(
          kpiData?.revenue_per_production_employee,
          t("hr.kpi.revenuePerProductionEmployee.label"),
          formatCurrency,
        )}
      </div>
    </div>
  );
}
