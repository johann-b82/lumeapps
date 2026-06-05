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

export function IframePlayer({ uri, durationS, onCycleEnd }: IframePlayerProps) {
  useEffect(() => {
    if (!onCycleEnd) return;
    const handler = (event: MessageEvent) => {
      if (event.data && (event.data as { type?: string }).type === "embed-cycle-complete") {
        onCycleEnd();
      }
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [onCycleEnd]);

  if (!uri) return null;
  const src = (() => {
    if (durationS == null) return uri;
    try {
      const u = new URL(uri); // requires absolute URL
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
