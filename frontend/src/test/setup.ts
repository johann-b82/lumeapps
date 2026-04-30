// Phase 52 Plan 02 — vitest global setup for component tests (jsdom env).
// Extends expect with @testing-library/jest-dom matchers so assertions
// like toBeInTheDocument / toBeChecked work.
import "@testing-library/jest-dom/vitest";

// v1.25: jsdom does not implement ResizeObserver or window.matchMedia, but
// `Toggle` (and any component using its indicator-position effect) reads
// both at mount. Provide minimal shims so existing tests stop crashing on
// initial render.
if (typeof globalThis.ResizeObserver === "undefined") {
  class ResizeObserverShim {
    observe() {}
    unobserve() {}
    disconnect() {}
  }
  globalThis.ResizeObserver = ResizeObserverShim as unknown as typeof ResizeObserver;
}

if (typeof window !== "undefined" && typeof window.matchMedia === "undefined") {
  Object.defineProperty(window, "matchMedia", {
    writable: true,
    value: (query: string) => ({
      matches: false,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
      onchange: null,
      dispatchEvent: () => false,
    }),
  });
}
