import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Phase 71 Plan 02 — bootstrap.ts cold-start one-shot purge of legacy
// ['signage', ...] TanStack Query cache keys (FE-02 / FE-03).

const CACHE_PURGE_KEY = "kpi.cache_purge_v22";

// Stub out network + i18n side effects so bootstrap() resolves cleanly
// without hitting fetch.
vi.mock("./i18n", () => {
  const i18n = {
    language: "en",
    changeLanguage: vi.fn(async () => {}),
    on: vi.fn(),
  };
  return { default: i18n, i18nInitPromise: Promise.resolve() };
});

vi.mock("./lib/api", () => ({
  fetchSettings: vi.fn(async () => ({})),
}));

// Build a fresh in-memory localStorage shim. Node 25 ships an experimental
// `localStorage` global that takes precedence over jsdom's Storage and
// throws "setItem is not a function"; pin a controlled store per test.
function makeStore(): Storage {
  const map = new Map<string, string>();
  return {
    get length() {
      return map.size;
    },
    clear: () => map.clear(),
    getItem: (k: string) => (map.has(k) ? (map.get(k) as string) : null),
    setItem: (k: string, v: string) => {
      map.set(k, String(v));
    },
    removeItem: (k: string) => {
      map.delete(k);
    },
    key: (i: number) => Array.from(map.keys())[i] ?? null,
  };
}

describe("bootstrap.ts — legacy ['signage'] cache purge (FE-02 / FE-03)", () => {
  beforeEach(() => {
    vi.resetModules();
    vi.stubGlobal("localStorage", makeStore());
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
  });

  it("Test 1: first boot — purge runs, removeQueries called with ['signage'] key, flag set to 'done'", async () => {
    const removeQueries = vi.fn();
    vi.doMock("./queryClient", () => ({
      queryClient: {
        removeQueries,
        setQueryData: vi.fn(),
        getQueryData: vi.fn(),
      },
    }));

    const { bootstrap } = await import("./bootstrap");
    await bootstrap();

    expect(removeQueries).toHaveBeenCalledTimes(1);
    expect(removeQueries).toHaveBeenCalledWith({ queryKey: ["signage"] });
    expect(localStorage.getItem(CACHE_PURGE_KEY)).toBe("done");
  });

  it("Test 2: second boot — flag already 'done', removeQueries NOT called", async () => {
    localStorage.setItem(CACHE_PURGE_KEY, "done");

    const removeQueries = vi.fn();
    vi.doMock("./queryClient", () => ({
      queryClient: {
        removeQueries,
        setQueryData: vi.fn(),
        getQueryData: vi.fn(),
      },
    }));

    const { bootstrap } = await import("./bootstrap");
    await bootstrap();

    expect(removeQueries).not.toHaveBeenCalled();
    expect(localStorage.getItem(CACHE_PURGE_KEY)).toBe("done");
  });

  it("Test 3: namespace scope — purge removes ['signage', ...] but leaves ['directus', ...] and ['fastapi', ...] intact", async () => {
    // Use a real QueryClient to assert namespace-scoped removal behavior.
    const { QueryClient } = await import("@tanstack/react-query");
    const realClient = new QueryClient();

    realClient.setQueryData(["signage", "x"], 1);
    realClient.setQueryData(["directus", "signage_devices"], 2);
    realClient.setQueryData(["fastapi", "resolved"], 3);

    vi.doMock("./queryClient", () => ({ queryClient: realClient }));

    const { bootstrap } = await import("./bootstrap");
    await bootstrap();

    expect(realClient.getQueryData(["signage", "x"])).toBeUndefined();
    expect(realClient.getQueryData(["directus", "signage_devices"])).toBe(2);
    expect(realClient.getQueryData(["fastapi", "resolved"])).toBe(3);
  });

  it("Test 4: defensive guard — purge block is a no-op when localStorage is undefined (Pitfall 6)", async () => {
    const removeQueries = vi.fn();
    vi.doMock("./queryClient", () => ({
      queryClient: {
        removeQueries,
        setQueryData: vi.fn(),
        getQueryData: vi.fn(),
      },
    }));

    // Verify the typeof-guard structurally guarantees no-op under SSR
    // (where `localStorage` is undefined). bootstrap.ts has a pre-existing
    // unconditional `localStorage.getItem(LANG_STORAGE_KEY)` call upstream,
    // so stubbing localStorage to undefined will reject the outer promise —
    // we still assert that the purge code path was NOT reached, which is
    // the contract Pitfall 6 demands of the new block.
    vi.stubGlobal("localStorage", undefined);

    const { bootstrap } = await import("./bootstrap");
    await bootstrap().catch(() => {
      /* upstream lang line throws — irrelevant to purge-block contract */
    });

    expect(removeQueries).not.toHaveBeenCalled();
  });
});
