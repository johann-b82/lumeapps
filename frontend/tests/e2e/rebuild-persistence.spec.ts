import { test, expect } from "@playwright/test";

// Visual half of the Phase 7 rebuild-persistence harness (D-23 step 8).
// Asserts that the seeded branding from `test_rebuild_seed.py` is not just
// echoed by the API but actually reaches the browser after a full
// `docker compose down && up --build` cycle.
test("branding survives docker compose up --build", async ({ page, request }) => {
  // v1.24: log in via Directus cookie-mode auth before touching protected
  // routes. Smoke-rebuild reseeds the DB but does not preserve browser
  // state, so a clean session has no auth cookie.
  const adminEmail = process.env.DIRECTUS_ADMIN_EMAIL ?? "admin@example.com";
  const adminPassword = process.env.DIRECTUS_ADMIN_PASSWORD;
  if (!adminPassword) {
    throw new Error(
      "DIRECTUS_ADMIN_PASSWORD env var not set — required for E2E login",
    );
  }
  const loginRes = await request.post("http://localhost/directus/auth/login", {
    data: { email: adminEmail, password: adminPassword, mode: "cookie" },
  });
  if (!loginRes.ok()) {
    throw new Error(
      `Directus login failed (${loginRes.status()}): ${await loginRes.text()}`,
    );
  }
  // Carry the auth cookie into the page context.
  const cookies = (await request.storageState()).cookies;
  await page.context().addCookies(cookies);

  await page.goto("/settings");
  await page.waitForLoadState("networkidle");

  // (Removed v1.24) `default_language` was deleted from app_settings in v1.6
  // — it now lives in localStorage. The lang/heading assertions that used to
  // be here can't run after a clean rebuild because there's no per-server
  // default to restore. Logo + primary-color persistence still apply.

  // NavBar brand slot: logo <img> uses app_name as alt (NavBar.tsx).
  const logo = page.locator('nav img[alt="Rebuild Test Corp"]');
  await expect(logo).toBeVisible();

  // 4. Primary color CSS var matches the seeded oklch — proves ThemeProvider
  //    wrote --primary to :root after the post-rebuild GET /api/settings.
  const primary = await page.evaluate(() =>
    getComputedStyle(document.documentElement)
      .getPropertyValue("--primary")
      .trim()
  );
  expect(primary).toContain("oklch(0.5 0.2 30)");
});
