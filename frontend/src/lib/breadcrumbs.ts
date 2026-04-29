/**
 * Static route→breadcrumb-label-key map. Values are i18n keys resolved via t().
 *
 * Each entry is an ORDERED chain of crumbs (excluding the implicit Home crumb,
 * which is prepended at render time, D-04). Leaf order == display order.
 *
 * Dynamic segments (e.g. /signage/playlists/:id) MUST resolve to the pattern
 * that owns the dynamic segment (parent "playlists" as leaf, D-02). The matcher
 * walks patterns top-down, so deeper-before-shallower order is enforced here
 * (Pitfall 2 — keeps future matcher tweaks safe).
 *
 * Phase 56 Plan 01 — HDR-02, HDR-03.
 */

export type BreadcrumbEntry = {
  /** i18n key for this crumb label. */
  labelKey: string;
  /** Href for this crumb. Omit on the leaf pattern when it equals the
   *  current route itself (the renderer always renders the last crumb
   *  as aria-current="page", D-06). */
  href?: string;
};

export const BREADCRUMB_ROUTES: ReadonlyArray<{
  pattern: string;
  trail: ReadonlyArray<BreadcrumbEntry>;
}> = [
  // Dashboards
  { pattern: "/sales", trail: [{ labelKey: "nav.sales", href: "/sales" }] },
  { pattern: "/hr", trail: [{ labelKey: "nav.hr", href: "/hr" }] },
  // Upload
  { pattern: "/upload", trail: [{ labelKey: "nav.upload", href: "/upload" }] },
  // Sensors dashboard
  { pattern: "/sensors", trail: [{ labelKey: "sensors.title", href: "/sensors" }] },
  // Settings tree — deeper first
  {
    pattern: "/settings/sensors",
    trail: [
      { labelKey: "nav.settings", href: "/settings" },
      { labelKey: "settings.sensors_link.title", href: "/settings/sensors" },
    ],
  },
  { pattern: "/settings", trail: [{ labelKey: "nav.settings", href: "/settings" }] },
  // Docs — dynamic segments collapse to the parent leaf (D-02)
  {
    pattern: "/docs/:section/:slug",
    trail: [{ labelKey: "docs.nav.docsLabel", href: "/docs" }],
  },
  { pattern: "/docs", trail: [{ labelKey: "docs.nav.docsLabel", href: "/docs" }] },
  // Signage — deeper first so /signage/playlists/:id wins over /signage/playlists
  {
    pattern: "/signage/playlists/:id",
    trail: [
      { labelKey: "signage.admin.page_title", href: "/signage/media" },
      { labelKey: "signage.admin.nav.playlists", href: "/signage/playlists" },
    ],
  },
  {
    pattern: "/signage/playlists",
    trail: [
      { labelKey: "signage.admin.page_title", href: "/signage/media" },
      { labelKey: "signage.admin.nav.playlists", href: "/signage/playlists" },
    ],
  },
  {
    pattern: "/signage/devices",
    trail: [
      { labelKey: "signage.admin.page_title", href: "/signage/media" },
      { labelKey: "signage.admin.nav.devices", href: "/signage/devices" },
    ],
  },
  {
    pattern: "/signage/media",
    trail: [
      { labelKey: "signage.admin.page_title", href: "/signage/media" },
      { labelKey: "signage.admin.nav.media", href: "/signage/media" },
    ],
  },
  {
    pattern: "/signage/schedules",
    trail: [
      { labelKey: "signage.admin.page_title", href: "/signage/media" },
      { labelKey: "signage.admin.nav.schedules", href: "/signage/schedules" },
    ],
  },
  {
    pattern: "/signage/pair",
    trail: [
      { labelKey: "signage.admin.page_title", href: "/signage/media" },
      { labelKey: "breadcrumb.signage.pair", href: "/signage/pair" },
    ],
  },
] as const;

/**
 * Match a pathname against the route table. Returns the trail for the first
 * matching pattern, or null for routes excluded from breadcrumbs (/, /login)
 * or unknown routes.
 *
 * Dynamic segments (":id") match any non-empty segment with no "/".
 */
export function matchBreadcrumb(
  pathname: string,
): ReadonlyArray<BreadcrumbEntry> | null {
  if (pathname === "/" || pathname === "/login") return null;
  for (const { pattern, trail } of BREADCRUMB_ROUTES) {
    if (matchesPattern(pathname, pattern)) return trail;
  }
  return null;
}

function matchesPattern(pathname: string, pattern: string): boolean {
  const pSegs = pathname.split("/").filter(Boolean);
  const tSegs = pattern.split("/").filter(Boolean);
  if (pSegs.length !== tSegs.length) return false;
  return tSegs.every((t, i) =>
    t.startsWith(":") ? (pSegs[i] ?? "").length > 0 : t === pSegs[i],
  );
}
