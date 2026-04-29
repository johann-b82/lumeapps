// Phase 47 UI-SPEC §Playback canvas: wraps <PlayerRenderer> with the SSE/polling
// lifecycle, duration defaults, sidecar-aware media URLs, and the offline chip
// overlay.
//
// Heartbeat: the Pi sidecar owns production heartbeats (Phase 48 D-8). As a
// browser-testing fallback (no sidecar present), the JS bundle sends a
// lightweight 60s heartbeat so admin presence/analytics reflect reality. The
// server-side event insert is idempotent (ON CONFLICT on (device_id, ts)), so
// Pi-with-sidecar + JS double-heartbeat is harmless.

import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { PlayerRenderer } from "@/signage/player/PlayerRenderer";
import type {
  PlayerItem,
  PlayerItemKind,
  PlayerTransition,
} from "@/signage/player/types";
import { fetchCalibration, playerFetch } from "@/player/lib/playerApi";
import { playerKeys } from "@/player/lib/queryKeys";
import { applyDurationDefaults } from "@/player/lib/durationDefaults";
import { resolveMediaUrl } from "@/player/lib/mediaUrl";
import { useDeviceToken } from "@/player/hooks/useDeviceToken";
import { useSseWithPollingFallback } from "@/player/hooks/useSseWithPollingFallback";
import { useSidecarStatus } from "@/player/hooks/useSidecarStatus";
import { OfflineChip } from "@/player/components/OfflineChip";

interface PlaylistEnvelopeItem {
  media_id: string;
  kind: PlayerItemKind;
  uri: string;
  duration_ms: number;
  transition: PlayerTransition | "fade" | "cut";
  position: number;
  // Optional handler-specific fields (server may emit these for pptx/html).
  slide_paths?: string[] | null;
  html?: string | null;
}

interface PlaylistEnvelope {
  playlist_id: string | null;
  name: string | null;
  items: PlaylistEnvelopeItem[];
  resolved_at: string;
}

const PLAYLIST_URL = "/api/signage/player/playlist";
const STREAM_URL = "/api/signage/player/stream";

export function PlaybackShell() {
  const { token, clearToken } = useDeviceToken();
  const queryClient = useQueryClient();
  const sidecarStatus = useSidecarStatus();

  // Phase 62 D-05 / CAL-PI-06 — local calibration state. Default `false` keeps
  // the Phase 47 autoplay-muted invariant until the admin UI enables audio.
  // The Pi sidecar handles the system-sink mute via `wpctl` in parallel; this
  // flag drives the element-level `<video muted>` attribute so both layers
  // agree (D-05 — element-level muted is NOT a no-op on top of `wpctl`).
  const [audioEnabled, setAudioEnabled] = useState(false);

  const refreshCalibration = useCallback(async () => {
    if (!token) return;
    try {
      const cal = await fetchCalibration(token, clearToken);
      setAudioEnabled(cal.audio_enabled);
    } catch {
      // Non-fatal: keep the last-known value. SSE will retry on next event;
      // the Pi sidecar still holds the authoritative wpctl + wlr-randr state.
    }
  }, [token, clearToken]);

  // Seed calibration on token arrival (initial mount after pairing).
  useEffect(() => {
    void refreshCalibration();
  }, [refreshCalibration]);

  // Initial + invalidate-driven playlist fetch. Polling fallback (30s) is driven
  // by the SSE hook, NOT a refetchInterval here — see UI-SPEC §"Data Fetching
  // Contract" (refetchInterval: false normally).
  const { data: envelope } = useQuery<PlaylistEnvelope>({
    queryKey: playerKeys.playlist(),
    queryFn: () =>
      playerFetch<PlaylistEnvelope>(PLAYLIST_URL, {
        token: token!,
        on401: clearToken,
      }),
    enabled: !!token,
    staleTime: 5 * 60_000,
    gcTime: Infinity, // never evict last-known playlist (offline cache-and-loop)
    retry: (failureCount) => failureCount < 3,
  });

  // Wire the SSE/watchdog/polling lifecycle. On any signal that the playlist may
  // have changed, invalidate the query so TanStack refetches (which reuses the
  // SW-cached response if offline).
  useSseWithPollingFallback({
    token,
    streamUrl: STREAM_URL,
    pollUrl: PLAYLIST_URL,
    onPlaylistInvalidated: () => {
      void queryClient.invalidateQueries({ queryKey: playerKeys.playlist() });
    },
    onCalibrationChanged: () => {
      void refreshCalibration();
    },
    onUnauthorized: clearToken,
  });

  // Apply per-format duration defaults (D-6) AND sidecar URL rewrite (D-1).
  // Result is memoized so PlayerRenderer's [items] reset effect only fires on
  // an actual playlist change.
  const items: PlayerItem[] = useMemo(() => {
    if (!envelope) return [];
    const mapped: PlayerItem[] = envelope.items.map((it) => {
      const transition: PlayerTransition =
        it.transition === "fade" || it.transition === "cut"
          ? it.transition
          : null;
      return {
        id: `${it.media_id}-${it.position}`,
        kind: it.kind,
        uri: resolveMediaUrl({ id: it.media_id, uri: it.uri }, token),
        html: it.html ?? null,
        slide_paths: it.slide_paths ?? null,
        duration_s: it.duration_ms > 0 ? it.duration_ms / 1000 : 0,
        transition,
      };
    });
    return applyDurationDefaults(mapped);
  }, [envelope, token]);

  // Browser-mode heartbeat fallback: 60s interval as long as the shell is
  // mounted. Pi sidecar still owns production heartbeats; this closes the gap
  // when the player is opened directly in a browser (admin QA, kiosk tabs that
  // may be backgrounded). No visibilityState guard — kiosk displays frequently
  // run with the tab unfocused, and we still want presence reflected.
  useEffect(() => {
    if (!token) return;
    const tick = () => {
      void playerFetch<void>("/api/signage/player/heartbeat", {
        token,
        method: "POST",
        body: JSON.stringify({
          current_item_id: null,
          playlist_etag: null,
        }),
        headers: { "Content-Type": "application/json" },
        on401: clearToken,
      }).catch(() => {
        // Heartbeat failures are non-fatal for playback. Silence.
      });
    };
    tick();
    const id = window.setInterval(tick, 60_000);
    return () => window.clearInterval(id);
  }, [token, clearToken]);

  // Hide cursor on playback canvas (UI-SPEC §"No user interaction" safety net).
  useEffect(() => {
    const prev = document.body.style.cursor;
    document.body.style.cursor = "none";
    return () => {
      document.body.style.cursor = prev;
    };
  }, []);

  return (
    <div className="w-screen h-screen bg-black overflow-hidden">
      <PlayerRenderer items={items} audioEnabled={audioEnabled} />
      <OfflineChip sidecarStatus={sidecarStatus} />
    </div>
  );
}
