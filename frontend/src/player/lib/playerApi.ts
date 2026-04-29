// Phase 47: device-JWT fetch adapter. THIS IS THE ONE PERMITTED RAW fetch() CALLSITE
// in frontend/src/player/**. The CI guard (Plan 47-05 check-player-isolation.mjs) exempts this file.
// Documented exception per ROADMAP "v1.16 Cross-Cutting Hazards" #2:
//   "Phase 47 player uses its own minimal fetch with device-token bearer, documented exception."
//
// NOTE: project tsconfig runs `erasableSyntaxOnly`, which disallows TS
// parameter-properties (`constructor(public status: number)`). PlayerApiError
// uses explicit field declarations instead.

export class PlayerApiError extends Error {
  status: number;
  bodyText: string;
  url: string;
  constructor(status: number, bodyText: string, url: string) {
    super(`PlayerApi ${status} on ${url}: ${bodyText.slice(0, 200)}`);
    this.name = "PlayerApiError";
    this.status = status;
    this.bodyText = bodyText;
    this.url = url;
  }
}

export interface PlayerFetchOpts extends Omit<RequestInit, "headers"> {
  token: string;
  headers?: Record<string, string>;
  /** Called exactly once when the server returns 401 (device revoked). */
  on401?: () => void;
}

export async function playerFetch<T>(url: string, opts: PlayerFetchOpts): Promise<T> {
  const { token, on401, headers, ...rest } = opts;
  const r = await fetch(url, {
    ...rest,
    cache: "no-store", // Phase 47 D-8 closeout — prevent browser HTTP cache from serving stale responses
    headers: {
      Accept: "application/json",
      ...headers,
      Authorization: `Bearer ${token}`,
    },
  });
  if (r.status === 401) {
    on401?.();
    throw new PlayerApiError(401, await r.text().catch(() => ""), url);
  }
  if (!r.ok) {
    const body = await r.text().catch(() => "");
    throw new PlayerApiError(r.status, body, url);
  }
  // 204 No Content path (heartbeat-shaped responses) — caller asks for void.
  if (r.status === 204) return undefined as T;
  return (await r.json()) as T;
}

// Phase 62 Plan 04 (CAL-PI-06): calibration shape + helper.
// Matches backend SignageCalibrationRead (plan 62-01). The player consumes the
// `audio_enabled` field to flip the HTMLMediaElement `muted` attribute (D-05).
export interface PlayerCalibration {
  rotation: 0 | 90 | 180 | 270;
  hdmi_mode: string | null;
  audio_enabled: boolean;
}

export function fetchCalibration(
  token: string,
  onUnauthorized?: () => void,
): Promise<PlayerCalibration> {
  return playerFetch<PlayerCalibration>("/api/signage/player/calibration", {
    token,
    on401: onUnauthorized,
  });
}

// Phase 48: push the device JWT to the Pi sidecar so it can make authenticated
// upstream requests and own the 60s heartbeat. Fire-and-forget: if the sidecar
// is not running, the 200ms timeout fails fast and the UX is unaffected.
const SIDECAR_TOKEN_URL = "http://localhost:8080/token";
export async function postSidecarToken(token: string): Promise<boolean> {
  try {
    const r = await fetch(SIDECAR_TOKEN_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ token }),
      signal: AbortSignal.timeout(200),
    });
    return r.ok;
  } catch {
    return false;
  }
}
