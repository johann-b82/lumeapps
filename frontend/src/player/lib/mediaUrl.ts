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
}

/**
 * Synchronous resolver. Reads window.signageSidecarReady at call time.
 * For the more robust hybrid detector (window flag + 200ms localhost probe), see useSidecarStatus
 * (added in Plan 47-03 per Pitfall P10).
 */
export function resolveMediaUrl(media: MediaForUrl, token?: string | null): string {
  // DEFECT-11: url/html items carry non-file uris (absolute URL or empty).
  // Only file-backed kinds (image/video/pdf/pptx) route through the asset
  // passthrough. Absolute URLs pass through verbatim.
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

export {};
