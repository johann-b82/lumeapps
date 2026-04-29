// Phase 47 D-2: token resolution + persistence + clear-on-401.
// Priority: URL path token → localStorage → null.
// Side effect: when URL provides the token, persist to localStorage so a /player/ (no token) reload recovers identity.

import { useEffect, useState, useCallback } from "react";
import { useParams, useLocation } from "wouter";

const STORAGE_KEY = "signage_device_token";

export interface UseDeviceTokenResult {
  token: string | null;
  clearToken: () => void;
}

export function useDeviceToken(): UseDeviceTokenResult {
  const params = useParams<{ token?: string }>();
  const [, navigate] = useLocation();

  // Initial read is synchronous so first paint has the right surface.
  const [token, setToken] = useState<string | null>(() => {
    if (typeof window === "undefined") return null;
    const fromUrl = params?.token ?? null;
    if (fromUrl) return fromUrl;
    try {
      return window.localStorage.getItem(STORAGE_KEY);
    } catch {
      return null;
    }
  });

  // Persist URL token to localStorage on mount AND when params.token changes.
  useEffect(() => {
    if (typeof window === "undefined") return;
    if (!params?.token) return;
    try {
      const stored = window.localStorage.getItem(STORAGE_KEY);
      if (stored !== params.token) {
        window.localStorage.setItem(STORAGE_KEY, params.token);
      }
    } catch {
      // localStorage may be disabled (private browsing); fail soft — URL still works for this session.
    }
    setToken(params.token);
  }, [params?.token]);

  const clearToken = useCallback(() => {
    if (typeof window !== "undefined") {
      try {
        window.localStorage.removeItem(STORAGE_KEY);
      } catch {
        /* fail soft */
      }
    }
    setToken(null);
    // DEFECT-2 (revoke path): wouter Router base="/player" already prepends
    // the base. Navigate to "/" to land at "/player/" (not "/player/player/").
    navigate("/");
  }, [navigate]);

  return { token, clearToken };
}
