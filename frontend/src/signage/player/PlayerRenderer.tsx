import { Suspense, lazy, useCallback, useEffect, useRef, useState } from "react";
import type { PlayerItem } from "./types";
import { ImagePlayer } from "./ImagePlayer";
import { VideoPlayer } from "./VideoPlayer";
import { IframePlayer } from "./IframePlayer";
import { HtmlPlayer } from "./HtmlPlayer";
import { PptxPlayer } from "./PptxPlayer";

// SGN-POL-05 (Phase 50): lazy-loaded so react-pdf + pdfjs-dist glue ship in
// a separate chunk, fetched only when a playlist item with kind='pdf' actually renders.
// Named-export adapter per 50-RESEARCH.md Pitfall 1.
const PdfPlayer = lazy(() => import("./PdfPlayer").then((m) => ({ default: m.PdfPlayer })));

export interface PlayerRendererProps {
  items: PlayerItem[];
  className?: string;
  /** Phase 62 D-05 / CAL-PI-06: forwarded to VideoPlayer as `muted={!audioEnabled}`.
   *  Default `false` preserves the Phase 47 autoplay-muted behaviour until the
   *  admin UI enables audio for this device. */
  audioEnabled?: boolean;
}

function renderItem(
  item: PlayerItem,
  audioEnabled: boolean,
  onCycleEnd: (() => void) | undefined,
) {
  switch (item.kind) {
    case "image":
      return <ImagePlayer uri={item.uri} />;
    case "video":
      return <VideoPlayer uri={item.uri} muted={!audioEnabled} />;
    case "pdf":
      return (
        <Suspense fallback={<div className="w-full h-full bg-black" />}>
          <PdfPlayer
            uri={item.uri}
            autoFlipSeconds={item.duration_s}
            onCycleEnd={onCycleEnd}
          />
        </Suspense>
      );
    case "url":
      return <IframePlayer uri={item.uri} />;
    case "html":
      return <HtmlPlayer html={item.html} />;
    case "pptx":
      return (
        <PptxPlayer
          slidePaths={item.slide_paths}
          durationS={item.duration_s}
          onCycleEnd={onCycleEnd}
        />
      );
    default:
      return null;
  }
}

// Item kinds whose inner player owns its own lifetime via `onCycleEnd`.
// For these, PlayerRenderer skips the outer `duration_s`-seconds setTimeout —
// `duration_s` is interpreted per slide / page, so the total visible time is
// driven by the slide / page count, not by a single outer countdown.
function ownsOwnLifetime(kind: PlayerItem["kind"]): boolean {
  return kind === "pptx" || kind === "pdf";
}

/**
 * Admin-preview PlayerRenderer (SGN-DIFF-02 / D-09, D-10).
 *
 * Accepts in-memory items (form state or server state) and auto-advances
 * through them. duration_s semantics depend on item.kind:
 *  - image / video / url / html: per-item — the outer timer fires once per
 *    duration_s seconds and moves on.
 *  - pptx: per-slide. Inner PptxPlayer flips every duration_s; after the last
 *    slide, calls onCycleEnd and the renderer advances. Total visible time
 *    for a PPTX item = duration_s * slide_paths.length.
 *  - pdf: per-page. Inner PdfPlayer flips every duration_s; after the last
 *    page, calls onCycleEnd. Total visible time depends on numPages, which
 *    is only known once <Document> loads.
 *
 * Single-item playlists let the inner player loop internally (onCycleEnd
 * stays unset) so the deck / PDF replays in place.
 *
 * Resets currentIndex to 0 when the items prop reference changes
 * (playlist save, item add/remove).
 *
 * No SSE, no heartbeat, no offline cache — those are Phase 47 wrappers.
 *
 * Transition handling:
 *  - "fade" (default): 300ms CSS opacity transition between swaps
 *  - "cut": immediate swap (no transition)
 */
export function PlayerRenderer({ items, className, audioEnabled = false }: PlayerRendererProps) {
  const [currentIndex, setCurrentIndex] = useState(0);
  const [fading, setFading] = useState(false);
  // Guards inner-player onCycleEnd callbacks from double-firing (e.g. React
  // strict-mode duplicate effect runs in dev) — only the first call per
  // currentIndex actually advances.
  const advancedRef = useRef(false);

  // Reset on items reference change — mitigates stale-index after add/remove.
  useEffect(() => {
    setCurrentIndex(0);
  }, [items]);

  // Re-arm the advance guard whenever we move to a new item.
  useEffect(() => {
    advancedRef.current = false;
  }, [currentIndex]);

  const advance = useCallback(() => {
    if (advancedRef.current) return;
    advancedRef.current = true;
    if (items.length <= 1) return; // single-item playlist: inner loops itself
    const next = items[(currentIndex + 1) % items.length];
    const useFade = next?.transition !== "cut";
    if (useFade) {
      setFading(true);
      setTimeout(() => {
        setCurrentIndex((i) => (i + 1) % items.length);
        setFading(false);
      }, 300);
    } else {
      setCurrentIndex((i) => (i + 1) % items.length);
    }
  }, [items, currentIndex]);

  useEffect(() => {
    if (items.length === 0) return;
    const item = items[currentIndex] ?? items[0];
    // PPTX / PDF items advance via the inner player's onCycleEnd — their
    // duration_s is per-slide / per-page, not per-item. Skip the outer timer.
    if (ownsOwnLifetime(item.kind)) return;
    const durationMs = Math.max(1000, item.duration_s * 1000);
    const advanceTimer = window.setTimeout(advance, durationMs);
    return () => window.clearTimeout(advanceTimer);
  }, [items, currentIndex, advance]);

  if (items.length === 0) {
    return (
      <div
        className={`w-full h-full flex items-center justify-center bg-muted text-muted-foreground text-sm ${className ?? ""}`}
      >
        —
      </div>
    );
  }

  const current = items[currentIndex] ?? items[0];
  // onCycleEnd only fires for PPTX/PDF and only when there's somewhere to
  // advance to. Single-item playlists let the inner player loop internally.
  const onCycleEnd =
    ownsOwnLifetime(current.kind) && items.length > 1 ? advance : undefined;
  return (
    <div
      // Stable key per item forces unmount/remount — critical for iframes (HTML preview) and to
      // reset react-pdf internal state between items.
      key={current.id}
      className={`w-full h-full relative overflow-hidden bg-background transition-opacity duration-300 ${fading ? "opacity-0" : "opacity-100"} ${className ?? ""}`}
    >
      {renderItem(current, audioEnabled, onCycleEnd)}
    </div>
  );
}
