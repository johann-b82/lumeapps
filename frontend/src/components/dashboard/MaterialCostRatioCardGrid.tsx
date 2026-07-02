/**
 * MaterialCostRatioCardGrid — KPI cards for the Materialkostenquote section.
 *
 * - Materialkostenquote (%) = Materialkosten / Umsatz, with delta badges vs.
 *   Vorperiode / Vorjahr. Lower is better; the raw delta is passed straight
 *   through to match the OTD / Reklamationsquote convention (DeltaBadge
 *   colours by sign, not by good/bad polarity).
 * - Materialkosten (€) — the numerator (consumed qty × newest WE price).
 * - Umsatz (€) — the denominator (Σ revenues.wert_eur, RG/GS net).
 * - Ohne Preis (count) — consumed articles with no WE purchase price; they
 *   are excluded from the cost and surfaced here for transparency.
 */
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { KpiCard } from "./KpiCard";
import { DeltaBadgeStack } from "./DeltaBadgeStack";
import { computeDelta } from "@/lib/delta";
import { fetchMaterialCostRatio } from "@/lib/api";
import { financeKeys } from "@/lib/queryKeys";
import { formatPrevPeriodDeltaLabels } from "@/lib/periodLabels";
import { useDateRange } from "@/contexts/DateRangeContext";
import { toApiDate } from "@/lib/dateUtils";

export function MaterialCostRatioCardGrid() {
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
    queryKey: financeKeys.materialCostRatio(date_from, date_to),
    queryFn: () => fetchMaterialCostRatio({ date_from, date_to }),
  });

  const formatPercent = (n: number) =>
    new Intl.NumberFormat(locale, {
      style: "percent",
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    }).format(n);

  const formatEur = (n: number) =>
    new Intl.NumberFormat(locale, {
      style: "currency",
      currency: "EUR",
      maximumFractionDigits: 0,
    }).format(n);

  const formatCount = (n: number) =>
    new Intl.NumberFormat(locale, { maximumFractionDigits: 0 }).format(n);

  if (isError) {
    return (
      <div className="rounded-md border border-destructive bg-destructive/10 p-6">
        <p className="text-sm font-semibold">{t("finance.kpi.error.heading")}</p>
        <p className="text-sm text-muted-foreground">
          {t("finance.kpi.error.body")}
        </p>
      </div>
    );
  }

  const rawPrevPeriod =
    data?.ratio != null ? computeDelta(data.ratio, data.previous_period) : null;
  const rawPrevYear =
    data?.ratio != null ? computeDelta(data.ratio, data.previous_year) : null;
  const prevPeriodDelta = preset === "thisYear" ? rawPrevYear : rawPrevPeriod;
  const prevYearDelta = preset === "thisYear" ? null : rawPrevYear;

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-8">
      <KpiCard
        label={t("finance.materialCostRatio.label")}
        subtitle={t("finance.materialCostRatio.subtitle")}
        value={
          isLoading
            ? undefined
            : data?.ratio != null
            ? formatPercent(data.ratio)
            : "—"
        }
        isLoading={isLoading}
        delta={
          showBadges && data?.ratio != null ? (
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
        label={t("finance.materialCost.label")}
        value={isLoading ? undefined : formatEur(data?.material_cost ?? 0)}
        isLoading={isLoading}
      />
      <KpiCard
        label={t("finance.revenue.label")}
        value={isLoading ? undefined : formatEur(data?.revenue ?? 0)}
        isLoading={isLoading}
      />
      <KpiCard
        label={t("finance.unmatched.label")}
        subtitle={t("finance.unmatched.subtitle")}
        value={isLoading ? undefined : formatCount(data?.unmatched_articles ?? 0)}
        isLoading={isLoading}
      />
    </div>
  );
}
