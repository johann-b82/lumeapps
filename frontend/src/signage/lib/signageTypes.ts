// Signage admin TypeScript types — narrow mirrors of backend Pydantic schemas.
// Only fields consumed by the admin UI are modeled here.

export type SignageMediaKind =
  | "image"
  | "video"
  | "pdf"
  | "pptx"
  | "url"
  | "html";

export type SignageConversionStatus =
  | "pending"
  | "processing"
  | "done"
  | "failed";

export interface SignageTag {
  id: number;
  name: string;
}

export interface SignageMedia {
  id: string; // uuid as string over JSON
  kind: SignageMediaKind;
  title: string;
  // Backend Read shape returns `uri` (Directus asset UUID for image/video/pdf,
  // or a URL for kind=url). For images/videos, build thumbnail via
  // `${DIRECTUS_URL}/assets/${uri}`. For `url` kind, `uri` is the full URL.
  uri: string | null;
  html_content: string | null;
  mime_type: string | null;
  size_bytes: number | null;
  duration_ms: number | null;
  // `tags` and `metadata` are not in the current Read shape; kept optional
  // for forward-compat with future enhancement.
  tags?: SignageTag[];
  metadata?: Record<string, unknown> | null;
  conversion_status: SignageConversionStatus | null;
  conversion_error: string | null;
  slide_paths: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface SignageDevice {
  id: string;
  name: string;
  status: "pending" | "online" | "offline";
  last_seen_at: string | null; // ISO-8601 or null
  revoked_at: string | null;
  // DEFECT-12: backend currently returns only tag_ids on list/detail; `tags`
  // is populated on a future enhancement. Keep optional until then.
  tags?: SignageTag[];
  tag_ids?: number[] | null;
  current_playlist_id: string | null;
  current_playlist_name?: string | null; // optional; filled by admin list endpoint if present
  // Phase 62 — calibration (CAL-BE-02 backend shape; admin GET includes these).
  // `rotation` is the labwc wlr-randr transform. `hdmi_mode` NULL means
  // "use current" (D-02/D-07 — sidecar makes no wlr-randr --mode call).
  // `available_modes` is reported via heartbeat by sidecar (D-02) — until
  // that lands it is undefined/null and the admin dropdown shows only the
  // Auto placeholder (CAL-UI-02).
  rotation: 0 | 90 | 180 | 270;
  hdmi_mode: string | null;
  audio_enabled: boolean;
  available_modes?: string[] | null;
  created_at: string;
  updated_at: string;
}

export interface SignagePlaylist {
  id: string;
  name: string;
  description: string | null;
  enabled: boolean;
  priority: number;
  // Backend SignagePlaylistRead does not currently embed tag objects on
  // the list/detail responses; `tag_ids` may be present (number[]) or null
  // depending on the route. `tags` is reserved for a future enhancement.
  tag_ids: number[] | null;
  tags?: SignageTag[];
  created_at: string;
  updated_at: string;
}

export interface SignagePlaylistItem {
  id?: string; // optional client-side for drag keys
  media_id: string;
  position: number;
  duration_s: number;
  transition: string | null; // "fade" | "cut" | null
}

// 409 response shape from DELETE /api/signage/media/{id} when RESTRICT fires.
export interface MediaInUseError {
  detail: string;
  playlist_ids: string[];
}

/**
 * Phase 52 SGN-SCHED-UI-01 — mirrors backend ScheduleRead
 * (backend/app/schemas/signage.py). weekday_mask bit0=Mo..bit6=So (D-05).
 * start_hhmm/end_hhmm are integers 0..2359 in HHMM form
 * (e.g. 730 = 07:30, 1430 = 14:30). Adapter to/from "HH:MM" lives in
 * the editor dialog (Plan 02).
 */
export interface SignageSchedule {
  id: string;            // uuid
  playlist_id: string;   // uuid
  weekday_mask: number;  // 0..127, bit0=Mo..bit6=So
  start_hhmm: number;    // 0..2359
  end_hhmm: number;      // 0..2359
  priority: number;
  enabled: boolean;
  created_at: string;    // ISO8601
  updated_at: string;    // ISO8601
}

export interface SignageScheduleCreate {
  playlist_id: string;
  weekday_mask: number;
  start_hhmm: number;
  end_hhmm: number;
  priority?: number;
  enabled?: boolean;
}

export interface SignageScheduleUpdate {
  playlist_id?: string;
  weekday_mask?: number;
  start_hhmm?: number;
  end_hhmm?: number;
  priority?: number;
  enabled?: boolean;
}

/**
 * Phase 53 SGN-ANA-01 — mirrors backend DeviceAnalyticsRead.
 * uptime_24h_pct is null when the server's denominator is 0 (zero
 * heartbeats retained). missed_windows_24h is 0 in that case.
 * window_minutes ∈ [0, 1440] — when < 1440 the frontend shows
 * the "_partial" tooltip variant with windowH = Math.ceil(window_minutes/60).
 */
export interface SignageDeviceAnalytics {
  device_id: string;
  uptime_24h_pct: number | null;
  missed_windows_24h: number;
  window_minutes: number;
}
