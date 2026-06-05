/**
 * Shared pagination for the /embed/birthdays + /embed/joiners signage views.
 *
 * `?duration=<seconds>` (the player appends it from the playlist item's
 * `duration_s`) is the time PER PAGE — total visible time = pages × duration.
 * Defaults to 10 s when no duration is on the URL so a hand-typed embed
 * still rotates sensibly. Hard floor of 2 s per page so the operator can't
 * accidentally make the deck blink unreadably fast.
 *
 * After the last page has been shown for its `perPageMs`, posts
 * `{ type: "embed-cycle-complete" }` to the parent window so the signage
 * player can advance to the next playlist item. The player listens for this
 * in IframePlayer; if the embed is being viewed standalone (no parent
 * listening) the message is harmlessly delivered to `window` itself.
 */
import { useEffect, useState } from "react";

const DEFAULT_PER_PAGE_S = 10;
const MIN_PAGE_MS = 2_000;

export function useEmbedPaging(totalEntries: number, pageSize: number) {
  const [page, setPage] = useState(0);

  const perPageSeconds = (() => {
    if (typeof window === "undefined") return DEFAULT_PER_PAGE_S;
    const raw = new URLSearchParams(window.location.search).get("duration");
    const parsed = raw != null ? parseInt(raw, 10) : NaN;
    return Number.isFinite(parsed) && parsed > 0 ? parsed : DEFAULT_PER_PAGE_S;
  })();

  const pages = Math.max(1, Math.ceil(totalEntries / pageSize));
  const perPageMs = Math.max(MIN_PAGE_MS, perPageSeconds * 1000);

  // Reset to page 0 when the underlying dataset changes shape (e.g. a new
  // birthday rolls in across midnight) so we don't index past the new length.
  useEffect(() => {
    setPage((p) => (p >= pages ? 0 : p));
  }, [pages]);

  useEffect(() => {
    let step = 0;
    setPage(0);
    const id = window.setInterval(() => {
      step += 1;
      if (step >= pages) {
        // The last page has been shown for perPageMs — signal the player so
        // it can move on. `window.parent` falls back to `window` when the
        // page isn't iframed, which posts to nothing in particular and is
        // a no-op.
        try {
          window.parent.postMessage({ type: "embed-cycle-complete" }, "*");
        } catch {
          /* posting cross-origin can throw on some browsers — swallow */
        }
        window.clearInterval(id);
      } else {
        setPage(step);
      }
    }, perPageMs);
    return () => window.clearInterval(id);
  }, [pages, perPageMs]);

  return { page, pages, perPageMs, pageSize };
}
