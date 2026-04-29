/**
 * DeltaBadge — single-row presentational delta indicator.
 *
 * Implements CARD-02 (arrow + semantic color), CARD-03 (locale percent
 * format), CARD-04 (em-dash + tooltip fallback) per 09-CONTEXT.md
 * section E.
 *
 * Purely prop-driven: no hooks, no i18n, no data fetching. The
 * caller (KpiCardGrid in 09-03) passes an already-computed numeric
 * delta (or null) plus a pre-translated `noBaselineTooltip` string.
 *
 * Tooltip: uses the native HTML `title` attribute rather than a
 * shadcn Tooltip primitive — none is installed in this project and
 * "no new dependencies" takes precedence. Native `title` is announced
 * by screen readers and matches the LanguageToggle pattern already
 * in use. Phase 10+ can upgrade to a visual tooltip if needed.
 */
import {
  deltaClassName,
  formatDeltaText,
  type DeltaLocale,
} from "./deltaFormat";

export interface DeltaBadgeProps {
  /** Result of computeDelta(); null = no baseline available. */
  value: number | null;
  locale: DeltaLocale;
  /** Pre-translated tooltip string shown on hover for null deltas. */
  noBaselineTooltip: string;
}

export function DeltaBadge({ value, locale, noBaselineTooltip }: DeltaBadgeProps) {
  const className = deltaClassName(value);
  const text = formatDeltaText(value, locale);
  if (value === null) {
    return (
      <span className={className} title={noBaselineTooltip}>
        {text}
      </span>
    );
  }
  return <span className={className}>{text}</span>;
}
