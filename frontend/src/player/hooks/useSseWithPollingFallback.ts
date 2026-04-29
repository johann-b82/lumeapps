// Phase 47 D-4 + D-7: SSE/watchdog/polling lifecycle.
// States: connecting → live → silent (watchdog fired) → polling → reconnecting → live.
//
// Key invariants:
//   - 45s watchdog (resettable on EventSource onopen + onmessage)
//   - On watchdog fire OR onerror: close ES, start 30s polling
//   - On successful poll: attempt SSE reconnect; if first event arrives within 5s, kill polling
//   - Token transport: ?token= query string (Pitfall P7 accepted; Phase 45 + OQ4 fix support)
//   - StrictMode safety: cleanup closes ES + clears all timers
//     (leaked EventSources crash the server's per-device queue under Phase 45 D-03)

import { useEffect, useRef } from "react";
import { playerFetch } from "@/player/lib/playerApi";

const WATCHDOG_MS = 45_000;
const POLLING_MS = 30_000;
const SSE_RECONNECT_GRACE_MS = 5_000;

export interface UseSseWithPollingFallbackOpts {
  token: string | null;
  /** e.g. "/api/signage/player/stream" */
  streamUrl: string;
  /** e.g. "/api/signage/player/playlist" */
  pollUrl: string;
  /** Called when an SSE event OR a successful poll says the playlist may have changed. */
  onPlaylistInvalidated: () => void;
  /** Called on 401 — caller wipes token. */
  onUnauthorized: () => void;
  /** Phase 62 D-05: called on `calibration-changed` SSE event so the shell can
   *  refetch /api/signage/player/calibration and flip `<video muted>`. */
  onCalibrationChanged?: () => void;
}

export function useSseWithPollingFallback(
  opts: UseSseWithPollingFallbackOpts,
): void {
  const {
    token,
    streamUrl,
    pollUrl,
    onPlaylistInvalidated,
    onUnauthorized,
    onCalibrationChanged,
  } = opts;

  // Keep callbacks in a ref so the effect's identity only depends on
  // token/streamUrl/pollUrl. Otherwise StrictMode + re-renders would churn
  // the EventSource connection.
  const callbacksRef = useRef({
    onPlaylistInvalidated,
    onUnauthorized,
    onCalibrationChanged,
  });
  callbacksRef.current = {
    onPlaylistInvalidated,
    onUnauthorized,
    onCalibrationChanged,
  };

  useEffect(() => {
    if (!token) return;

    let killed = false;
    let es: EventSource | null = null;
    let watchdog: number | undefined;
    let pollingTimer: number | undefined;
    let reconnectGrace: number | undefined;
    let lastEventAt = 0;

    const clearWatchdog = () => {
      if (watchdog !== undefined) {
        window.clearTimeout(watchdog);
        watchdog = undefined;
      }
    };
    const clearPolling = () => {
      if (pollingTimer !== undefined) {
        window.clearInterval(pollingTimer);
        pollingTimer = undefined;
      }
    };
    const clearReconnectGrace = () => {
      if (reconnectGrace !== undefined) {
        window.clearTimeout(reconnectGrace);
        reconnectGrace = undefined;
      }
    };

    const armWatchdog = () => {
      clearWatchdog();
      if (killed) return;
      watchdog = window.setTimeout(onWatchdogFire, WATCHDOG_MS);
    };

    const onWatchdogFire = () => {
      if (killed) return;
      es?.close();
      es = null;
      startPolling();
    };

    const noteEvent = () => {
      lastEventAt = Date.now();
      // If polling was running as a fallback and SSE just came back to life
      // within the grace window, stop polling immediately.
      if (reconnectGrace !== undefined) {
        clearPolling();
        clearReconnectGrace();
      }
      armWatchdog();
    };

    const openSse = () => {
      if (killed) return;
      // ?token= per Pitfall P7 (browsers can't set EventSource headers).
      // Backend accepts this via the OQ4 get_current_device tweak.
      const fullUrl = `${streamUrl}?token=${encodeURIComponent(token)}`;
      es = new EventSource(fullUrl);
      es.onopen = () => noteEvent();
      es.onmessage = (e) => {
        noteEvent();
        // Phase 45 payload {event, playlist_id, etag}; on 'playlist-changed', invalidate.
        try {
          const data = JSON.parse(e.data) as { event?: string };
          if (data.event === "playlist-changed") {
            callbacksRef.current.onPlaylistInvalidated();
          } else if (data.event === "calibration-changed") {
            // Phase 62 D-05/D-08: refetch /player/calibration and flip
            // <video muted> to match audio_enabled. Payload is {event, device_id}
            // only; full state lives behind the GET per D-08.
            callbacksRef.current.onCalibrationChanged?.();
          }
        } catch {
          // Malformed payload — still treat as liveness signal.
        }
      };
      es.onerror = () => {
        if (killed) return;
        es?.close();
        es = null;
        startPolling();
      };
      armWatchdog();
    };

    const startPolling = () => {
      if (killed || pollingTimer !== undefined) return;
      const poll = async () => {
        try {
          await playerFetch(pollUrl, {
            token,
            on401: () => callbacksRef.current.onUnauthorized(),
          });
          if (killed) return;
          // A successful poll says "playlist may have advanced" — invalidate.
          callbacksRef.current.onPlaylistInvalidated();
          // Try SSE reconnect; if first event arrives within 5s, kill polling.
          if (!es) {
            openSse();
            clearReconnectGrace();
            reconnectGrace = window.setTimeout(() => {
              // If we got an event during the grace window, polling was already cleared.
              if (Date.now() - lastEventAt <= SSE_RECONNECT_GRACE_MS) {
                clearPolling();
              }
              reconnectGrace = undefined;
            }, SSE_RECONNECT_GRACE_MS);
          }
        } catch {
          // 401 already handled inside playerFetch; other errors → keep polling silently.
        }
      };
      // Fire immediately, then on interval.
      void poll();
      pollingTimer = window.setInterval(() => void poll(), POLLING_MS);
    };

    openSse();

    return () => {
      killed = true;
      es?.close();
      es = null;
      clearWatchdog();
      clearPolling();
      clearReconnectGrace();
    };
  }, [token, streamUrl, pollUrl]);
}
