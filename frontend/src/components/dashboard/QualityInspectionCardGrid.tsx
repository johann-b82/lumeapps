/**
 * QualityInspectionCardGrid — Anzahl geprüfter Produkte (Große / Kleine).
 *
 * Mirrors the QualityKpiCardGrid layout (2-card grid + delta badges).
 * Backend returns 0/0 until the aggregation logic is defined; the UI
 * still renders — cards show "0" instead of the em-dash so the widget
 * is visibly present and testable end-to-end.
 */
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { KpiCard } from "./KpiCard";
import { DeltaBadgeStack } from "./DeltaBadgeStack";
import { computeDelta } from "@/lib/delta";
import { fetchInspections } from "@/lib/api";
import { qualityKeys } from "@/lib/queryKeys";
import { formatPrevPeriodDeltaLabels } from "@/lib/periodLabels";
import { useDateRange } from "@/contexts/DateRangeContext";
import { toApiDate } from "@/lib/dateUtils";

export function QualityInspectionCardGrid() {
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
    queryKey: qualityKeys.inspections(date_from, date_to),
    queryFn: () => fetchInspections({ date_from, date_to }),
  });

  const formatCount = (n: number) => new Intl.NumberFormat(locale).format(n);

  function renderCard(
    label: string,
    value: number | undefined,
    prevPeriod: number | null | undefined,
    prevYear: number | null | undefined,
  ) {
    if (isLoading) {
      return <KpiCard label={label} isLoading={true} />;
    }
    if (value === undefined) {
      return <KpiCard label={label} value={undefined} isLoading={false} />;
    }

    const rawPrevPeriod = computeDelta(value, prevPeriod ?? null);
    const rawPrevYear = computeDelta(value, prevYear ?? null);
    const prevPeriodDelta =
      preset === "thisYear" ? rawPrevYear : rawPrevPeriod;
    const prevYearDelta = preset === "thisYear" ? null : rawPrevYear;

    return (
      <KpiCard
        label={label}
        subtitle={t("quality.inspection.unit")}
        value={formatCount(value)}
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

  return (
    <div>
      {isError && (
        <div className="rounded-md border border-destructive bg-destructive/10 p-6 mb-6">
          <p className="text-sm font-semibold">
            {t("quality.kpi.error.heading")}
          </p>
          <p className="text-sm text-muted-foreground">
            {t("quality.kpi.error.body")}
          </p>
        </div>
      )}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        {renderCard(
          t("quality.inspection.large.label"),
          data?.large_count,
          data?.previous_period_large ?? null,
          data?.previous_year_large ?? null,
        )}
        {renderCard(
          t("quality.inspection.small.label"),
          data?.small_count,
          data?.previous_period_small ?? null,
          data?.previous_year_small ?? null,
        )}
      </div>
    </div>
  );
}
