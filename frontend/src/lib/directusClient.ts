import { createDirectus, authentication, rest } from "@directus/sdk";

// Phase 64 D-05: same-origin default. Caddy proxies /directus/* to directus:8055
// (handle_path prefix-strip). Set VITE_DIRECTUS_URL to override for dev
// workflows that need to bypass the proxy (e.g. direct :8055 access).
//
// NOTE: the Directus SDK validates its base URL via `new URL(...)` and rejects
// bare relative paths. We compose `window.location.origin + "/directus"` so
// the URL is absolute but still same-origin (cookies + no CORS preflight).
// SSR/test fallback: if `window` is unavailable, use a localhost placeholder.
const DIRECTUS_URL =
  (import.meta.env.VITE_DIRECTUS_URL as string | undefined) ??
  (typeof window !== "undefined"
    ? `${window.location.origin}/directus`
    : "http://localhost/directus");

/**
 * Singleton Directus SDK client.
 *
 * Cookie-mode auth: the SDK stores the refresh token in an httpOnly cookie
 * set by Directus on the same origin (Phase 64). `credentials: 'include'`
 * remains required so the cookie travels on refresh requests. CORS config
 * on the Directus container was removed in Phase 64 because all SPA calls
 * now go through Caddy's /directus/* reverse-proxy route (same origin);
 * no cross-origin preflight happens on normal flows.
 *
 * The short-lived access token returned by `login()` / `refresh()` is pulled
 * via `directus.getToken()` and handed to the module-singleton in
 * `apiClient.ts` (see Pattern 1 in 29-RESEARCH.md).
 */
export const directus = createDirectus(DIRECTUS_URL)
  .with(authentication("cookie", { credentials: "include" }))
  .with(rest({ credentials: "include" }));
