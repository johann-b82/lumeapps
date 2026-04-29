import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Phase 52 Plan 02 — dedicated vitest config so component tests get jsdom
// and @testing-library matchers without polluting the Vite build config.
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    environmentMatchGlobs: [
      // Pure-logic tests (no DOM) can stay in node env for speed — vitest
      // picks jsdom by default because of `environment` above; override for
      // the handful of non-DOM test files.
      ["src/signage/lib/scheduleAdapters.test.ts", "node"],
      ["src/lib/chartTimeUtils.test.ts", "node"],
      ["src/components/sensors/sensorDelta.test.ts", "node"],
      ["src/hooks/useSensorDraft.test.ts", "node"],
    ],
  },
});
