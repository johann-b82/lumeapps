// Phase 47 D-6: per-format default duration_s when item omits it.
// SINGLE SOURCE OF TRUTH — change here only.
//
// NOTE on typing: PlayerItem (from frontend/src/signage/player/types.ts, defined
// in Phase 46-03) requires `duration_s: number` (no undefined). The envelope
// normalizer upstream (Phase 43 resolver, duration_ms → duration_s) ensures
// every item has a number, but server may emit 0 as a "use default" sentinel
// for kinds whose duration is per-unit (pdf pages, pptx slides) or natural-end
// (video). This helper replaces 0 / missing with per-format defaults.
//
// `kind === "pdf"` has no `pageCount` on PlayerItem today; page count is read
// at render time inside PdfPlayer. The default here applies a flat fallback
// per-item; once pageCount is plumbed into PlayerItem we can multiply.

import type { PlayerItem } from "@/signage/player/types";

export const IMAGE_DEFAULT_DURATION_S = 10;
export const PDF_PER_PAGE_DURATION_S = 6;
export const IFRAME_DEFAULT_DURATION_S = 30;
export const HTML_DEFAULT_DURATION_S = 30;
export const PPTX_PER_SLIDE_DURATION_S = 8;
/** Sentinel meaning "let the video element's onended advance the playlist" (D-6). */
export const VIDEO_DURATION_NATURAL = 0;

/**
 * Fill in `duration_s` on items that omit it (duration_s <= 0 treated as unset),
 * per the per-format defaults. Pure: returns a new array; does not mutate inputs.
 *
 * NOTE: PlayerItem.kind uses "url" (not "iframe") per the Phase 46-03 contract.
 */
export function applyDurationDefaults(items: PlayerItem[]): PlayerItem[] {
  return items.map((item) => {
    if (typeof item.duration_s === "number" && item.duration_s > 0) return item;
    switch (item.kind) {
      case "image":
        return { ...item, duration_s: IMAGE_DEFAULT_DURATION_S };
      case "video":
        return { ...item, duration_s: VIDEO_DURATION_NATURAL };
      case "pdf":
        // pageCount not in PlayerItem today; apply single-page default.
        // When pageCount lands on the type, multiply by PDF_PER_PAGE_DURATION_S.
        return { ...item, duration_s: PDF_PER_PAGE_DURATION_S };
      case "url":
        return { ...item, duration_s: IFRAME_DEFAULT_DURATION_S };
      case "html":
        return { ...item, duration_s: HTML_DEFAULT_DURATION_S };
      case "pptx": {
        const slidePaths = Array.isArray(item.slide_paths) ? item.slide_paths : [];
        const n = slidePaths.length || 1;
        return { ...item, duration_s: n * PPTX_PER_SLIDE_DURATION_S };
      }
      default:
        return item;
    }
  });
}
