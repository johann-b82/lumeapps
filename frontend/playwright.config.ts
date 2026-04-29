import { defineConfig, devices } from "@playwright/test";

// Minimal chromium-only config for the Phase 7 rebuild-persistence harness.
// The harness (`scripts/smoke-rebuild.sh`) assumes `docker compose up` is
// already running and exposes the Vite dev server on :5173 — no webServer
// block here, we do not auto-start Vite.
export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 30_000,
  retries: 0,
  workers: 1,
  reporter: "list",
  use: {
    baseURL: "http://localhost:5173",
    trace: "on-first-retry",
  },
  projects: [
    { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  ],
});
