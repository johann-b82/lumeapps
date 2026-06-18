// Phase 47 D-1: rewrite media URLs to localhost:8080 when the Phase 48 sidecar is online.
// Phase 47 ships the detector; Phase 48 ships the sidecar.

declare global {
  interface Window {
    signageSidecarReady?: boolean;
  }
}

export interface MediaForUrl {
  id: string;
  uri: string;
  kind?: string;
}

/**
 * Synchronous resolver. Reads window.signageSidecarReady at call time.
 * For the more robust hybrid detector (window flag + 200ms localhost probe), see useSidecarStatus
 * (added in Plan 47-03 per Pitfall P10).
 */
export function resolveMediaUrl(media: MediaForUrl, token?: string | null): string {
  // url media (websites + internal /embed pages) are shown as a LIVE iframe of
  // the page itself, so dynamic content keeps updating. The raw uri is used
  // verbatim: absolute http(s) URLs load directly; site-relative uris like
  // /embed/worldcup resolve against the player's origin — which is Caddy, where
  // /embed/* is served by the frontend and self-refreshes via /api polling.
  if (media.kind === "url") return media.uri;
  if (/^https?:\/\//i.test(media.uri)) return media.uri;
  if (!media.uri) return "";

  if (typeof window !== "undefined" && window.signageSidecarReady === true) {
    return `http://localhost:8080/media/${media.id}`;
  }
  // DEFECT-5: media.uri is a bare Directus file UUID; route through the
  // backend device-auth'd asset passthrough. <img>/<video> cannot set the
  // Authorization header, so use the ?token=… query form (OQ4 contract).
  const base = `/api/signage/player/asset/${media.id}`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

/**
 * PPTX slide URL resolver. Conversion writes slides server-side under
 * /app/media/slides/<media_id>/slide-NNN.png, exposed via the device-auth'd
 * /api/signage/player/asset/<media_id>/slide/<idx> endpoint. <img> can't set
 * Authorization, so the device token rides in as ?token=… same as other assets.
 *
 * Sidecar path mirrors resolveMediaUrl — the kiosk's local proxy is expected to
 * forward /media/<id>/slide/<idx> upstream (no-op until the sidecar adds that
 * route; until then we still go through the backend even when the sidecar is
 * online, since browsing the wrong scheme would just 404).
 */
export function resolveSlideUrl(
  mediaId: string,
  idx: number,
  token?: string | null,
): string {
  if (typeof window !== "undefined" && window.signageSidecarReady === true) {
    return `http://localhost:8080/media/${mediaId}/slide/${idx}`;
  }
  const base = `/api/signage/player/asset/${mediaId}/slide/${idx}`;
  return token ? `${base}?token=${encodeURIComponent(token)}` : base;
}

export {};
