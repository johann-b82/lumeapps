/**
 * Shared pagination for the /embed/birthdays + /embed/joiners signage views.
 *
 * Reads `?duration=<seconds>` off `window.location` (the player appends it
 * from the playlist item's `duration_s`) and divides it across the page count
 * needed to display every entry at `pageSize` tiles per page. Defaults to 30 s
 * when no duration is present so a hand-typed URL still rotates sensibly.
 *
 * Enforces a 2 s minimum per page so a stack with 14 entries and a 10 s slot
 * doesn't blink unreadably fast — the iframe will overshoot the playlist
 * item's window in that case and the player will advance off it mid-cycle.
 */
import { useEffect, useState } from "react";

const DEFAULT_TOTAL_S = 30;
const MIN_PAGE_MS = 2_000;

export function useEmbedPaging(totalEntries: number, pageSize: number) {
  const [page, setPage] = useState(0);

  const totalSeconds = (() => {
    if (typeof window === "undefined") return DEFAULT_TOTAL_S;
    const raw = new URLSearchParams(window.location.search).get("duration");
    const parsed = raw != null ? parseInt(raw, 10) : NaN;
    return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_TOTAL_S;
  })();

  const pages = Math.max(1, Math.ceil(totalEntries / pageSize));
  const perPageMs = Math.max(MIN_PAGE_MS, Math.floor((totalSeconds * 1000) / pages));

  // Reset to page 0 when the underlying dataset changes shape (e.g. a new
  // birthday rolls in across midnight) so we don't index past the new length.
  useEffect(() => {
    setPage((p) => (p >= pages ? 0 : p));
  }, [pages]);

  useEffect(() => {
    if (pages <= 1) return;
    const id = window.setInterval(() => setPage((p) => (p + 1) % pages), perPageMs);
    return () => window.clearInterval(id);
  }, [pages, perPageMs]);

  return { page, pages, perPageMs, pageSize };
}
