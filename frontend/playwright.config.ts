import { defineConfig, devices } from "@playwright/test";

// Minimal chromium-only config for the Phase 7 rebuild-persistence harness.
// The harness (`scripts/smoke-rebuild.sh`) assumes `docker compose up` is
// already running. v1.24: target the Caddy proxy on :80 (added v1.21) so
// /directus/* and /api/* are reachable via same-origin paths — required for
// cookie-mode Directus auth and for the SPA's runtime calls.
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  retries: 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://localhost",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
