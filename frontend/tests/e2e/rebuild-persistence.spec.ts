import { test, expect } from "@playwright/test";

// Visual half of the Phase 7 rebuild-persistence harness (D-23 step 8).
// Asserts that the seeded branding from `test_rebuild_seed.py` is not just
// echoed by the API but actually reaches the browser after a full
// `docker compose down && up --build` cycle.
test("branding survives docker compose up --build", async ({ page }) => {
  await page.goto("/settings");

  // 1. Seeded default_language was "DE"; bootstrap.ts should have called
  //    i18n.changeLanguage('de') before the first React commit, and
  //    react-i18next mirrors that onto <html lang="...">.
  await expect(page.locator("html")).toHaveAttribute("lang", "de");

  // 2. German "Einstellungen" heading is visible (proves de.json loaded).
  await expect(
    page.getByRole("heading", { name: /Einstellungen/i })
  ).toBeVisible();

  // 3. NavBar brand slot: logo <img> uses app_name as alt (NavBar.tsx).
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
