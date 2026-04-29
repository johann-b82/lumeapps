/**
 * DeltaBadgeStack — two stacked DeltaBadge rows with muted
 * contextual secondary labels.
 *
 * Implements CARD-01 (dual badges on every card) + CARD-05
 * (contextual secondary labels) per 09-CONTEXT.md section E.
 *
 * Pure presentational. No hooks, no i18n, no data. KpiCardGrid
 * (09-03) is responsible for:
 *   1. Calling computeDelta() against the Phase 8 summary response.
 *   2. Calling formatPrevPeriodLabel / formatPrevYearLabel from
 *      lib/periodLabels to produce the secondary label strings.
 *   3. Passing the translated noBaselineTooltip string through.
 *
 * Edge case: when a secondary label is itself "—" (for thisYear
 * prev-period or allTime), we render it in the muted span without
 * any special deduplication. A muted — next to a muted — is an
 * acceptable "no comparison period" signal for Phase 9; simpler is
 * better and Phase 10 can refine if the visual warrants it.
 */
import { DeltaBadge } from "./DeltaBadge";
import type { DeltaLocale } from "./deltaFormat";

export interface DeltaBadgeStackProps {
  prevPeriodDelta: number | null;
  prevYearDelta: number | null;
  prevPeriodLabel: string;
  // null = hide the bottom badge row entirely (used by thisYear preset,
  // which collapses to a single top-row YTD-vs-YTD badge).
  prevYearLabel: string | null;
  locale: DeltaLocale;
  noBaselineTooltip: string;
}

export function DeltaBadgeStack({
  prevPeriodDelta,
  prevYearDelta,
  prevPeriodLabel,
  prevYearLabel,
  locale,
  noBaselineTooltip,
}: DeltaBadgeStackProps) {
  return (
    <div className="flex flex-col gap-1 text-sm">
      <div className="flex items-baseline gap-2">
        <DeltaBadge
          value={prevPeriodDelta}
          locale={locale}
          noBaselineTooltip={noBaselineTooltip}
        />
        <span className="text-xs text-muted-foreground">{prevPeriodLabel}</span>
      </div>
      {prevYearLabel !== null && (
        <div className="flex items-baseline gap-2">
          <DeltaBadge
            value={prevYearDelta}
            locale={locale}
            noBaselineTooltip={noBaselineTooltip}
          />
          <span className="text-xs text-muted-foreground">{prevYearLabel}</span>
        </div>
      )}
    </div>
  );
}
