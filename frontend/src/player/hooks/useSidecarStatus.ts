// Phase 47 D-1 + Pitfall P10: hybrid sidecar detector.
// Resolution priority:
//   1. window.signageSidecarReady === true → flagged-ready
//   2. fetch('http://localhost:8080/health') with 200ms timeout → fetch-detected
//   3. neither → 'unknown' (treat as no sidecar; Offline chip stays hidden per UI-SPEC truth table)
//
// Status semantics (UI-SPEC §"Visibility rules"):
//   'unknown'  → sidecar not present (dev server, no Pi); chip HIDDEN
//   'online'   → sidecar present and reporting connectivity OK; chip HIDDEN
//   'offline'  → sidecar present and reporting connectivity FAILED; chip VISIBLE
//
// Result is cached for the session; the sidecar dispatches 'signage:sidecar-ready'
// (or 'signage:sidecar-status') on its own when status changes (Phase 48 contract),
// and the listener re-probes.
//
// This hook owns the ONLY raw fetch() call to localhost:8080 in the player tree.
// The CI guard (Plan 47-05 check-player-isolation.mjs) allowlists this file.

import { useEffect, useRef, useState } from "react";
import { postSidecarToken } from "../lib/playerApi";

export type SidecarStatus = "unknown" | "online" | "offline";

const SIDECAR_HEALTH_URL = "http://localhost:8080/health";
const PROBE_TIMEOUT_MS = 200;

async function probeSidecar(): Promise<SidecarStatus> {
  // Sync flag check first — the sidecar may set this before /health binds.
  if (typeof window !== "undefined" && window.signageSidecarReady === true) {
    return "online";
  }
  // Fetch probe with 200ms abort (Pitfall P10 — do not stall first paint).
  try {
    const r = await fetch(SIDECAR_HEALTH_URL, {
      signal: AbortSignal.timeout(PROBE_TIMEOUT_MS),
    });
    if (!r.ok) return "unknown";
    // Sidecar /health response shape (Phase 48 contract — assumed):
    //   { online: boolean }
    const body = (await r.json().catch(() => ({}))) as { online?: boolean };
    if (body.online === true) return "online";
    if (body.online === false) return "offline";
    return "online"; // sidecar exists but didn't report — assume online
  } catch {
    return "unknown";
  }
}

export function useSidecarStatus(): SidecarStatus {
  const [status, setStatus] = useState<SidecarStatus>("unknown");
  // Track previous status to detect unknown/online → offline transitions (sidecar restart).
  const prevStatusRef = useRef<SidecarStatus>("unknown");

  useEffect(() => {
    let cancelled = false;

    const runProbe = () => {
      probeSidecar().then((s) => {
        if (cancelled) return;
        const prev = prevStatusRef.current;
        prevStatusRef.current = s;
        setStatus(s);
        // Phase 48: sidecar-restart recovery — if the sidecar transitions to
        // 'offline' from a state where it was previously known to exist
        // ('unknown' means "just discovered" in this context; 'online' means
        // it just went down), re-post the cached token so the sidecar can
        // re-authenticate without re-pairing.
        if (s === "offline" && (prev === "unknown" || prev === "online")) {
          try {
            const stored = window.localStorage.getItem("signage_device_token");
            if (stored) void postSidecarToken(stored);
          } catch {
            /* localStorage unavailable — skip silently */
          }
        }
      });
    };

    // Initial probe.
    runProbe();

    // Listen for sidecar-dispatched updates (Phase 48 will dispatch one of these
    // on status changes). Phase 47 ships defensively for both names.
    if (typeof window !== "undefined") {
      window.addEventListener("signage:sidecar-ready", runProbe);
      window.addEventListener("signage:sidecar-status", runProbe);
    }

    // Periodic 30s re-probe in case sidecar comes/goes without dispatching events.
    const interval = window.setInterval(runProbe, 30_000);

    return () => {
      cancelled = true;
      if (typeof window !== "undefined") {
        window.removeEventListener("signage:sidecar-ready", runProbe);
        window.removeEventListener("signage:sidecar-status", runProbe);
      }
      window.clearInterval(interval);
    };
  }, []);

  return status;
}
