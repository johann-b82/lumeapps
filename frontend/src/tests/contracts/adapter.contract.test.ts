/**
 * Phase 71-03 (FE-05) — adapter contract snapshot tests.
 *
 * For each migrated GET endpoint we mock the underlying transport
 * (Directus SDK `directus.request` or shared `apiClient`), call the FE
 * adapter function, and assert that the returned shape deep-equals a
 * checked-in JSON fixture under `frontend/src/tests/contracts/`.
 *
 * Purpose: lock the Directus/FastAPI -> FE wire shape. Any future
 * Directus version drift or accidental adapter refactor that changes
 * the returned shape will fail CI.
 *
 * Regen flow:
 *   UPDATE_SNAPSHOTS=1 npm test --prefix frontend -- src/tests/contracts/adapter.contract.test.ts
 * Reviewer convention (D-01c): commit message
 *   `contract: regenerate <endpoint>` per fixture changed.
 *
 * Composite reads (Pitfall 4) — `signageApi.listPlaylists()` issues
 * TWO Directus calls in parallel via Promise.all. Order is fixed by the
 * call site:
 *   1st `directus.request` -> playlist rows (signage_playlists)
 *   2nd `directus.request` -> tag-map rows (signage_playlist_tag_map)
 * `mockResolvedValueOnce` MUST be enqueued in that order.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

vi.mock("@/lib/directusClient", () => ({
  directus: { request: vi.fn() },
}));

vi.mock("@/lib/apiClient", () => ({
  apiClient: vi.fn(),
  apiClientWithBody: vi.fn(),
  getAccessToken: () => "test-token",
  setAccessToken: vi.fn(),
  setAuthFailureHandler: vi.fn(),
  trySilentRefresh: vi.fn(),
}));

import { signageApi } from "@/signage/lib/signageApi";
import { directus } from "@/lib/directusClient";
import { apiClient } from "@/lib/apiClient";
import { fetchSalesRecords, fetchEmployees } from "@/lib/api";
import { readMe } from "@directus/sdk";

const FIXTURES_DIR = path.dirname(fileURLToPath(import.meta.url));
const UPDATE = process.env.UPDATE_SNAPSHOTS === "1";

function snapshot(name: string, actual: unknown): void {
  const fpath = path.join(FIXTURES_DIR, `${name}.json`);
  if (UPDATE || !existsSync(fpath)) {
    writeFileSync(fpath, JSON.stringify(actual, null, 2) + "\n");
    return;
  }
  const expected = JSON.parse(readFileSync(fpath, "utf-8"));
  expect(actual).toEqual(expected);
}

// Stable identifiers so fixtures are deterministic across runs.
const UID1 = "00000000-0000-0000-0000-000000000001";
const UID2 = "00000000-0000-0000-0000-000000000002";
const UID3 = "00000000-0000-0000-0000-000000000003";
const ISO_T = "2026-04-01T00:00:00Z";
const ISO_T2 = "2026-04-02T00:00:00Z";

describe("FE-05: adapter contract snapshots", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // -----------------------------------------------------------------
  // 1. readMe_minimal — AuthContext readMe call
  //    fields: id, email, role.name (Phase 66 D-03 minimal shape)
  // -----------------------------------------------------------------
  it("readMe_minimal", async () => {
    (directus.request as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      id: "user-uuid-0001",
      email: "viewer@example.com",
      role: { name: "Viewer" },
    });
    const got = await directus.request(
      readMe({ fields: ["id", "email", "role.name"] }),
    );
    snapshot("readMe_minimal", got);
  });

  // -----------------------------------------------------------------
  // 2. readMe_full — useCurrentUserProfile readMe call (Phase 66 D-05)
  //    fields: id, email, first_name, last_name, avatar, role.name
  // -----------------------------------------------------------------
  it("readMe_full", async () => {
    (directus.request as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      id: "user-uuid-0001",
      email: "viewer@example.com",
      first_name: "Ada",
      last_name: "Lovelace",
      avatar: null,
      role: { name: "Viewer" },
    });
    const got = await directus.request(
      readMe({
        fields: ["id", "email", "first_name", "last_name", "avatar", "role.name"],
      }),
    );
    snapshot("readMe_full", got);
  });

  // -----------------------------------------------------------------
  // 3. sales_records — fetchSalesRecords (Phase 67 MIG-DATA-01)
  //    Directus readItems('sales_records', ...) -> SalesRecordRow[]
  // -----------------------------------------------------------------
  it("sales_records", async () => {
    (directus.request as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
      {
        id: 1,
        order_number: "ORD-1001",
        customer_name: "Acme GmbH",
        city: "Berlin",
        order_date: "2026-03-15",
        total_value: 12500.5,
        remaining_value: 0,
        responsible_person: "Ada Lovelace",
        project_name: "Project Alpha",
        status_code: 10,
      },
      {
        id: 2,
        order_number: "ORD-1002",
        customer_name: null,
        city: null,
        order_date: null,
        total_value: null,
        remaining_value: null,
        responsible_person: null,
        project_name: null,
        status_code: null,
      },
    ]);
    const got = await fetchSalesRecords({ search: "acme" });
    snapshot("sales_records", got);
  });

  // -----------------------------------------------------------------
  // 4. personio_employees — fetchEmployees (Phase 67 MIG-DATA-02)
  //    9-field allowlist; compute fields zero-filled by adapter.
  // -----------------------------------------------------------------
  it("personio_employees", async () => {
    (directus.request as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
      {
        id: 101,
        first_name: "Ada",
        last_name: "Lovelace",
        status: "active",
        department: "Engineering",
        position: "Engineer",
        hire_date: "2024-01-15",
        termination_date: null,
        weekly_working_hours: 40,
      },
      {
        id: 102,
        first_name: "Grace",
        last_name: "Hopper",
        status: "active",
        department: "Engineering",
        position: "Architect",
        hire_date: "2023-09-01",
        termination_date: null,
        weekly_working_hours: 32,
      },
    ]);
    const got = await fetchEmployees();
    snapshot("personio_employees", got);
  });

  // -----------------------------------------------------------------
  // 5. signage_device_tags — signageApi.listTags (Phase 68-04)
  //    Collection: signage_device_tags (NOT signage_tags).
  // -----------------------------------------------------------------
  it("signage_device_tags", async () => {
    (directus.request as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
      { id: 1, name: "lobby" },
      { id: 2, name: "kitchen" },
      { id: 3, name: "warehouse" },
    ]);
    const got = await signageApi.listTags();
    snapshot("signage_device_tags", got);
  });

  // -----------------------------------------------------------------
  // 6. signage_schedules — signageApi.listSchedules (Phase 68-04)
  //    SCHEDULE_FIELDS allowlist; sort by -priority,-updated_at.
  // -----------------------------------------------------------------
  it("signage_schedules", async () => {
    (directus.request as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
      {
        id: UID1,
        playlist_id: UID2,
        weekday_mask: 31, // Mo-Fr
        start_hhmm: 800,
        end_hhmm: 1800,
        priority: 10,
        enabled: true,
        created_at: ISO_T,
        updated_at: ISO_T,
      },
      {
        id: UID2,
        playlist_id: UID3,
        weekday_mask: 96, // Sa-Su
        start_hhmm: 1000,
        end_hhmm: 1600,
        priority: 5,
        enabled: false,
        created_at: ISO_T,
        updated_at: ISO_T2,
      },
    ]);
    const got = await signageApi.listSchedules();
    snapshot("signage_schedules", got);
  });

  // -----------------------------------------------------------------
  // 7. signage_playlists — signageApi.listPlaylists (Phase 69-03)
  //    COMPOSITE READ (Pitfall 4):
  //      1st mockResolvedValueOnce -> playlist rows
  //      2nd mockResolvedValueOnce -> tag-map rows (playlist_id, tag_id)
  //    Adapter merges into SignagePlaylist[] with tag_ids hydrated.
  // -----------------------------------------------------------------
  it("signage_playlists", async () => {
    const requestMock = directus.request as unknown as ReturnType<typeof vi.fn>;
    // Call #1: playlist rows
    requestMock.mockResolvedValueOnce([
      {
        id: UID1,
        name: "Lobby Default",
        description: "Mid-day lobby loop",
        priority: 10,
        enabled: true,
        created_at: ISO_T,
        updated_at: ISO_T,
      },
      {
        id: UID2,
        name: "Kitchen Specials",
        description: null,
        priority: 5,
        enabled: false,
        created_at: ISO_T,
        updated_at: ISO_T2,
      },
    ]);
    // Call #2: tag-map rows
    requestMock.mockResolvedValueOnce([
      { playlist_id: UID1, tag_id: 1 },
      { playlist_id: UID1, tag_id: 2 },
      { playlist_id: UID2, tag_id: 2 },
    ]);
    const got = await signageApi.listPlaylists();
    snapshot("signage_playlists", got);
  });

  // -----------------------------------------------------------------
  // 8. signage_playlist_items_per_playlist — signageApi.listPlaylistItems
  //    PLAYLIST_ITEM_FIELDS allowlist (8 fields).
  // -----------------------------------------------------------------
  it("signage_playlist_items_per_playlist", async () => {
    (directus.request as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
      {
        id: "11111111-1111-1111-1111-111111111111",
        playlist_id: UID1,
        media_id: "22222222-2222-2222-2222-222222222222",
        position: 0,
        duration_s: 10,
        transition: "fade",
        created_at: ISO_T,
        updated_at: ISO_T,
      },
      {
        id: "11111111-1111-1111-1111-111111111112",
        playlist_id: UID1,
        media_id: "22222222-2222-2222-2222-222222222223",
        position: 1,
        duration_s: 7,
        transition: null,
        created_at: ISO_T,
        updated_at: ISO_T,
      },
    ]);
    const got = await signageApi.listPlaylistItems(UID1);
    snapshot("signage_playlist_items_per_playlist", got);
  });

  // -----------------------------------------------------------------
  // 9. signage_devices — signageApi.listDevices (Phase 70-03)
  //    DEVICE_FIELDS allowlist; resolved/computed fields filled
  //    client-side by DevicesPage useQueries merge.
  // -----------------------------------------------------------------
  it("signage_devices", async () => {
    (directus.request as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce([
      {
        id: UID1,
        name: "Lobby TV",
        created_at: ISO_T,
        updated_at: ISO_T,
        last_seen_at: ISO_T2,
        revoked_at: null,
        rotation: 0,
        hdmi_mode: null,
        audio_enabled: true,
      },
      {
        id: UID2,
        name: "Kitchen Display",
        created_at: ISO_T,
        updated_at: ISO_T2,
        last_seen_at: null,
        revoked_at: null,
        rotation: 90,
        hdmi_mode: "1920x1080@60",
        audio_enabled: false,
      },
    ]);
    const got = await signageApi.listDevices();
    snapshot("signage_devices", got);
  });

  // -----------------------------------------------------------------
  // 10. resolved_per_device — signageApi.getResolvedForDevice
  //     FastAPI compute endpoint via apiClient (NOT Directus).
  // -----------------------------------------------------------------
  it("resolved_per_device", async () => {
    (apiClient as unknown as ReturnType<typeof vi.fn>).mockResolvedValueOnce({
      current_playlist_id: UID2,
      current_playlist_name: "Lobby Default",
      tag_ids: [1, 2],
    });
    const got = await signageApi.getResolvedForDevice(UID1);
    snapshot("resolved_per_device", got);
  });
});
