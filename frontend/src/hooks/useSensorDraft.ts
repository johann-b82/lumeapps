import { useCallback, useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  createSensor,
  deleteSensor,
  fetchSensors,
  updateSensor,
  updateSettings,
  type SensorCreatePayload,
  type SensorRead,
  type SensorUpdatePayload,
  type Settings,
  type SettingsUpdatePayload,
} from "@/lib/api";
import { useSettings } from "@/hooks/useSettings";
import { sensorKeys } from "@/lib/queryKeys";

// ---------------------------------------------------------------------------
// Draft row / globals shapes (Phase 40-01)
// ---------------------------------------------------------------------------

export interface SensorDraftRow {
  /** Local row identity — never sent to server. React key + unsaved-row tag. */
  _localId: string;
  /** Server id — null until first save. null = new (POST); present = existing (PATCH). */
  id: number | null;
  name: string;
  host: string;
  port: number;
  /** Write-only. Blank = "don't change" on PATCH; REQUIRED non-empty on POST. */
  community: string;
  /** true once the user types into community — distinguishes "kept" vs "set new". */
  communityDirty: boolean;
  /** "" in draft = null server-side. */
  temperature_oid: string;
  humidity_oid: string;
  temperature_scale: string;
  humidity_scale: string;
  enabled: boolean;
  /** v1.39: optional `#rrggbb` chart color. "" in draft = NULL server-side. */
  chart_color: string;
  /**
   * On existing rows loaded from server, tracks whether the server has a
   * stored community. Frontend uses this to show the "saved — leave blank
   * to keep" placeholder hint. Always false on new (id===null) rows.
   */
  hasStoredCommunity: boolean;
  /**
   * Local-only removal flag. On save: if id != null → DELETE /api/sensors/{id};
   * if id === null → dropped silently (never existed on server).
   */
  _markedForDelete: boolean;
}

export interface SensorDraftGlobals {
  sensor_poll_interval_s: number;
  /** "" in draft = "don't change" (per backend None-means-don't-change rule). */
  sensor_temperature_min: string;
  sensor_temperature_max: string;
  sensor_humidity_min: string;
  sensor_humidity_max: string;
}

export interface UseSensorDraftReturn {
  isLoading: boolean;
  isError: boolean;
  rows: SensorDraftRow[] | null;
  globals: SensorDraftGlobals | null;
  snapshot: { rows: SensorDraftRow[]; globals: SensorDraftGlobals } | null;
  isDirty: boolean;
  isSaving: boolean;
  addRow: () => void;
  updateRow: (_localId: string, patch: Partial<SensorDraftRow>) => void;
  markRowDeleted: (_localId: string) => void;
  setGlobal: <K extends keyof SensorDraftGlobals>(
    key: K,
    value: SensorDraftGlobals[K],
  ) => void;
  save: () => Promise<void>;
  discard: () => void;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeLocalId(): string {
  // crypto.randomUUID exists in all modern browsers + Node 20+ (Vitest).
  // Fallback to Math.random for the rare environments without it.
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `local-${Math.random().toString(36).slice(2)}-${Date.now()}`;
}

function serverSensorToRow(s: SensorRead): SensorDraftRow {
  return {
    _localId: `srv-${s.id}`,
    id: s.id,
    name: s.name,
    host: s.host,
    port: s.port,
    community: "",
    communityDirty: false,
    temperature_oid: s.temperature_oid ?? "",
    humidity_oid: s.humidity_oid ?? "",
    temperature_scale: s.temperature_scale,
    humidity_scale: s.humidity_scale,
    enabled: s.enabled,
    chart_color: s.chart_color ?? "",
    // Backend never echoes community but every persisted sensor_config row
    // has an encrypted community (required on create). Treat any server
    // row as "has a stored community".
    hasStoredCommunity: true,
    _markedForDelete: false,
  };
}

function settingsToGlobals(s: Settings): SensorDraftGlobals {
  return {
    sensor_poll_interval_s: s.sensor_poll_interval_s,
    // Draft uses "" for "don't change" / unset. Preserve server values as
    // initial draft content so admin sees what's currently stored.
    sensor_temperature_min: s.sensor_temperature_min ?? "",
    sensor_temperature_max: s.sensor_temperature_max ?? "",
    sensor_humidity_min: s.sensor_humidity_min ?? "",
    sensor_humidity_max: s.sensor_humidity_max ?? "",
  };
}

function rowsEqual(a: SensorDraftRow, b: SensorDraftRow): boolean {
  return (
    a.id === b.id &&
    a.name === b.name &&
    a.host === b.host &&
    a.port === b.port &&
    a.communityDirty === b.communityDirty &&
    (a.communityDirty ? a.community === b.community : true) &&
    a.temperature_oid === b.temperature_oid &&
    a.humidity_oid === b.humidity_oid &&
    a.temperature_scale === b.temperature_scale &&
    a.humidity_scale === b.humidity_scale &&
    a.enabled === b.enabled &&
    a.chart_color === b.chart_color &&
    a._markedForDelete === b._markedForDelete
  );
}

function globalsEqual(a: SensorDraftGlobals, b: SensorDraftGlobals): boolean {
  return (
    a.sensor_poll_interval_s === b.sensor_poll_interval_s &&
    a.sensor_temperature_min === b.sensor_temperature_min &&
    a.sensor_temperature_max === b.sensor_temperature_max &&
    a.sensor_humidity_min === b.sensor_humidity_min &&
    a.sensor_humidity_max === b.sensor_humidity_max
  );
}

/**
 * Builds the PATCH body for an existing row.
 * CRITICAL: community is OMITTED when communityDirty === false — the server
 * treats None as "keep stored ciphertext". Only dirty fields are included.
 */
export function buildSensorUpdatePayload(
  row: SensorDraftRow,
  snapshotRow: SensorDraftRow,
): SensorUpdatePayload {
  const body: SensorUpdatePayload = {};
  if (row.name !== snapshotRow.name) body.name = row.name;
  if (row.host !== snapshotRow.host) body.host = row.host;
  if (row.port !== snapshotRow.port) body.port = row.port;
  if (row.communityDirty && row.community !== "") body.community = row.community;
  if (row.temperature_oid !== snapshotRow.temperature_oid) {
    body.temperature_oid = row.temperature_oid === "" ? null : row.temperature_oid;
  }
  if (row.humidity_oid !== snapshotRow.humidity_oid) {
    body.humidity_oid = row.humidity_oid === "" ? null : row.humidity_oid;
  }
  if (row.temperature_scale !== snapshotRow.temperature_scale) {
    body.temperature_scale = row.temperature_scale;
  }
  if (row.humidity_scale !== snapshotRow.humidity_scale) {
    body.humidity_scale = row.humidity_scale;
  }
  if (row.enabled !== snapshotRow.enabled) body.enabled = row.enabled;
  if (row.chart_color !== snapshotRow.chart_color) {
    body.chart_color = row.chart_color === "" ? null : row.chart_color;
  }
  return body;
}

function buildSensorCreatePayload(row: SensorDraftRow): SensorCreatePayload {
  return {
    name: row.name,
    host: row.host,
    port: row.port,
    community: row.community,
    temperature_oid: row.temperature_oid === "" ? null : row.temperature_oid,
    humidity_oid: row.humidity_oid === "" ? null : row.humidity_oid,
    temperature_scale: row.temperature_scale,
    humidity_scale: row.humidity_scale,
    enabled: row.enabled,
    chart_color: row.chart_color === "" ? null : row.chart_color,
  };
}

function buildGlobalsPayload(
  globals: SensorDraftGlobals,
  snapshot: SensorDraftGlobals,
): Partial<SettingsUpdatePayload> | null {
  // Include ONLY changed fields. Empty-string thresholds = "don't change"
  // (carry-forward limitation documented in the plan).
  const payload: Partial<SettingsUpdatePayload> = {};
  let any = false;
  if (globals.sensor_poll_interval_s !== snapshot.sensor_poll_interval_s) {
    payload.sensor_poll_interval_s = globals.sensor_poll_interval_s;
    any = true;
  }
  const thresholds: (keyof SensorDraftGlobals)[] = [
    "sensor_temperature_min",
    "sensor_temperature_max",
    "sensor_humidity_min",
    "sensor_humidity_max",
  ];
  for (const key of thresholds) {
    if (globals[key] !== snapshot[key] && globals[key] !== "") {
      // Decimals on the wire as strings (see api.ts SettingsUpdatePayload).
      (payload as Record<string, unknown>)[key] = globals[key];
      any = true;
    }
  }
  if (!any) return null;
  // PUT /api/settings requires the full brand block. Caller merges with
  // current Settings cache when building the final payload.
  return payload;
}

// Exported for unit testing validate().
export class SensorDraftValidationError extends Error {
  // Phase 61: parameter-property shorthand is forbidden under
  // erasableSyntaxOnly (TS1294). Explicit field + assignment preserves the
  // public readonly `key` surface without emitting non-erasable syntax.
  readonly key: string;
  constructor(key: string) {
    // Error.message is the i18n key — toast callers route via t(err.message).
    super(key);
    this.key = key;
    this.name = "SensorDraftValidationError";
  }
}

export function validateSensorDraft(
  rows: SensorDraftRow[],
  globals: SensorDraftGlobals,
): void {
  const live = rows.filter((r) => !r._markedForDelete);
  const names = new Set<string>();
  for (const r of live) {
    if (!r.name.trim()) {
      throw new SensorDraftValidationError("sensors.admin.validation.name_required");
    }
    if (!r.host.trim()) {
      throw new SensorDraftValidationError("sensors.admin.validation.host_required");
    }
    if (names.has(r.name)) {
      throw new SensorDraftValidationError("sensors.admin.validation.name_duplicate");
    }
    names.add(r.name);
    const ts = Number(r.temperature_scale);
    const hs = Number(r.humidity_scale);
    if (!(ts > 0) || !(hs > 0)) {
      throw new SensorDraftValidationError("sensors.admin.validation.positive_number");
    }
    // v1.27: SNMP community is optional. Some devices accept unauthenticated
    // SNMPv2c reads; the empty string passes through to pysnmp which sends
    // an empty community in the GET PDU. Validation here used to require a
    // non-empty community on new sensors, but that prevented configuring
    // those devices at all. The "Test connection" button still surfaces a
    // real auth-failure response if the device DOES require a community.
  }
  if (
    globals.sensor_poll_interval_s < 5 ||
    globals.sensor_poll_interval_s > 86400
  ) {
    throw new SensorDraftValidationError(
      "sensors.admin.poll_interval.out_of_bounds",
    );
  }
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Phase 40-01 admin-only draft for /settings/sensors.
 *
 * Multi-row editing semantics: snapshot captured once on first successful
 * load; save() walks rows, issuing deleteSensor / createSensor / updateSensor
 * in deterministic order, then a single PUT /api/settings for changed globals.
 *
 * Non-transactional across rows by design — if a mid-stream request fails,
 * already-committed rows stay committed. The draft re-snapshots from the
 * fresh list on the next refetch so the user sees the current server state
 * and can retry only the failed row. Phase 41 could add /api/sensors/bulk
 * if operators request atomicity.
 */
export function useSensorDraft(): UseSensorDraftReturn {
  const queryClient = useQueryClient();
  const { data: settingsData } = useSettings();

  // Separate cache key from the /sensors dashboard's ['sensors', 'list']:
  // the dashboard auto-refetches every 15s; the admin form does not want
  // the draft blown away by a background refresh. Keep read-fresh here.
  const sensorsQuery = useQuery<SensorRead[]>({
    queryKey: ["sensors", "admin"],
    queryFn: fetchSensors,
    staleTime: Infinity,
    gcTime: Infinity,
    retry: 1,
  });

  const [snapshot, setSnapshot] = useState<
    { rows: SensorDraftRow[]; globals: SensorDraftGlobals } | null
  >(null);
  const [rows, setRows] = useState<SensorDraftRow[] | null>(null);
  const [globals, setGlobals] = useState<SensorDraftGlobals | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // Capture snapshot on first successful load of BOTH sensors + settings.
  useEffect(() => {
    if (snapshot !== null) return;
    if (!sensorsQuery.data || !settingsData) return;
    const initialRows = sensorsQuery.data.map(serverSensorToRow);
    const initialGlobals = settingsToGlobals(settingsData);
    setSnapshot({ rows: initialRows, globals: initialGlobals });
    setRows(initialRows);
    setGlobals(initialGlobals);
  }, [sensorsQuery.data, settingsData, snapshot]);

  const isDirty = useMemo(() => {
    if (!rows || !globals || !snapshot) return false;
    if (!globalsEqual(globals, snapshot.globals)) return true;
    // New or deleted row present → dirty.
    if (rows.some((r) => r.id === null || r._markedForDelete)) return true;
    // Any existing row differs from its snapshot counterpart.
    for (const r of rows) {
      if (r.id === null) continue;
      const snap = snapshot.rows.find((s) => s.id === r.id);
      if (!snap) return true; // safety: shouldn't happen
      if (!rowsEqual(r, snap)) return true;
    }
    return false;
  }, [rows, globals, snapshot]);

  const addRow = useCallback(() => {
    setRows((prev) => {
      const next = prev ? [...prev] : [];
      next.push({
        _localId: makeLocalId(),
        id: null,
        name: "",
        host: "",
        port: 161,
        community: "",
        communityDirty: false,
        temperature_oid: "",
        humidity_oid: "",
        temperature_scale: "1.0",
        humidity_scale: "1.0",
        enabled: true,
        chart_color: "",
        hasStoredCommunity: false,
        _markedForDelete: false,
      });
      return next;
    });
  }, []);

  const updateRow = useCallback(
    (_localId: string, patch: Partial<SensorDraftRow>) => {
      setRows((prev) => {
        if (!prev) return prev;
        return prev.map((r) => (r._localId === _localId ? { ...r, ...patch } : r));
      });
    },
    [],
  );

  const markRowDeleted = useCallback((_localId: string) => {
    setRows((prev) => {
      if (!prev) return prev;
      const row = prev.find((r) => r._localId === _localId);
      if (!row) return prev;
      // Unsaved new rows drop entirely — no server state to reconcile.
      if (row.id === null) {
        return prev.filter((r) => r._localId !== _localId);
      }
      // Existing rows: mark for deletion. save() issues the DELETE; until
      // then the row stays in the list so the user can unmark if we add
      // such a control later (40-02 delete dialog).
      return prev.map((r) =>
        r._localId === _localId ? { ...r, _markedForDelete: true } : r,
      );
    });
  }, []);

  const setGlobal = useCallback(
    <K extends keyof SensorDraftGlobals>(key: K, value: SensorDraftGlobals[K]) => {
      setGlobals((prev) => (prev ? { ...prev, [key]: value } : prev));
    },
    [],
  );

  const save = useCallback(async () => {
    if (!rows || !globals || !snapshot) return;
    validateSensorDraft(rows, globals);
    setIsSaving(true);
    try {
      // 1. Deletes first (existing rows marked for deletion).
      for (const r of rows) {
        if (r._markedForDelete && r.id !== null) {
          await deleteSensor(r.id);
        }
      }
      // 2. Creates (new rows).
      const createdMap = new Map<string, SensorRead>();
      for (const r of rows) {
        if (r.id === null && !r._markedForDelete) {
          const created = await createSensor(buildSensorCreatePayload(r));
          createdMap.set(r._localId, created);
        }
      }
      // 3. Updates (existing rows with dirty fields).
      for (const r of rows) {
        if (r.id === null || r._markedForDelete) continue;
        const snap = snapshot.rows.find((s) => s.id === r.id);
        if (!snap) continue;
        const body = buildSensorUpdatePayload(r, snap);
        if (Object.keys(body).length > 0) {
          await updateSensor(r.id, body);
        }
      }
      // 4. Globals (PUT /api/settings) if changed.
      const globalsBody = buildGlobalsPayload(globals, snapshot.globals);
      if (globalsBody && settingsData) {
        // PUT /api/settings requires the full brand block — merge with cache.
        // Phase 61: collapse into a single spread layout so there are no
        // duplicate literal keys (TS2783). Destructure the brand block from
        // the cached Settings so the payload stays narrow to
        // SettingsUpdatePayload (avoids leaking read-only fields like
        // logo_url, personio_has_credentials).
        const {
          color_primary,
          color_accent,
          color_background,
          color_foreground,
          color_muted,
          color_destructive,
          app_name,
        } = settingsData;
        await updateSettings({
          color_primary,
          color_accent,
          color_background,
          color_foreground,
          color_muted,
          color_destructive,
          app_name,
          ...globalsBody,
        });
      }
      // 5. Invalidate + refetch so snapshot re-captures from server truth.
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["sensors", "admin"] }),
        queryClient.invalidateQueries({ queryKey: sensorKeys.all }),
        queryClient.invalidateQueries({ queryKey: ["settings"] }),
      ]);
      const refreshed = await queryClient.fetchQuery<SensorRead[]>({
        queryKey: ["sensors", "admin"],
        queryFn: fetchSensors,
      });
      const refreshedSettings = queryClient.getQueryData<Settings>(["settings"]) ??
        settingsData;
      const nextRows = refreshed.map(serverSensorToRow);
      const nextGlobals = refreshedSettings
        ? settingsToGlobals(refreshedSettings)
        : globals;
      setRows(nextRows);
      setGlobals(nextGlobals);
      setSnapshot({ rows: nextRows, globals: nextGlobals });
      // Mark used to keep lint happy; createdMap reserved for 40-02 toast aggregation.
      void createdMap;
    } finally {
      setIsSaving(false);
    }
  }, [rows, globals, snapshot, settingsData, queryClient]);

  const discard = useCallback(() => {
    if (!snapshot) return;
    setRows(snapshot.rows);
    setGlobals(snapshot.globals);
  }, [snapshot]);

  return {
    isLoading: sensorsQuery.isLoading,
    isError: sensorsQuery.isError,
    rows,
    globals,
    snapshot,
    isDirty,
    isSaving,
    addRow,
    updateRow,
    markRowDeleted,
    setGlobal,
    save,
    discard,
  };
}
