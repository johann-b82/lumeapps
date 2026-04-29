// Phase 47 SGN-PLY-03: full pairing surface.
// Layout per UI-SPEC §Pairing screen: full viewport bg-neutral-950, centered column, gap-16.
// Polling per UI-SPEC §"Data Fetching Contract": TanStack Query, refetchInterval 3000, gcTime 0.
//
// NOTE: this file contains TWO raw fetch() callsites for /pair/request and /pair/status.
// These endpoints are unauthenticated (Phase 42 D-15), so playerFetch (which requires a bearer
// token) is not the right adapter. Plan 47-05's check-player-isolation.mjs MUST exempt this file
// (second exempt callsite alongside frontend/src/player/lib/playerApi.ts).

import { useEffect, useState } from "react";
import { useLocation } from "wouter";
import { useQuery } from "@tanstack/react-query";
import { playerKeys } from "@/player/lib/queryKeys";
import { postSidecarToken } from "@/player/lib/playerApi";
import { t } from "@/player/lib/strings";
import { PairingCode } from "@/player/components/PairingCode";

interface PairRequestResponse {
  pairing_code: string;
  pairing_session_id: string;
  expires_in: number;
}

type PairStatusResponse =
  | { status: "pending" }
  | { status: "expired" }
  | { status: "claimed"; device_token: string }
  | { status: "claimed_consumed" };

const STORAGE_KEY = "signage_device_token";

/** Anonymous request — no Authorization header (Phase 42 D-15 — /pair/request is unauthenticated). */
async function requestPairingSession(): Promise<PairRequestResponse> {
  const r = await fetch("/api/signage/pair/request", { method: "POST" });
  if (!r.ok) throw new Error(`pair/request failed ${r.status}`);
  return (await r.json()) as PairRequestResponse;
}

async function fetchPairStatus(sessionId: string): Promise<PairStatusResponse> {
  const r = await fetch(
    `/api/signage/pair/status?pairing_session_id=${encodeURIComponent(sessionId)}`,
  );
  if (!r.ok) throw new Error(`pair/status failed ${r.status}`);
  return (await r.json()) as PairStatusResponse;
}

export function PairingScreen() {
  const [, navigate] = useLocation();
  const [session, setSession] = useState<PairRequestResponse | null>(null);
  const [requestError, setRequestError] = useState(false);

  // DEFECT-4: /player/ must resume from a saved token before allocating a
  // fresh pairing code. Without this, a reload after claim drops the kiosk
  // back into the pairing flow with a brand-new code.
  useEffect(() => {
    try {
      const saved = window.localStorage.getItem(STORAGE_KEY);
      if (saved) navigate(`/${saved}`);
    } catch {
      /* noop */
    }
  }, [navigate]);

  // Open a session on mount; re-issue on `expired` or after `expires_in` countdown elapses.
  useEffect(() => {
    // Skip session allocation if we already hold a token — the effect above
    // will have fired navigate() and this screen is about to unmount.
    try {
      if (window.localStorage.getItem(STORAGE_KEY)) return;
    } catch {
      /* noop */
    }
    let cancelled = false;
    let expiryTimer: number | undefined;

    const open = () => {
      requestPairingSession()
        .then((s) => {
          if (cancelled) return;
          setRequestError(false);
          setSession(s);
          // Re-issue 5s before expiry to avoid a brief gap.
          const ms = Math.max(5_000, (s.expires_in - 5) * 1000);
          expiryTimer = window.setTimeout(() => {
            if (!cancelled) open();
          }, ms);
        })
        .catch(() => {
          if (cancelled) return;
          setRequestError(true);
          // Retry every 5s silently per UI-SPEC §"Error state".
          expiryTimer = window.setTimeout(() => {
            if (!cancelled) open();
          }, 5_000);
        });
    };

    open();
    return () => {
      cancelled = true;
      if (expiryTimer) window.clearTimeout(expiryTimer);
    };
  }, []);

  // Poll status every 3s while a session is open.
  const { data: status } = useQuery<PairStatusResponse>({
    queryKey: playerKeys.pairStatus(session?.pairing_session_id ?? null),
    queryFn: () => fetchPairStatus(session!.pairing_session_id),
    refetchInterval: 3_000,
    enabled: !!session,
    gcTime: 0,
    staleTime: 0,
    retry: false,
  });

  // On `claimed`: persist token, navigate to playback. `claimed_consumed` is a no-op on this screen
  // (we already navigated away on the prior poll). `expired` triggers a fresh request.
  useEffect(() => {
    if (!status) return;
    if (status.status === "claimed") {
      try {
        window.localStorage.setItem(STORAGE_KEY, status.device_token);
      } catch {
        /* fail soft — URL token still works for this session */
      }
      // Phase 48: push the new device JWT to the Pi sidecar so it can make
      // authenticated upstream requests. Fire-and-forget — sidecar absence
      // must not delay the pairing UX. The 30s re-probe in useSidecarStatus
      // will re-post if the sidecar comes online later.
      void postSidecarToken(status.device_token);
      // DEFECT-2: wouter Router base="/player" prepends the base automatically.
      // navigate("/<token>") composes to "/player/<token>"; the prior
      // navigate("/player/<token>") composed to "/player/player/<token>".
      navigate(`/${status.device_token}`);
    } else if (status.status === "expired") {
      // Force re-issue: drop the session so polling pauses, then re-request.
      setSession(null);
      requestPairingSession()
        .then((s) => {
          setRequestError(false);
          setSession(s);
        })
        .catch(() => setRequestError(true));
    }
  }, [status, navigate]);

  const code = session?.pairing_code ?? null;
  // requestError state is silently retried per UI-SPEC; the surface still shows the placeholder em-dash.
  // Variable referenced to satisfy linter:
  void requestError;

  return (
    <main className="w-screen h-screen bg-neutral-950 flex flex-col items-center justify-center gap-16">
      <h1 className="text-6xl font-semibold leading-tight text-neutral-50">
        {t("pair.headline")}
      </h1>
      <PairingCode code={code} />
      <p className="text-2xl font-normal text-neutral-400 max-w-3xl text-center px-4">
        {t("pair.hint")}
      </p>
    </main>
  );
}
