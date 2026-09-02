import { useEffect } from "react";

export interface IframePlayerProps {
  uri: string | null;
  /** Forwarded into the iframe URL as `?duration=<seconds>` when the source is
   *  an absolute http(s) URL. The embed pages (/embed/birthdays, /embed/joiners)
   *  treat it as per-page time; other embedded apps are free to ignore an
   *  unknown query string. Bare URIs without an http scheme (e.g. legacy
   *  "google.de" entries) are left untouched. */
  durationS?: number;
  /** Called when the embed page posts `{type: "embed-cycle-complete"}` to its
   *  parent window. Embed-aware playlist items (URLs containing `/embed/`)
   *  use this to drive their lifetime — same contract as PptxPlayer / PdfPlayer.
   *  Non-embed URL items just don't post and rely on the player's outer timer. */
  onCycleEnd?: () => void;
}

// Last-resort backstop: if an embed item never posts `embed-cycle-complete`
// (a stale, broken, or non-paginating page), advance anyway after this long so
// a single item can never freeze the whole playlist. Deliberately generous so
// it never truncates a legitimately paginating embed; the real postMessage
// (which arrives far sooner) wins in the normal case.
const EMBED_SAFETY_FLOOR_MS = 120_000;

export function IframePlayer({ uri, durationS, onCycleEnd }: IframePlayerProps) {
  useEffect(() => {
    if (!onCycleEnd) return;
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      onCycleEnd();
    };
    const handler = (event: MessageEvent) => {
      if (event.data && (event.data as { type?: string }).type === "embed-cycle-complete") {
        finish();
      }
    };
    window.addEventListener("message", handler);
    const safetyMs = Math.max(EMBED_SAFETY_FLOOR_MS, (durationS ?? 0) * 1000 * 3);
    const safety = window.setTimeout(finish, safetyMs);
    return () => {
      window.removeEventListener("message", handler);
      window.clearTimeout(safety);
    };
  }, [onCycleEnd, durationS]);

  if (!uri) return null;
  const src = (() => {
    if (durationS == null) return uri;
    try {
      // Site-relative uris (e.g. "/embed/worldcup") resolve against the
      // player's own origin, so a media row never has to hard-code the host
      // it happens to be deployed on.
      const base = typeof window !== "undefined" ? window.location.origin : undefined;
      const u = new URL(uri, base);
      u.searchParams.set("duration", String(durationS));
      return u.toString();
    } catch {
      return uri;
    }
  })();
  return (
    <iframe
      src={src}
      sandbox="allow-scripts allow-same-origin"
      className="w-full h-full border-0"
      title="External content"
    />
  );
}
