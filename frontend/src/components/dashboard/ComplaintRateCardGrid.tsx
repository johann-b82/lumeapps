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

  const formatQty = (n: number) =>
    new Intl.NumberFormat(locale, {
      maximumFractionDigits: 0,
    }).format(n);

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

  // Rate-card delta logic
  const rawPrevPeriod =
    data?.rate != null ? computeDelta(data.rate, data.previous_period) : null;
  const rawPrevYear =
    data?.rate != null ? computeDelta(data.rate, data.previous_year) : null;
  const prevPeriodDelta =
    preset === "thisYear" ? rawPrevYear : rawPrevPeriod;
  const prevYearDelta = preset === "thisYear" ? null : rawPrevYear;

  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <KpiCard
        label={
          complaintType === "internal"
            ? t("quality.complaintRate.labelInternal")
            : t("quality.complaintRate.label")
        }
        subtitle={
          qtyMode === "accepted"
            ? t("quality.complaintRate.subtitleAccepted")
            : t("quality.complaintRate.subtitleTotal")
        }
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
