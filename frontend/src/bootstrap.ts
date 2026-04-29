import i18n, { i18nInitPromise } from "./i18n";
import { queryClient } from "./queryClient";
import { fetchSettings } from "./lib/api";

const LANG_STORAGE_KEY = "kpi-light-lang";
const CACHE_PURGE_KEY = "kpi.cache_purge_v22";

// Guard against double-init (hot reload, StrictMode effects, etc.).
let bootstrapPromise: Promise<void> | null = null;

/**
 * Single cold-start writer for initial i18n language and the TanStack
 * `["settings"]` cache entry.
 *
 * Language is read from localStorage (frontend-only).
 * Settings are fetched from /api/settings for theme/Personio config.
 */
let htmlLangHookWired = false;
function wireHtmlLangSync() {
  if (htmlLangHookWired) return;
  htmlLangHookWired = true;
  const apply = (lng: string) => {
    if (typeof document !== "undefined") {
      document.documentElement.lang = lng;
    }
  };
  apply(i18n.language);
  i18n.on("languageChanged", (lng) => {
    apply(lng);
    localStorage.setItem(LANG_STORAGE_KEY, lng);
  });
}

export function bootstrap(): Promise<void> {
  if (bootstrapPromise) return bootstrapPromise;
  bootstrapPromise = (async () => {
    await i18nInitPromise;
    wireHtmlLangSync();

    // Language from localStorage (frontend-only)
    const storedLang = localStorage.getItem(LANG_STORAGE_KEY) || "en";
    await i18n.changeLanguage(storedLang);

    // Settings from API (theme, Personio config — no language)
    try {
      const settings = await fetchSettings();
      queryClient.setQueryData(["settings"], settings);
    } catch (err) {
      // eslint-disable-next-line no-console
      console.warn("[bootstrap] fetchSettings failed:", err);
    }

    // Phase 71 FE-03 (D-02 / D-02a): one-shot purge of legacy ['signage', ...]
    // cache keys to evict pre-Phase-65 cached /api/signage/* responses. New
    // ['directus', ...] and ['fastapi', ...] namespaces are NOT touched.
    //
    // Phase 73 CACHE-03 (D-06 / D-06a): RETAIN through v1.23.
    // Sunset target: v1.24. See docs/architecture.md "Cache Namespace
    // Migration & v22 Purge Flag (Phase 73 CACHE-03)" for rationale.
    if (typeof localStorage !== "undefined" && localStorage.getItem(CACHE_PURGE_KEY) !== "done") {
      queryClient.removeQueries({ queryKey: ["signage"] });
      localStorage.setItem(CACHE_PURGE_KEY, "done");
    }
  })();
  return bootstrapPromise;
}
