// Debounce device-token revocation so a transient 401 does NOT unpair a kiosk.
//
// Device JWTs are non-expiring (revoke-only). The backend nonetheless returns
// 401 for a *missing* device row as well as a genuinely revoked one
// (backend/app/security/device_auth.py). During a server restart, a DB restore,
// or the reboot startup race, the device row can be briefly unresolvable while
// the API is already answering requests — so one heartbeat 401s and, under the
// naive "any 401 → clearToken" policy, permanently wipes a still-valid token and
// strands the kiosk on the pairing screen (see operator-runbook §17–19).
//
// Policy: a 401 is only treated as a real revoke once 401s have persisted
// CONTINUOUSLY — with no successful authenticated response resetting the clock —
// for REVOKE_CONFIRM_MS. A genuine admin revoke keeps 401ing forever and so
// still drops to pairing (within ~REVOKE_CONFIRM_MS); a transient blip resolves
// on the next successful heartbeat and the token is preserved. This mirrors the
// sidecar's `_PROBE_FAIL_THRESHOLD` and the SSE watchdog: conclude only after a
// failure is sustained, never on the first strike.

import { useCallback, useRef } from "react";

// Genuine revoke drops to pairing within roughly this window; transient
// server-unhealthy 401s shorter than this are tolerated. Kept above a couple of
// heartbeat cycles (60s each) so a normal restart never crosses it.
export const REVOKE_CONFIRM_MS = 3 * 60_000;

export interface RevocationGuard {
  /** Wire into every authed `on401` / `onUnauthorized` callsite. */
  onUnauthorized: () => void;
  /** Call on any successful authenticated response to reset the strike clock. */
  noteAuthSuccess: () => void;
}

export function useRevocationGuard(onConfirmedRevoke: () => void): RevocationGuard {
  const firstStrikeAtRef = useRef<number | null>(null);

  const onUnauthorized = useCallback(() => {
    const now = Date.now();
    if (firstStrikeAtRef.current === null) {
      // First 401 in a streak — start the clock, don't act yet.
      firstStrikeAtRef.current = now;
      return;
    }
    if (now - firstStrikeAtRef.current >= REVOKE_CONFIRM_MS) {
      firstStrikeAtRef.current = null;
      onConfirmedRevoke();
    }
  }, [onConfirmedRevoke]);

  const noteAuthSuccess = useCallback(() => {
    firstStrikeAtRef.current = null;
  }, []);

  return { onUnauthorized, noteAuthSuccess };
}
