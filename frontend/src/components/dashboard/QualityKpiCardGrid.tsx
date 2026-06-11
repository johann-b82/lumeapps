/**
 * QualityKpiCardGrid — Audit-Findings Level 1 / Level 2 KPI cards.
 *
 * Mirrors HrKpiCardGrid behavior (delta badges driven by the active
 * date-range preset). Reads the audit-type filter from props so the
 * page can hoist filter state above this and the history chart.
 */
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { KpiCard } from "./KpiCard";
import { DeltaBadgeStack } from "./DeltaBadgeStack";
import { computeDelta } from "@/lib/delta";
import {
  fetchAuditFindings,
  type AuditTypeCode,
} from "@/lib/api";
import { qualityKeys } from "@/lib/queryKeys";
import { formatPrevPeriodDeltaLabels } from "@/lib/periodLabels";
import { useDateRange } from "@/contexts/DateRangeContext";
import { toApiDate } from "@/lib/dateUtils";

interface QualityKpiCardGridProps {
  auditTypes: readonly AuditTypeCode[];
}

export function QualityKpiCardGrid({ auditTypes }: QualityKpiCardGridProps) {
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
    queryKey: qualityKeys.auditFindings(date_from, date_to, auditTypes),
    queryFn: () =>
      fetchAuditFindings({ date_from, date_to, audit_types: auditTypes }),
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

    // thisYear preset → collapse to a single top-row badge (YTD vs YTD),
    // matching the HR / Sales conventions.
    const prevPeriodDelta =
      preset === "thisYear" ? rawPrevYear : rawPrevPeriod;
    const prevYearDelta = preset === "thisYear" ? null : rawPrevYear;

    return (
      <KpiCard
        label={label}
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
          t("quality.kpi.auditFindingsLevel1.label"),
          data?.level_1,
          data?.previous_period_level_1 ?? null,
          data?.previous_year_level_1 ?? null,
        )}
        {renderCard(
          t("quality.kpi.auditFindingsLevel2.label"),
          data?.level_2,
          data?.previous_period_level_2 ?? null,
          data?.previous_year_level_2 ?? null,
        )}
      </div>
    </div>
  );
}
