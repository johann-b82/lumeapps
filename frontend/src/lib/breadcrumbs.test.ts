import { describe, it, expect } from "vitest";
import { matchBreadcrumb, BREADCRUMB_ROUTES } from "./breadcrumbs";

describe("matchBreadcrumb", () => {
  it("returns null for / (launcher, D-03)", () => {
    expect(matchBreadcrumb("/")).toBeNull();
  });

  it("returns null for /login (pre-auth, D-03)", () => {
    expect(matchBreadcrumb("/login")).toBeNull();
  });

  it("returns null for unknown route", () => {
    expect(matchBreadcrumb("/foo-unknown")).toBeNull();
  });

  it("matches /sales", () => {
    expect(matchBreadcrumb("/sales")).toEqual([
      { labelKey: "nav.sales", href: "/sales" },
    ]);
  });

  it("matches /hr", () => {
    expect(matchBreadcrumb("/hr")).toEqual([
      { labelKey: "nav.hr", href: "/hr" },
    ]);
  });

  it("matches /upload", () => {
    expect(matchBreadcrumb("/upload")).toEqual([
      { labelKey: "nav.upload", href: "/upload" },
    ]);
  });

  it("matches /sensors", () => {
    expect(matchBreadcrumb("/sensors")).toEqual([
      { labelKey: "sensors.title", href: "/sensors" },
    ]);
  });

  it("matches /settings", () => {
    expect(matchBreadcrumb("/settings")).toEqual([
      { labelKey: "nav.settings", href: "/settings" },
    ]);
  });

  it("matches /settings/sensors BEFORE /settings (specificity, Pitfall 2)", () => {
    const trail = matchBreadcrumb("/settings/sensors");
    expect(trail?.map((c) => c.labelKey)).toEqual([
      "nav.settings",
      "settings.sensors_link.title",
    ]);
  });

  it("matches /docs leaf", () => {
    expect(matchBreadcrumb("/docs")?.[0].labelKey).toBe("docs.nav.docsLabel");
  });

  it("matches /docs/user/intro — dynamic segments skipped (D-02)", () => {
    const trail = matchBreadcrumb("/docs/user/intro");
    expect(trail?.map((c) => c.labelKey)).toEqual(["docs.nav.docsLabel"]);
  });

  it("matches /signage/media with 2-entry trail", () => {
    const trail = matchBreadcrumb("/signage/media");
    expect(trail?.map((c) => c.labelKey)).toEqual([
      "signage.admin.page_title",
      "signage.admin.nav.media",
    ]);
  });

  it("matches /signage/playlists", () => {
    const trail = matchBreadcrumb("/signage/playlists");
    expect(trail?.map((c) => c.labelKey)).toEqual([
      "signage.admin.page_title",
      "signage.admin.nav.playlists",
    ]);
  });

  it("matches /signage/playlists/abc-123 to Playlists leaf (D-02 dynamic)", () => {
    const trail = matchBreadcrumb("/signage/playlists/abc-123");
    expect(trail?.map((c) => c.labelKey)).toEqual([
      "signage.admin.page_title",
      "signage.admin.nav.playlists",
    ]);
  });

  it("matches /signage/devices", () => {
    const trail = matchBreadcrumb("/signage/devices");
    expect(trail?.[trail.length - 1].labelKey).toBe("signage.admin.nav.devices");
  });

  it("matches /signage/schedules", () => {
    const trail = matchBreadcrumb("/signage/schedules");
    expect(trail?.[trail.length - 1].labelKey).toBe("signage.admin.nav.schedules");
  });

  it("matches /signage/pair with explicit breadcrumb key", () => {
    const trail = matchBreadcrumb("/signage/pair");
    expect(trail?.[trail.length - 1].labelKey).toBe("breadcrumb.signage.pair");
  });

  it("BREADCRUMB_ROUTES orders /settings/sensors before /settings", () => {
    const patterns = BREADCRUMB_ROUTES.map((r) => r.pattern);
    const specific = patterns.indexOf("/settings/sensors");
    const generic = patterns.indexOf("/settings");
    expect(specific).toBeGreaterThanOrEqual(0);
    expect(generic).toBeGreaterThanOrEqual(0);
    expect(specific).toBeLessThan(generic);
  });

  it("BREADCRUMB_ROUTES orders /signage/playlists/:id before /signage/playlists", () => {
    const patterns = BREADCRUMB_ROUTES.map((r) => r.pattern);
    const specific = patterns.indexOf("/signage/playlists/:id");
    const generic = patterns.indexOf("/signage/playlists");
    expect(specific).toBeGreaterThanOrEqual(0);
    expect(generic).toBeGreaterThanOrEqual(0);
    expect(specific).toBeLessThan(generic);
  });

  it("BREADCRUMB_ROUTES orders /docs/:section/:slug before /docs", () => {
    const patterns = BREADCRUMB_ROUTES.map((r) => r.pattern);
    const specific = patterns.indexOf("/docs/:section/:slug");
    const generic = patterns.indexOf("/docs");
    expect(specific).toBeGreaterThanOrEqual(0);
    expect(generic).toBeGreaterThanOrEqual(0);
    expect(specific).toBeLessThan(generic);
  });
});
