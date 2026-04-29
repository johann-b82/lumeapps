import {
  createContext,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { readMe } from "@directus/sdk";

import { directus } from "@/lib/directusClient";
import {
  setAccessToken,
  setAuthFailureHandler,
  trySilentRefresh,
} from "@/lib/apiClient";
import { toApiError } from "@/lib/toApiError";

export type Role = "admin" | "viewer";

export interface AuthUser {
  id: string;
  email: string;
  role: Role;
}

export interface AuthState {
  user: AuthUser | null;
  role: Role | null;
  isLoading: boolean;
  signIn: (email: string, password: string) => Promise<void>;
  signOut: () => Promise<void>;
}

export const AuthContext = createContext<AuthState | null>(null);

/**
 * D-01: map Directus role.name to the frontend Role union.
 * Unknown names return null — caller clears auth (D-09) instead of
 * silently defaulting to viewer.
 */
function mapRoleName(name: string | null | undefined): Role | null {
  switch (name) {
    case "Administrator":
      return "admin";
    case "Viewer":
      return "viewer";
    default:
      return null;
  }
}

/**
 * AuthProvider — owns user/role/isLoading React state. The short-lived access
 * token does NOT live in React state; it sits in apiClient.ts's module
 * singleton to avoid re-rendering every consumer on every refresh.
 *
 * On mount: attempt a silent refresh (uses the httpOnly Directus refresh
 * cookie set on a prior login). If it succeeds, hydrate the user via
 * directus.request(readMe(...)) — Phase 66 MIG-AUTH-01 replaces the old
 * GET that used to live on a deleted FastAPI route. If readMe fails or
 * the role name is unmapped, we land unauthenticated and <AuthGate>
 * redirects to /login.
 *
 * signIn / signOut delegate to the Directus SDK, then sync the module-singleton
 * token and React state. signOut also clears the React Query cache so a new
 * user doesn't see the previous user's data.
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const queryClient = useQueryClient();

  // StrictMode runs effects twice in dev. Guard the initial hydration so we
  // don't double-fire directus.refresh() and race the refresh-token rotation.
  const hydratedRef = useRef(false);

  // Clears auth state locally. Used by signOut() and the 401-refresh-failure
  // path (via setAuthFailureHandler below).
  const clearLocalAuth = useCallback(() => {
    setAccessToken(null);
    setUser(null);
    queryClient.clear();
  }, [queryClient]);

  // Register the apiClient auth-failure callback. This fires when a 401
  // survives a silent refresh attempt — AuthGate will then redirect to /login
  // because user becomes null.
  useEffect(() => {
    setAuthFailureHandler(() => {
      clearLocalAuth();
    });
    return () => setAuthFailureHandler(null);
  }, [clearLocalAuth]);

  // Initial hydration. hydratedRef guarantees single-run across StrictMode's
  // mount/unmount/remount; no cancellation guard — the first run's cleanup
  // would otherwise block its own setState calls, leaving isLoading true
  // forever.
  useEffect(() => {
    if (hydratedRef.current) return;
    hydratedRef.current = true;
    (async () => {
      try {
        const refreshed = await trySilentRefresh();
        if (!refreshed) {
          setUser(null);
          return;
        }
        let profile: { id: string; email: string; role: { name: string } | null };
        try {
          profile = await directus.request(
            readMe({ fields: ["id", "email", "role.name"] }),
          ) as { id: string; email: string; role: { name: string } | null };
        } catch (e) { throw toApiError(e); }
        const mappedRole = mapRoleName(profile.role?.name);
        if (!mappedRole) {
          // D-09: unknown/unmapped role clears auth like a readMe failure.
          setUser(null);
          return;
        }
        setUser({ id: String(profile.id), email: profile.email, role: mappedRole });
      } catch {
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    })();
  }, []);

  const signIn = useCallback(
    async (email: string, password: string) => {
      // Throws on bad credentials — LoginPage catches to show inline error.
      // Phase 72 ERR-01 (D-01): normalize Directus plain-object throws.
      try {
        await directus.login({ email, password });
      } catch (e) { throw toApiError(e); }
      const token = await directus.getToken();
      setAccessToken(token ?? null);
      let profile: { id: string; email: string; role: { name: string } | null };
      try {
        profile = await directus.request(
          readMe({ fields: ["id", "email", "role.name"] }),
        ) as { id: string; email: string; role: { name: string } | null };
      } catch (e) { throw toApiError(e); }
      const mappedRole = mapRoleName(profile.role?.name);
      if (!mappedRole) {
        // D-09: unknown role after a fresh login — clear and reject.
        clearLocalAuth();
        // Phase 72 D-02: domain validation error (role mapping rejected
        // client-side after a successful Directus call). NOT wrapped via
        // toApiError — LoginPage pattern-matches on err.message === "unknown_role".
        throw new Error("unknown_role");
      }
      setUser({ id: String(profile.id), email: profile.email, role: mappedRole });
    },
    [],
  );

  const signOut = useCallback(async () => {
    try {
      await directus.logout();
    } catch {
      // D-07: Network failure must still clear local auth state.
    }
    clearLocalAuth();
  }, [clearLocalAuth]);

  const value: AuthState = {
    user,
    role: user?.role ?? null,
    isLoading,
    signIn,
    signOut,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
