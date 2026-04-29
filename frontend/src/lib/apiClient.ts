import { directus } from "./directusClient";
import { toApiError } from "./toApiError";

// ---------------------------------------------------------------------------
// Module-singleton access token
// ---------------------------------------------------------------------------
// apiClient.ts is a plain module (not a React component), so it cannot call
// useAuth(). The token lives here as a module-level variable; AuthContext
// pushes updates via setAccessToken() on login/refresh/logout. This avoids
// a circular import between AuthContext and apiClient.
// See 29-RESEARCH.md "Pattern 1: Module Singleton for Token".

let _accessToken: string | null = null;

export function setAccessToken(token: string | null): void {
  _accessToken = token;
}

export function getAccessToken(): string | null {
  return _accessToken;
}

// ---------------------------------------------------------------------------
// Auth-failure callback (AuthContext plugs in cleanup + redirect)
// ---------------------------------------------------------------------------

let _onAuthFailure: (() => void) | null = null;

/**
 * AuthContext calls this once on mount to register a handler that will be
 * invoked when a 401 survives a silent-refresh attempt. Keeps apiClient free
 * of React / router imports.
 */
export function setAuthFailureHandler(fn: (() => void) | null): void {
  _onAuthFailure = fn;
}

// ---------------------------------------------------------------------------
// Concurrent-refresh guard
// ---------------------------------------------------------------------------
// If multiple requests 401 simultaneously we must only call directus.refresh()
// once — otherwise we'd race the refresh-token rotation and bounce back to
// login. A shared promise collapses all concurrent 401s onto a single refresh.

let _refreshPromise: Promise<boolean> | null = null;

export async function trySilentRefresh(): Promise<boolean> {
  if (_refreshPromise) return _refreshPromise;
  _refreshPromise = (async () => {
    try {
      // Phase 72 ERR-01 (D-01, D-01b): normalize directus.refresh() throws
      // through toApiError. The outer catch below swallows the normalized
      // throw and returns false so the public boolean contract is preserved
      // for both _doRequest's 401-retry path and AuthContext's consumer.
      // The wrap is observable in tests but transparent to UX.
      try {
        await directus.refresh();
      } catch (e) { throw toApiError(e); }
      const token = await directus.getToken();
      if (!token) return false;
      setAccessToken(token);
      return true;
    } catch {
      return false;
    } finally {
      // Clear on next tick so callers racing this promise still see the
      // resolved value before a fresh refresh can start.
      queueMicrotask(() => {
        _refreshPromise = null;
      });
    }
  })();
  return _refreshPromise;
}

// ---------------------------------------------------------------------------
// apiClient<T>()
// ---------------------------------------------------------------------------

interface ErrorBody {
  detail?: string | unknown;
}

/**
 * Thin fetch wrapper that:
 *   1. Attaches `Authorization: Bearer <token>` when a token is set.
 *   2. Leaves FormData bodies untouched (no forced Content-Type) so multipart
 *      uploads keep working — see frontend/src/lib/api.ts uploadFile/uploadLogo.
 *   3. Handles 401 with one silent refresh + retry. If refresh fails, invokes
 *      the auth-failure handler (AuthContext clears state; AuthGate redirects).
 *   4. Throws `Error(body.detail ?? "<status> <statusText>")` on non-ok non-401
 *      so the legacy `err.detail` contract from api.ts is preserved.
 */
export async function apiClient<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  return _doRequest<T>(path, init, /* retriedAfterRefresh */ false);
}

async function _doRequest<T>(
  path: string,
  init: RequestInit,
  retriedAfterRefresh: boolean,
): Promise<T> {
  const token = _accessToken;

  // Only set Content-Type: application/json when the caller did not provide
  // one AND the body is not FormData. FormData must set its own multipart
  // boundary header — forcing JSON breaks uploads.
  const callerHeaders = (init.headers ?? {}) as Record<string, string>;
  const isFormData =
    typeof FormData !== "undefined" && init.body instanceof FormData;
  const hasContentType = Object.keys(callerHeaders).some(
    (k) => k.toLowerCase() === "content-type",
  );
  const headers: Record<string, string> = { ...callerHeaders };
  if (init.body !== undefined && !isFormData && !hasContentType) {
    headers["Content-Type"] = "application/json";
  }
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(path, { ...init, headers });

  if (res.status === 401 && !retriedAfterRefresh) {
    const refreshed = await trySilentRefresh();
    if (refreshed) {
      return _doRequest<T>(path, init, true);
    }
    if (_onAuthFailure) _onAuthFailure();
    throw new Error("unauthorized");
  }

  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as ErrorBody;
    const detail =
      typeof body.detail === "string"
        ? body.detail
        : `${res.status} ${res.statusText}`;
    throw new Error(detail);
  }

  // 204 No Content and friends — don't attempt json parse.
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
