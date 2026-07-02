/**
 * ComplaintRateCardGrid — three KPI cards for the Reklamationen view.
 *
 * - Reklamationsquote (%) with delta badges vs. Vorperiode / Vorjahr.
 * - Gelieferte Stück (absolute denominator) — helps spot the "high rate
 *   driven by tiny delivery volume" anti-pattern.
 * - Reklamierte Stück (absolute numerator, depends on qty-mode).
 */
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { KpiCard } from "./KpiCard";
import { DeltaBadgeStack } from "./DeltaBadgeStack";
import { computeDelta } from "@/lib/delta";
import {
  fetchComplaintRate,
  type ComplaintType,
  type QtyMode,
} from "@/lib/api";
import { qualityKeys } from "@/lib/queryKeys";
import { formatPrevPeriodDeltaLabels } from "@/lib/periodLabels";
import { useDateRange } from "@/contexts/DateRangeContext";
import { toApiDate } from "@/lib/dateUtils";

interface ComplaintRateCardGridProps {
  qtyMode: QtyMode;
  complaintType: ComplaintType;
}

export function ComplaintRateCardGrid({
  qtyMode,
  complaintType,
}: ComplaintRateCardGridProps) {
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
    queryKey: qualityKeys.complaintRate(
      date_from,
      date_to,
      qtyMode,
      complaintType,
    ),
    queryFn: () =>
      fetchComplaintRate({
        date_from,
        date_to,
        qty_mode: qtyMode,
        complaint_type: complaintType,
      }),
  });

  const formatPercent = (n: number) =>
    new Intl.NumberFormat(locale, {
      style: "percent",
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(n);

  // On Quality % uses one more decimal than the defect rate — a 0.319 %
  // defect renders 99,681 % which compresses to "99,68 %" at 2 decimals
  // and loses interesting digits. 3 decimals keeps the spec-rounding.
  const formatOnQualityPercent = (n: number) =>
    new Intl.NumberFormat(locale, {
      style: "percent",
      minimumFractionDigits: 3,
      maximumFractionDigits: 3,
    }).format(n);

  const formatQty = (n: number) =>
    new Intl.NumberFormat(locale, {
      maximumFractionDigits: 0,
    }).format(n);

  // Defect rate → On Quality. NULL stays NULL (no deliveries → no quote).
  const toOnQuality = (rate: number | null): number | null =>
    rate == null ? null : 1 - rate;

  if (isError) {
    return (
      <div className="rounded-md border border-destructive bg-destructive/10 p-6">
        <p className="text-sm font-semibold">
          {t("quality.kpi.error.heading")}
        </p>
        <p className="text-sm text-muted-foreground">
          {t("quality.kpi.error.body")}
        </p>
      </div>
    );
  }

  // Card shows On Quality (= 1 − defect rate) as the headline. Deltas
  // are computed in the On-Quality space so "+0,1 %" reads as "quality
  // improved by 0.1 percentage points" — same sign convention as Sales.
  const onQuality = toOnQuality(data?.rate ?? null);
  const onQualityPrevPeriod = toOnQuality(data?.previous_period ?? null);
  const onQualityPrevYear = toOnQuality(data?.previous_year ?? null);

  const rawPrevPeriod =
    onQuality != null ? computeDelta(onQuality, onQualityPrevPeriod) : null;
  const rawPrevYear =
    onQuality != null ? computeDelta(onQuality, onQualityPrevYear) : null;
  const prevPeriodDelta =
    preset === "thisYear" ? rawPrevYear : rawPrevPeriod;
  const prevYearDelta = preset === "thisYear" ? null : rawPrevYear;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <KpiCard
        label={t(`quality.onQuality.labelByType.${complaintType}`)}
        subtitle={
          data?.rate != null
            ? t("quality.onQuality.subtitleFehler", {
                rate: formatPercent(data.rate),
              })
            : undefined
        }
        value={
          isLoading
            ? undefined
            : onQuality != null
            ? formatOnQualityPercent(onQuality)
            : "—"
        }
        isLoading={isLoading}
        delta={
          showBadges && onQuality != null ? (
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
        label={t("quality.deliveredQty.label")}
        value={isLoading ? undefined : formatQty(data?.delivered_qty ?? 0)}
        isLoading={isLoading}
      />
      <KpiCard
        label={
          qtyMode === "accepted"
            ? t("quality.acceptedComplaintQty.label")
            : t("quality.complaintQty.label")
        }
        value={isLoading ? undefined : formatQty(data?.complaint_qty ?? 0)}
        isLoading={isLoading}
      />
    </div>
  );
}
