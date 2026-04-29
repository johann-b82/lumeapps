import { apiClient, getAccessToken } from "@/lib/apiClient";
import { directus } from "@/lib/directusClient";
import { toApiError } from "@/lib/toApiError";
import {
  readItem,
  readItems,
  createItem,
  createItems,
  updateItem,
  deleteItem,
  deleteItems,
} from "@directus/sdk";
import type {
  SignageTag,
  SignageMedia,
  SignageDevice,
  SignagePlaylist,
  SignagePlaylistItem,
  SignageSchedule,
  SignageScheduleCreate,
  SignageScheduleUpdate,
  SignageDeviceAnalytics,
} from "./signageTypes";

/**
 * Error subclass that preserves both the HTTP status and the JSON response body
 * so callers can extract structured fields (e.g. `playlist_ids` from a 409 on
 * media delete). The shared `apiClient` discards the body and only surfaces
 * `body.detail` as `Error.message`, which is insufficient for the in-use UX.
 */
export class ApiErrorWithBody extends Error {
  status: number;
  body: unknown;
  constructor(status: number, body: unknown, message: string) {
    super(message);
    this.name = "ApiErrorWithBody";
    this.status = status;
    this.body = body;
  }
}

/**
 * Signage-specific apiClient variant that preserves the full JSON body on
 * error, needed for the 409 `playlist_ids` extraction on media delete
 * (Pitfall 6 in 46-RESEARCH.md). Honors the same bearer + credentials
 * contract as the shared apiClient; no `fetch()` elsewhere in signage
 * (CI grep guard added in 46-04).
 */
export async function apiClientWithBody<T>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(init?.headers);
  if (token) headers.set("Authorization", `Bearer ${token}`);
  if (init?.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const resp = await fetch(path, { ...init, headers, credentials: "include" });
  const contentType = resp.headers.get("content-type") ?? "";
  const body: unknown = contentType.includes("application/json")
    ? await resp.json().catch(() => null)
    : null;
  if (!resp.ok) {
    const detail =
      body && typeof body === "object" && "detail" in body
        ? String((body as { detail: unknown }).detail)
        : `HTTP ${resp.status}`;
    throw new ApiErrorWithBody(resp.status, body, detail);
  }
  return body as T;
}

// Phase 69-03 (D-01): mirrors SignagePlaylistItemRead 8 fields.
// Applied to every Directus playlist-items GET to keep payload shape stable.
const PLAYLIST_ITEM_FIELDS = [
  "id",
  "playlist_id",
  "media_id",
  "position",
  "duration_s",
  "transition",
  "created_at",
  "updated_at",
] as const;

// Phase 69-03: mirrors SignagePlaylistRead minus derived tag_ids
// (tag_ids is hydrated separately via signage_playlist_tag_map).
const PLAYLIST_FIELDS = [
  "id",
  "name",
  "description",
  "priority",
  "enabled",
  "created_at",
  "updated_at",
] as const;

// Phase 70-03: mirrors SignageDeviceRead minus computed fields
// (current_playlist_id, current_playlist_name, tag_ids are populated
// client-side via getResolvedForDevice — see DevicesPage useQueries merge).
// `status` is also computed server-side from heartbeat; it is filled by the
// resolved-merge layer or kept undefined for the row-only path.
const DEVICE_FIELDS = [
  "id",
  "name",
  "created_at",
  "updated_at",
  "last_seen_at",
  "revoked_at",
  "rotation",
  "hdmi_mode",
  "audio_enabled",
] as const;

// Phase v1.23 C-2: field allowlist mirroring SignageMediaRead
// (backend/app/schemas/signage.py SignageMediaBase + SignageMediaRead).
// Applied to every Directus signage_media GET to keep payload shape stable.
// `tags` and `metadata` are not column-backed and are intentionally omitted
// — SignageMedia in signageTypes.ts marks them optional for forward-compat.
const MEDIA_FIELDS = [
  "id",
  "kind",
  "title",
  "mime_type",
  "size_bytes",
  "uri",
  "duration_ms",
  "html_content",
  "conversion_status",
  "conversion_error",
  "slide_paths",
  "created_at",
  "updated_at",
] as const;

// Phase 68-04 (D-07): field allowlist mirroring SignageSchedule (signageTypes.ts)
// — applied to every Directus schedule request to keep payload shape stable.
const SCHEDULE_FIELDS = [
  "id",
  "playlist_id",
  "weekday_mask",
  "start_hhmm",
  "end_hhmm",
  "priority",
  "enabled",
  "created_at",
  "updated_at",
] as const;

// Typed GETs — reused by primitives + sub-pages. Use apiClient (not
// apiClientWithBody) for anything that does NOT need 409-body extraction.
//
// Phase 71-01 (FE-04, D-03): every adapter function wraps its Directus SDK
// or apiClient call in try { ... } catch (e) { throw toApiError(e); } to
// normalize Directus plain-object throws into ApiErrorWithBody. Public TYPE
// signatures are unchanged (still Promise<T>) — D-00e preserved.
export const signageApi = {
  // Phase 68-04 (D-04, D-07): Tag CRUD swapped from FastAPI to Directus SDK.
  // Collection name is `signage_device_tags` (verified directus/snapshots/v1.22.yaml),
  // NOT `signage_tags`. Public signatures unchanged (D-00g).
  listTags: async (): Promise<SignageTag[]> => {
    try {
      return (await directus.request(
        readItems("signage_device_tags", {
          fields: ["id", "name"],
          sort: ["id"],
          limit: -1,
        }),
      )) as SignageTag[];
    } catch (e) { throw toApiError(e); }
  },
  createTag: async (name: string): Promise<SignageTag> => {
    try {
      return (await directus.request(
        createItem("signage_device_tags", { name }, { fields: ["id", "name"] }),
      )) as SignageTag;
    } catch (e) { throw toApiError(e); }
  },
  updateTag: async (id: number, name: string): Promise<SignageTag> => {
    try {
      return (await directus.request(
        updateItem("signage_device_tags", id, { name }, { fields: ["id", "name"] }),
      )) as SignageTag;
    } catch (e) { throw toApiError(e); }
  },
  deleteTag: async (id: number): Promise<null> => {
    try {
      return (await directus.request(
        deleteItem("signage_device_tags", id),
      )) as null;
    } catch (e) { throw toApiError(e); }
  },
  // Phase v1.23 C-2 (D-07): media list swapped from FastAPI to Directus SDK.
  // Sort by created_at to match the prior FastAPI ordering. Admin-only:
  // Viewer hits FORBIDDEN at the Directus permission layer (no row for
  // signage_media on the Viewer policy — AUTHZ-02 convention).
  listMedia: async (): Promise<SignageMedia[]> => {
    try {
      return (await directus.request(
        readItems("signage_media", {
          fields: [...MEDIA_FIELDS],
          sort: ["created_at"],
          limit: -1,
        }),
      )) as SignageMedia[];
    } catch (e) { throw toApiError(e); }
  },
  // Phase v1.23 C-3 (D-07): per-row media read swapped from FastAPI to
  // Directus SDK (`readItem`). Same admin-only permission model as listMedia
  // (Viewer FORBIDDEN at the Directus layer). Field allowlist mirrors
  // SignageMediaRead so the polled MediaStatusPill keeps surfacing
  // conversion_status / conversion_error.
  getMedia: async (id: string): Promise<SignageMedia> => {
    try {
      return (await directus.request(
        readItem("signage_media", id, { fields: [...MEDIA_FIELDS] }),
      )) as SignageMedia;
    } catch (e) { throw toApiError(e); }
  },
  deleteMedia: async (id: string): Promise<null> => {
    try {
      return await apiClientWithBody<null>(`/api/signage/media/${id}`, {
        method: "DELETE",
      });
    } catch (e) { throw toApiError(e); }
  },
  // Phase 69-03 (D-07, D-00g, D-01): playlist metadata + items GET swapped from
  // FastAPI to Directus SDK. Public signatures unchanged so consumers
  // (PlaylistsPage, PlaylistEditorPage, PlaylistEditDialog) continue to receive
  // SignagePlaylist[] / SignagePlaylist with `tag_ids` populated. tag_ids is
  // hydrated by a parallel readItems('signage_playlist_tag_map', ...) call
  // (Option A: preserve consumer contract — PlaylistEditorPage reads
  // data.playlist.tag_ids unconditionally).
  //
  // Surviving FastAPI surface (D-00 architectural lock):
  //   - deletePlaylist: keeps apiClientWithBody to preserve the 409
  //     `{detail, schedule_ids}` shape consumed by PlaylistDeleteDialog.
  //   - bulkReplaceItems: keeps apiClient PUT for atomic DELETE+INSERT.
  //
  // Phase 71-01: composite reads wrap the OUTER awaited expression in one
  // try/catch so the first thrower normalizes the whole call.
  listPlaylists: async (): Promise<SignagePlaylist[]> => {
    try {
      const [rows, map] = await Promise.all([
        directus.request(
          readItems("signage_playlists", {
            fields: [...PLAYLIST_FIELDS],
            sort: ["name"],
            limit: -1,
          }),
        ) as Promise<Omit<SignagePlaylist, "tag_ids" | "tags">[]>,
        directus.request(
          readItems("signage_playlist_tag_map", {
            fields: ["playlist_id", "tag_id"],
            limit: -1,
          }),
        ) as Promise<{ playlist_id: string; tag_id: number }[]>,
      ]);
      const byPid = new Map<string, number[]>();
      for (const m of map) {
        const arr = byPid.get(m.playlist_id) ?? [];
        arr.push(m.tag_id);
        byPid.set(m.playlist_id, arr);
      }
      return rows.map(
        (r) => ({ ...r, tag_ids: byPid.get(r.id) ?? [] }) as SignagePlaylist,
      );
    } catch (e) { throw toApiError(e); }
  },
  getPlaylist: async (id: string): Promise<SignagePlaylist> => {
    try {
      const [row, tagRows] = await Promise.all([
        directus.request(
          readItems("signage_playlists", {
            filter: { id: { _eq: id } },
            fields: [...PLAYLIST_FIELDS],
            limit: 1,
          }),
        ) as Promise<Omit<SignagePlaylist, "tag_ids" | "tags">[]>,
        directus.request(
          readItems("signage_playlist_tag_map", {
            filter: { playlist_id: { _eq: id } },
            fields: ["tag_id"],
            limit: -1,
          }),
        ) as Promise<{ tag_id: number }[]>,
      ]);
      if (!row.length) throw new Error(`Playlist ${id} not found`);
      return {
        ...row[0],
        tag_ids: tagRows.map((t) => t.tag_id),
      } as SignagePlaylist;
    } catch (e) { throw toApiError(e); }
  },
  createPlaylist: async (body: {
    name: string;
    description?: string | null;
    priority?: number;
    enabled?: boolean;
  }): Promise<SignagePlaylist> => {
    try {
      return (await directus.request(
        createItem("signage_playlists", body, { fields: [...PLAYLIST_FIELDS] }),
      )) as SignagePlaylist;
    } catch (e) { throw toApiError(e); }
  },
  updatePlaylist: async (
    id: string,
    body: {
      name?: string;
      description?: string | null;
      priority?: number;
      enabled?: boolean;
    },
  ): Promise<SignagePlaylist> => {
    try {
      return (await directus.request(
        updateItem("signage_playlists", id, body, {
          fields: [...PLAYLIST_FIELDS],
        }),
      )) as SignagePlaylist;
    } catch (e) { throw toApiError(e); }
  },
  // Phase 52 D-13: uses apiClientWithBody so callers can read the 409
  // response body { detail, schedule_ids } when a playlist is blocked by
  // active schedules (FK RESTRICT from signage_schedules.playlist_id).
  // PRESERVED: D-00 architectural lock — DELETE stays in FastAPI.
  // Phase 71-01: toApiError is a pass-through for ApiErrorWithBody already
  // thrown by apiClientWithBody, so wrapping is safe + idempotent.
  deletePlaylist: async (id: string): Promise<null> => {
    try {
      return await apiClientWithBody<null>(`/api/signage/playlists/${id}`, {
        method: "DELETE",
      });
    } catch (e) { throw toApiError(e); }
  },
  // Phase 69-03 (D-02): FE-driven diff against signage_playlist_tag_map.
  // Read existing rows, compute toAdd/toRemove sets, fire concurrent
  // deleteItems + createItems via Promise.all (D-02a). signage_playlist_tag_map
  // has a composite PK (playlist_id, tag_id) — no surrogate `id` column —
  // so deleteItems uses the query/filter form (verified deleteItems signature
  // accepts `string[] | number[] | TQuery` in @directus/sdk@21.2.2).
  // Each map-row mutation fires a `playlist-changed` SSE via the Phase 65
  // trigger; FE deduplicates downstream (no consumer change needed — D-02b).
  // Return shape unchanged (D-00g): `{ tag_ids: number[] }` — the new desired set.
  replacePlaylistTags: async (
    id: string,
    tag_ids: number[],
  ): Promise<{ tag_ids: number[] }> => {
    try {
      const existing = (await directus.request(
        readItems("signage_playlist_tag_map", {
          filter: { playlist_id: { _eq: id } },
          fields: ["tag_id"],
          limit: -1,
        }),
      )) as { tag_id: number }[];
      const existingTagIds = new Set(existing.map((r) => r.tag_id));
      const desiredTagIds = new Set(tag_ids);
      const toAdd = [...desiredTagIds].filter((t) => !existingTagIds.has(t));
      const toRemove = [...existingTagIds].filter((t) => !desiredTagIds.has(t));
      await Promise.all([
        toRemove.length > 0
          ? directus.request(
              deleteItems("signage_playlist_tag_map", {
                filter: {
                  _and: [
                    { playlist_id: { _eq: id } },
                    { tag_id: { _in: toRemove } },
                  ],
                },
              }),
            )
          : Promise.resolve(),
        toAdd.length > 0
          ? directus.request(
              createItems(
                "signage_playlist_tag_map",
                toAdd.map((tagId) => ({ playlist_id: id, tag_id: tagId })),
              ),
            )
          : Promise.resolve(),
      ]);
      return { tag_ids } as { tag_ids: number[] };
    } catch (e) { throw toApiError(e); }
  },
  listPlaylistItems: async (id: string): Promise<SignagePlaylistItem[]> => {
    try {
      return (await directus.request(
        readItems("signage_playlist_items", {
          filter: { playlist_id: { _eq: id } },
          fields: [...PLAYLIST_ITEM_FIELDS],
          sort: ["position"],
          limit: -1,
        }),
      )) as SignagePlaylistItem[];
    } catch (e) { throw toApiError(e); }
  },
  bulkReplaceItems: async (
    id: string,
    items: Array<{
      media_id: string;
      position: number;
      duration_s: number;
      transition: string | null;
    }>,
  ): Promise<SignagePlaylistItem[]> => {
    try {
      return await apiClient<SignagePlaylistItem[]>(
        `/api/signage/playlists/${id}/items`,
        { method: "PUT", body: JSON.stringify({ items }) },
      );
    } catch (e) { throw toApiError(e); }
  },
  // Phase 70-03 (D-00g, D-04): listDevices reads from Directus signage_devices.
  // current_playlist_id / current_playlist_name / tag_ids are populated
  // client-side by DevicesPage's useQueries merge against
  // getResolvedForDevice — they are computed fields with no Directus column
  // (D-04 / D-04a — no rename to resolved_*).
  listDevices: async (): Promise<SignageDevice[]> => {
    try {
      return (await directus.request(
        readItems("signage_devices", {
          fields: [...DEVICE_FIELDS],
          sort: ["created_at"],
          limit: -1,
        }),
      )) as SignageDevice[];
    } catch (e) { throw toApiError(e); }
  },
  // Phase 70-03: per-device row read (matches old GET /api/signage/devices/{id}).
  getDevice: async (id: string): Promise<SignageDevice> => {
    try {
      const rows = (await directus.request(
        readItems("signage_devices", {
          filter: { id: { _eq: id } },
          fields: [...DEVICE_FIELDS],
          limit: 1,
        }),
      )) as SignageDevice[];
      if (!rows.length) throw new Error(`Device ${id} not found`);
      return rows[0];
    } catch (e) { throw toApiError(e); }
  },
  // Phase 70-03 (D-01, D-02): per-device resolved playlist + tag_ids from
  // FastAPI compute endpoint. Used by DevicesPage useQueries to merge with
  // Directus row data; field names align with SignageDevice extras so the
  // merge is `{...row, ...resolved}` with zero rename.
  getResolvedForDevice: async (
    id: string,
  ): Promise<{
    current_playlist_id: string | null;
    current_playlist_name: string | null;
    tag_ids: number[] | null;
  }> => {
    try {
      return await apiClient<{
        current_playlist_id: string | null;
        current_playlist_name: string | null;
        tag_ids: number[] | null;
      }>(`/api/signage/resolved/${id}`);
    } catch (e) { throw toApiError(e); }
  },
  // Phase 53 SGN-ANA-01 — Analytics-lite. Separate query from listDevices
  // so the two data streams can poll/invalidate independently (D-11).
  // Backend: backend/app/routers/signage_admin/analytics.py
  listDeviceAnalytics: async (): Promise<SignageDeviceAnalytics[]> => {
    try {
      return await apiClient<SignageDeviceAnalytics[]>(
        "/api/signage/analytics/devices",
      );
    } catch (e) { throw toApiError(e); }
  },
  // Phase 70-03 (D-00g): updateDevice's name PATCH swaps to Directus
  // updateItem. Public signature unchanged: still accepts {name, tag_ids}
  // for ergonomic call sites (DeviceEditDialog), but only forwards `name`
  // here — the caller sequences this with replaceDeviceTags(id, tag_ids)
  // (research Open Question 2: keep PATCH-then-PUT sequenced).
  updateDevice: async (
    id: string,
    body: { name?: string; tag_ids?: number[] },
  ): Promise<SignageDevice> => {
    try {
      return (await directus.request(
        updateItem(
          "signage_devices",
          id,
          { name: body.name },
          { fields: [...DEVICE_FIELDS] },
        ),
      )) as SignageDevice;
    } catch (e) { throw toApiError(e); }
  },
  // Phase 70-03 (D-03, D-03d): FE-driven diff against signage_device_tag_map.
  // IDENTICAL shape to replacePlaylistTags so Phase 71 FE-01 can extract a
  // shared replaceTagMap util mechanically. Composite PK (device_id, tag_id)
  // — deleteItems uses the query/filter form (Pitfall 5).
  // SSE: each map-row insert/delete fires `device-changed` per Phase 65
  // listener mapping (signage_pg_listen.py:86-88 — NOT playlist-changed,
  // research Pitfall 1 corrects CONTEXT D-03b). Multi-event tolerance
  // (D-03b — assert at-least-once, not exactly-once).
  replaceDeviceTags: async (
    id: string,
    tag_ids: number[],
  ): Promise<{ tag_ids: number[] }> => {
    try {
      const existing = (await directus.request(
        readItems("signage_device_tag_map", {
          filter: { device_id: { _eq: id } },
          fields: ["tag_id"],
          limit: -1,
        }),
      )) as { tag_id: number }[];
      const existingTagIds = new Set(existing.map((r) => r.tag_id));
      const desiredTagIds = new Set(tag_ids);
      const toAdd = [...desiredTagIds].filter((t) => !existingTagIds.has(t));
      const toRemove = [...existingTagIds].filter((t) => !desiredTagIds.has(t));
      await Promise.all([
        toRemove.length > 0
          ? directus.request(
              deleteItems("signage_device_tag_map", {
                filter: {
                  _and: [
                    { device_id: { _eq: id } },
                    { tag_id: { _in: toRemove } },
                  ],
                },
              }),
            )
          : Promise.resolve(),
        toAdd.length > 0
          ? directus.request(
              createItems(
                "signage_device_tag_map",
                toAdd.map((tagId) => ({ device_id: id, tag_id: tagId })),
              ),
            )
          : Promise.resolve(),
      ]);
      return { tag_ids } as { tag_ids: number[] };
    } catch (e) { throw toApiError(e); }
  },
  // Phase 70-03: Directus DELETE on signage_devices. Currently no UI
  // consumer (the visible "Revoke" CTA flips revoked_at via the pair
  // router — see revokeDevice below). Provided for parity with the
  // migrated route surface and for any future hard-delete UI.
  deleteDevice: async (id: string): Promise<null> => {
    try {
      return (await directus.request(
        deleteItem("signage_devices", id),
      )) as null;
    } catch (e) { throw toApiError(e); }
  },
  // Phase 62 — CAL-UI-03. PATCH /api/signage/devices/{id}/calibration. Body is
  // partial; backend applies only provided fields (exclude_unset=True) and
  // emits a `calibration-changed` SSE event. Returns the updated device so the
  // admin UI can reconcile without a second GET (backend returns
  // SignageDeviceRead with resolved playlist + tags). 422 on invalid rotation.
  updateDeviceCalibration: async (
    id: string,
    body: Partial<{
      rotation: 0 | 90 | 180 | 270;
      hdmi_mode: string | null;
      audio_enabled: boolean;
    }>,
  ): Promise<SignageDevice> => {
    try {
      return await apiClient<SignageDevice>(
        `/api/signage/devices/${id}/calibration`,
        {
          method: "PATCH",
          body: JSON.stringify(body),
        },
      );
    } catch (e) { throw toApiError(e); }
  },
  // Revoke lives on the pair router per backend/app/routers/signage_pair.py
  // (`POST /api/signage/pair/devices/{device_id}/revoke`).
  revokeDevice: async (id: string): Promise<null> => {
    try {
      return await apiClient<null>(
        `/api/signage/pair/devices/${id}/revoke`,
        { method: "POST" },
      );
    } catch (e) { throw toApiError(e); }
  },
  claimPairingCode: async (body: {
    code: string;
    device_name: string;
    tag_ids: number[] | null;
  }): Promise<null> => {
    try {
      return await apiClient<null>("/api/signage/pair/claim", {
        method: "POST",
        body: JSON.stringify(body),
      });
    } catch (e) { throw toApiError(e); }
  },
  // Phase 68-04 (D-07): Schedule CRUD swapped from FastAPI to Directus SDK.
  // Sort matches FastAPI's prior contract (priority desc, updated_at desc).
  // Inverted-range writes surface as DirectusError carrying the validation
  // hook's i18n key (Plan 02). Public signatures unchanged (D-00g).
  listSchedules: async (): Promise<SignageSchedule[]> => {
    try {
      return (await directus.request(
        readItems("signage_schedules", {
          fields: [...SCHEDULE_FIELDS],
          sort: ["-priority", "-updated_at"],
          limit: -1,
        }),
      )) as SignageSchedule[];
    } catch (e) { throw toApiError(e); }
  },
  createSchedule: async (
    body: SignageScheduleCreate,
  ): Promise<SignageSchedule> => {
    try {
      return (await directus.request(
        createItem("signage_schedules", body, { fields: [...SCHEDULE_FIELDS] }),
      )) as SignageSchedule;
    } catch (e) { throw toApiError(e); }
  },
  updateSchedule: async (
    id: string,
    body: SignageScheduleUpdate,
  ): Promise<SignageSchedule> => {
    try {
      return (await directus.request(
        updateItem("signage_schedules", id, body, {
          fields: [...SCHEDULE_FIELDS],
        }),
      )) as SignageSchedule;
    } catch (e) { throw toApiError(e); }
  },
  deleteSchedule: async (id: string): Promise<null> => {
    try {
      return (await directus.request(
        deleteItem("signage_schedules", id),
      )) as null;
    } catch (e) { throw toApiError(e); }
  },
};
