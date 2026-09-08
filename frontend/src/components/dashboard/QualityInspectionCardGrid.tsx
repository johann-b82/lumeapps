/**
 * QualityInspectionCardGrid — Teile pro Person und Tag (Große / Kleine / Gesamt).
 *
 * Three-card grid: headline = per_person_day, subtitle = per_day (Teile/Tag
 * gesamt). Delta badges on the per_person_day headline.
 */
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { KpiCard } from "./KpiCard";
import type { KpiInfoKey } from "@/lib/kpiInfo";
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

  const nf1 = new Intl.NumberFormat(locale, { maximumFractionDigits: 1 });

  function renderCard(
    label: string,
    value: number | undefined,
    perDay: number | undefined,
    prevPeriod: number | null | undefined,
    prevYear: number | null | undefined,
    infoKey: KpiInfoKey,
  ) {
    if (isLoading) {
      return <KpiCard label={label} isLoading={true} />;
    }
    if (value === undefined) {
      return <KpiCard label={label} value={undefined} isLoading={false} infoKey={infoKey} />;
    }

    const rawPrevPeriod = computeDelta(value, prevPeriod ?? null);
    const rawPrevYear = computeDelta(value, prevYear ?? null);
    const prevPeriodDelta =
      preset === "thisYear" ? rawPrevYear : rawPrevPeriod;
    const prevYearDelta = preset === "thisYear" ? null : rawPrevYear;

    const subtitle =
      perDay !== undefined
        ? t("quality.inspection.card.perDay", { value: nf1.format(perDay) })
        : t("quality.inspection.unit");

    return (
      <KpiCard
        label={label}
        infoKey={infoKey}
        subtitle={subtitle}
        value={nf1.format(value)}
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
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {renderCard(
          t("quality.inspection.large.label"),
          data?.large_per_person_day,
          data?.large_per_day,
          data?.previous_period_large_per_person_day ?? null,
          data?.previous_year_large_per_person_day ?? null,
          "quality.inspection_large",
        )}
        {renderCard(
          t("quality.inspection.small.label"),
          data?.small_per_person_day,
          data?.small_per_day,
          data?.previous_period_small_per_person_day ?? null,
          data?.previous_year_small_per_person_day ?? null,
          "quality.inspection_small",
        )}
        {renderCard(
          t("quality.inspection.total.label"),
          data?.total_per_person_day,
          data?.total_per_day,
          data?.previous_period_total_per_person_day ?? null,
          data?.previous_year_total_per_person_day ?? null,
          "quality.inspection_total",
        )}
      </div>
    </div>
  );
}
