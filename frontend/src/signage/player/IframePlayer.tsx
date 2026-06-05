export interface IframePlayerProps {
  uri: string | null;
  /** Forwarded into the iframe URL as `?duration=<seconds>` when the source is
   *  an absolute http(s) URL. The embed pages (/embed/birthdays, /embed/joiners)
   *  divide it across their internal page rotation; other embedded apps are
   *  free to ignore an unknown query string. Bare URIs without an http scheme
   *  (e.g. legacy "google.de" entries) are left untouched. */
  durationS?: number;
}

export function IframePlayer({ uri, durationS }: IframePlayerProps) {
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
