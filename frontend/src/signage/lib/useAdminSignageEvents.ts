import { useEffect } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { signageKeys } from "@/lib/queryKeys";

/**
 * Phase 52 Plan 02 — admin-side SSE event handler.
 *
 * Mounts an EventSource against /api/signage/admin/stream (if available) and
 * dispatches over the event kind in the payload. The admin stream is a
 * best-effort signal — admin mutations already call
 * queryClient.invalidateQueries() directly on success, so a missing or
 * failing SSE connection is non-fatal (onerror silently closes).
 *
 * Phase 51 backend emits \`schedule-changed\` events on schedule CRUD (per-
 * device fanout for player re-resolution). This admin hook invalidates the
 * local schedules() + playlists() caches on those events so other admin
 * sessions stay in sync.
 */
type EventKind = "schedule-changed" | "playlist-changed" | "device-changed";

interface SignageEventPayload {
  event?: EventKind;
  kind?: EventKind; // backward-compat: some fanouts use `kind`
}

export interface AdminSignageEventsOptions {
  /** URL override (defaults to /api/signage/admin/stream). */
  url?: string;
  /** Disable entirely (e.g. when not authenticated). */
  enabled?: boolean;
}

export function useAdminSignageEvents(opts: AdminSignageEventsOptions = {}) {
  const queryClient = useQueryClient();
  const { url = "/api/signage/admin/stream", enabled = true } = opts;

  useEffect(() => {
    if (!enabled) return;
    if (typeof window === "undefined") return;
    if (typeof window.EventSource !== "function") return;

    let es: EventSource | null = null;
    let killed = false;
    try {
      es = new EventSource(url);
    } catch {
      return;
    }

    es.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data) as SignageEventPayload;
        const kind = data.event ?? data.kind;
        // Phase 73 (CACHE-01 / D-03): signageKeys.X() now returns
        // ['directus', 'signage_X'] directly — no duplicate literal-key
        // invalidation needed. ['fastapi', 'resolved'] is intentionally
        // a separate cache prefix and is invalidated on top.
        switch (kind) {
          case "schedule-changed":
            queryClient.invalidateQueries({
              queryKey: signageKeys.schedules(),
            });
            break;
          case "playlist-changed":
            queryClient.invalidateQueries({
              queryKey: signageKeys.playlists(),
            });
            // Phase 70-04 (D-05a, Pitfall 1): tag-map mutations on
            // signage_device_tag_map ALSO fire device-changed (not playlist-changed)
            // per signage_pg_listen.py:86-88, but a true playlist-changed event
            // (item reorder, metadata) may flip the resolver output for any device
            // whose tags match. Invalidate the entire ['fastapi', 'resolved']
            // prefix so all per-device caches refresh.
            queryClient.invalidateQueries({
              queryKey: ["fastapi", "resolved"],
            });
            break;
          case "device-changed":
            queryClient.invalidateQueries({
              queryKey: signageKeys.devices(),
            });
            queryClient.invalidateQueries({
              queryKey: ["fastapi", "resolved"],
            });
            break;
          default:
            break;
        }
      } catch {
        // Malformed payload — ignore.
      }
    };

    es.onerror = () => {
      if (killed) return;
      // Admin stream is best-effort; close on error (no reconnect — the
      // admin mutation path is already the authoritative invalidator).
      es?.close();
      es = null;
    };

    return () => {
      killed = true;
      es?.close();
      es = null;
    };
  }, [url, enabled, queryClient]);
}
