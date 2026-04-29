// Phase 52 Plan 02 — vitest global setup for component tests (jsdom env).
// Extends expect with @testing-library/jest-dom matchers so assertions
// like toBeInTheDocument / toBeChecked work.
import "@testing-library/jest-dom/vitest";
