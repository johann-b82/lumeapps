import { useCallback, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useSettings } from "@/hooks/useSettings";
import { updateSettings, type Settings, type SettingsUpdatePayload } from "@/lib/api";
import { DEFAULT_SETTINGS } from "@/lib/defaults";
import { hexToOklch, oklchToHex } from "@/lib/color";

/**
 * The editable fields exposed to the UI. Color fields are stored as HEX
 * strings in the draft (for HexColorPicker compatibility — D-03) and converted
 * to oklch only at save time. Non-color fields are stored as-is.
 * Phase 13: Personio fields added — credentials are write-only (not in GET response).
 */
export interface DraftFields {
  color_primary: string;      // hex "#rrggbb" in draft
  color_accent: string;       // hex
  color_background: string;   // hex
  color_foreground: string;   // hex
  color_muted: string;        // hex
  color_destructive: string;  // hex
  app_name: string;
  // Phase 13 Personio fields
  personio_client_id: string;           // local-only, write-only (not in Settings response)
  personio_client_secret: string;       // local-only, write-only
  personio_sync_interval_h: 0 | 1 | 6 | 24 | 168;
  personio_sick_leave_type_id: number[];
  personio_production_dept: string[];
  personio_skill_attr_key: string[];
  // v1.102 — Personio-Rückschreiben (inert bis Freischaltung)
  personio_writeback_enabled: boolean;
  personio_writeback_kategorie_id: string;
  // HR KPI targets (stored as ratios, e.g. 0.05 = 5%)
  target_overtime_ratio: number | null;
  target_sick_leave_ratio: number | null;
  target_fluctuation: number | null;
  target_revenue_per_employee: number | null;
  // v1.55 Sales-dashboard weekly targets — stored as plain numbers
  // (no percent-conversion; the 3 counts are integers in practice and
  // angebote_eur is a € amount).
  target_sales_erstkontakte: number | null;
  target_sales_interessenten: number | null;
  target_sales_besuche: number | null;
  target_sales_angebote_eur: number | null;
  // v1.56 — €/week/rep goal on the OrdersDistributionCard tile.
  target_sales_orders_per_rep_eur: number | null;
  // v1.66 / v1.69 — Quality KPI targets (complaint rates as ratios, finding counts as ints).
  target_complaint_rate_customer: number | null;
  target_complaint_rate_internal: number | null;
  target_complaint_rate_supplier: number | null;
  target_complaint_rate_subcontractor: number | null;
  target_audit_findings_level1: number | null;
  target_audit_findings_level2: number | null;
  target_inspection_large: number | null;
  target_inspection_small: number | null;
  // v1.71 Finance target (material-cost ratio as fraction, e.g. 0.15 = 15%)
  target_material_cost_ratio: number | null;
  target_personnel_cost_ratio: number | null;
  // v1.77 — Produktion Verzug target (max Verzugsquote as fraction, 0.20 = 20%)
  target_produktion_verzug: number | null;
  // v1.57 World Cup signage — api key is write-only (not in Settings response)
  worldcup_api_key: string;
  worldcup_refresh_seconds: number;
}

export interface UseSettingsDraftReturn {
  isLoading: boolean;
  isError: boolean;
  draft: DraftFields | null;
  snapshot: DraftFields | null;
  isDirty: boolean;
  isSaving: boolean;
  setField: <K extends keyof DraftFields>(field: K, value: DraftFields[K]) => void;
  save: () => Promise<void>;
  discard: () => void;
  resetToDefaults: () => Promise<void>;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Converts server Settings (oklch colors) into a DraftFields (hex colors).
 * Called once on first successful load (D-06 snapshot capture) and after
 * save/resetToDefaults to rotate the snapshot.
 * Phase 13: Personio credentials are write-only — always start empty in draft.
 */
function settingsToDraft(s: Settings): DraftFields {
  return {
    color_primary: oklchToHex(s.color_primary),
    color_accent: oklchToHex(s.color_accent),
    color_background: oklchToHex(s.color_background),
    color_foreground: oklchToHex(s.color_foreground),
    color_muted: oklchToHex(s.color_muted),
    color_destructive: oklchToHex(s.color_destructive),
    app_name: s.app_name,
    // Personio: credentials are write-only, always start empty
    personio_client_id: "",
    personio_client_secret: "",
    personio_sync_interval_h: ((s.personio_sync_interval_h ?? 1) as 0 | 1 | 6 | 24 | 168),
    personio_sick_leave_type_id: s.personio_sick_leave_type_id ?? [],
    personio_production_dept: s.personio_production_dept ?? [],
    personio_skill_attr_key: s.personio_skill_attr_key ?? [],
    personio_writeback_enabled: s.personio_writeback_enabled ?? false,
    personio_writeback_kategorie_id: s.personio_writeback_kategorie_id ?? "",
    target_overtime_ratio: s.target_overtime_ratio,
    target_sick_leave_ratio: s.target_sick_leave_ratio,
    target_fluctuation: s.target_fluctuation,
    target_revenue_per_employee: s.target_revenue_per_employee,
    target_sales_erstkontakte: s.target_sales_erstkontakte,
    target_sales_interessenten: s.target_sales_interessenten,
    target_sales_besuche: s.target_sales_besuche,
    target_sales_angebote_eur: s.target_sales_angebote_eur,
    target_sales_orders_per_rep_eur: s.target_sales_orders_per_rep_eur,
    target_complaint_rate_customer: s.target_complaint_rate_customer,
    target_complaint_rate_internal: s.target_complaint_rate_internal,
    target_complaint_rate_supplier: s.target_complaint_rate_supplier,
    target_complaint_rate_subcontractor: s.target_complaint_rate_subcontractor,
    target_audit_findings_level1: s.target_audit_findings_level1,
    target_audit_findings_level2: s.target_audit_findings_level2,
    target_inspection_large: s.target_inspection_large,
    target_inspection_small: s.target_inspection_small,
    target_material_cost_ratio: s.target_material_cost_ratio,
    target_personnel_cost_ratio: s.target_personnel_cost_ratio,
    target_produktion_verzug: s.target_produktion_verzug,
    // World Cup: api key is write-only, always start empty
    worldcup_api_key: "",
    worldcup_refresh_seconds: s.worldcup_refresh_seconds ?? 60,
  };
}

/**
 * Converts a DraftFields (hex colors) into a Settings-shaped object (oklch
 * colors) for pushing into the ["settings"] cache. Merges with the previous
 * cache value to preserve logo_url / logo_updated_at which are not part of
 * the draft.
 * Phase 13: Personio fields from draft are synced to cache (except credentials).
 */
function draftToCacheSettings(draft: DraftFields, prev: Settings): Settings {
  return {
    ...prev,
    color_primary: hexToOklch(draft.color_primary),
    color_accent: hexToOklch(draft.color_accent),
    color_background: hexToOklch(draft.color_background),
    color_foreground: hexToOklch(draft.color_foreground),
    color_muted: hexToOklch(draft.color_muted),
    color_destructive: hexToOklch(draft.color_destructive),
    app_name: draft.app_name,
    // Personio: keep server values from prev, only sync_interval from draft
    personio_sync_interval_h: draft.personio_sync_interval_h,
    personio_sick_leave_type_id: draft.personio_sick_leave_type_id,
    personio_production_dept: draft.personio_production_dept,
    personio_skill_attr_key: draft.personio_skill_attr_key,
    personio_writeback_enabled: draft.personio_writeback_enabled,
    personio_writeback_kategorie_id: draft.personio_writeback_kategorie_id || null,
    target_overtime_ratio: draft.target_overtime_ratio,
    target_sick_leave_ratio: draft.target_sick_leave_ratio,
    target_fluctuation: draft.target_fluctuation,
    target_revenue_per_employee: draft.target_revenue_per_employee,
    target_sales_erstkontakte: draft.target_sales_erstkontakte,
    target_sales_interessenten: draft.target_sales_interessenten,
    target_sales_besuche: draft.target_sales_besuche,
    target_sales_angebote_eur: draft.target_sales_angebote_eur,
    target_sales_orders_per_rep_eur: draft.target_sales_orders_per_rep_eur,
    target_complaint_rate_customer: draft.target_complaint_rate_customer,
    target_complaint_rate_internal: draft.target_complaint_rate_internal,
    target_complaint_rate_supplier: draft.target_complaint_rate_supplier,
    target_complaint_rate_subcontractor: draft.target_complaint_rate_subcontractor,
    target_audit_findings_level1: draft.target_audit_findings_level1,
    target_audit_findings_level2: draft.target_audit_findings_level2,
    target_inspection_large: draft.target_inspection_large,
    target_inspection_small: draft.target_inspection_small,
    target_material_cost_ratio: draft.target_material_cost_ratio,
    target_personnel_cost_ratio: draft.target_personnel_cost_ratio,
    target_produktion_verzug: draft.target_produktion_verzug,
    worldcup_refresh_seconds: draft.worldcup_refresh_seconds,
  };
}

/**
 * Builds the PUT payload from the current draft. Throws if any hex fails to
 * parse — caller (save) catches and surfaces via toast.
 * Phase 13: Personio fields included; credentials only sent if non-empty.
 */
function draftToPutPayload(draft: DraftFields): SettingsUpdatePayload {
  const payload: SettingsUpdatePayload = {
    color_primary: hexToOklch(draft.color_primary),
    color_accent: hexToOklch(draft.color_accent),
    color_background: hexToOklch(draft.color_background),
    color_foreground: hexToOklch(draft.color_foreground),
    color_muted: hexToOklch(draft.color_muted),
    color_destructive: hexToOklch(draft.color_destructive),
    app_name: draft.app_name,
    // Personio fields — only include if user changed them
    personio_sync_interval_h: draft.personio_sync_interval_h,
    personio_sick_leave_type_id: draft.personio_sick_leave_type_id,
    personio_production_dept: draft.personio_production_dept,
    personio_skill_attr_key: draft.personio_skill_attr_key,
    personio_writeback_enabled: draft.personio_writeback_enabled,
    personio_writeback_kategorie_id: draft.personio_writeback_kategorie_id || null,
    target_overtime_ratio: draft.target_overtime_ratio,
    target_sick_leave_ratio: draft.target_sick_leave_ratio,
    target_fluctuation: draft.target_fluctuation,
    target_revenue_per_employee: draft.target_revenue_per_employee,
    target_sales_erstkontakte: draft.target_sales_erstkontakte,
    target_sales_interessenten: draft.target_sales_interessenten,
    target_sales_besuche: draft.target_sales_besuche,
    target_sales_angebote_eur: draft.target_sales_angebote_eur,
    target_sales_orders_per_rep_eur: draft.target_sales_orders_per_rep_eur,
    target_complaint_rate_customer: draft.target_complaint_rate_customer,
    target_complaint_rate_internal: draft.target_complaint_rate_internal,
    target_complaint_rate_supplier: draft.target_complaint_rate_supplier,
    target_complaint_rate_subcontractor: draft.target_complaint_rate_subcontractor,
    target_audit_findings_level1: draft.target_audit_findings_level1,
    target_audit_findings_level2: draft.target_audit_findings_level2,
    target_inspection_large: draft.target_inspection_large,
    target_inspection_small: draft.target_inspection_small,
    target_material_cost_ratio: draft.target_material_cost_ratio,
    target_personnel_cost_ratio: draft.target_personnel_cost_ratio,
    target_produktion_verzug: draft.target_produktion_verzug,
    worldcup_refresh_seconds: draft.worldcup_refresh_seconds,
  };
  // Only send credentials if user typed something (non-empty)
  if (draft.personio_client_id) {
    payload.personio_client_id = draft.personio_client_id;
  }
  if (draft.personio_client_secret) {
    payload.personio_client_secret = draft.personio_client_secret;
  }
  if (draft.worldcup_api_key) {
    payload.worldcup_api_key = draft.worldcup_api_key;
  }
  return payload;
}

export type SettingsSlice = "general" | "hr" | "sales" | "worldcup" | "quality" | "finance" | "production";

const GENERAL_FIELDS = [
  "app_name",
  "color_primary",
  "color_accent",
  "color_background",
  "color_foreground",
  "color_muted",
  "color_destructive",
] as const satisfies readonly (keyof DraftFields)[];

const HR_FIELDS = [
  "personio_client_id",
  "personio_client_secret",
  "personio_sync_interval_h",
  "personio_sick_leave_type_id",
  "personio_production_dept",
  "personio_skill_attr_key",
  "personio_writeback_enabled",
  "personio_writeback_kategorie_id",
  "target_overtime_ratio",
  "target_sick_leave_ratio",
  "target_fluctuation",
  "target_revenue_per_employee",
] as const satisfies readonly (keyof DraftFields)[];

const SALES_FIELDS = [
  "target_sales_erstkontakte",
  "target_sales_interessenten",
  "target_sales_besuche",
  "target_sales_angebote_eur",
  "target_sales_orders_per_rep_eur",
] as const satisfies readonly (keyof DraftFields)[];

const WORLDCUP_FIELDS = [
  "worldcup_api_key",
  "worldcup_refresh_seconds",
] as const satisfies readonly (keyof DraftFields)[];

const QUALITY_FIELDS = [
  "target_complaint_rate_customer",
  "target_complaint_rate_internal",
  "target_complaint_rate_supplier",
  "target_complaint_rate_subcontractor",
  "target_audit_findings_level1",
  "target_audit_findings_level2",
  "target_inspection_large",
  "target_inspection_small",
] as const satisfies readonly (keyof DraftFields)[];

const FINANCE_FIELDS = [
  "target_material_cost_ratio",
  "target_personnel_cost_ratio",
] as const satisfies readonly (keyof DraftFields)[];

const PRODUCTION_FIELDS = [
  "target_produktion_verzug",
] as const satisfies readonly (keyof DraftFields)[];

function fieldsForSlice(slice: SettingsSlice): readonly (keyof DraftFields)[] {
  if (slice === "general") return GENERAL_FIELDS;
  if (slice === "hr") return HR_FIELDS;
  if (slice === "worldcup") return WORLDCUP_FIELDS;
  if (slice === "quality") return QUALITY_FIELDS;
  if (slice === "finance") return FINANCE_FIELDS;
  if (slice === "production") return PRODUCTION_FIELDS;
  return SALES_FIELDS;
}

function eqField<K extends keyof DraftFields>(
  _key: K,
  a: DraftFields[K],
  b: DraftFields[K],
): boolean {
  if (Array.isArray(a) && Array.isArray(b)) {
    return JSON.stringify(a) === JSON.stringify(b);
  }
  return a === b;
}

function sliceIsDirty(
  draft: DraftFields,
  snapshot: DraftFields,
  slice: SettingsSlice,
): boolean {
  for (const k of fieldsForSlice(slice)) {
    if (!eqField(k, draft[k], snapshot[k])) return true;
  }
  return false;
}

interface UseSettingsDraftOptions {
  slice: SettingsSlice;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

export function useSettingsDraft(
  opts: UseSettingsDraftOptions = { slice: "general" },
): UseSettingsDraftReturn {
  const { slice } = opts;
  const queryClient = useQueryClient();
  const { data, isLoading, isError } = useSettings();
  const [snapshot, setSnapshot] = useState<DraftFields | null>(null);
  const [draft, setDraft] = useState<DraftFields | null>(null);
  const [isSaving, setIsSaving] = useState(false);

  // Capture snapshot on first successful load (D-06).
  // Subsequent reloads of `data` do NOT overwrite snapshot — save() and
  // resetToDefaults() are the only code paths that rotate the snapshot.
  useEffect(() => {
    if (data && snapshot === null) {
      const next = settingsToDraft(data);
      setSnapshot(next);
      setDraft(next);
    }
  }, [data, snapshot]);

  const isDirty = useMemo(() => {
    if (!draft || !snapshot) return false;
    return sliceIsDirty(draft, snapshot, slice);
  }, [draft, snapshot, slice]);

  const setField = useCallback(
    <K extends keyof DraftFields>(field: K, value: DraftFields[K]) => {
      setDraft((prev) => {
        if (!prev) return prev;
        const next = { ...prev, [field]: value };
        // Live preview: push draft into the ["settings"] cache so
        // ThemeProvider.applyTheme reapplies (D-04, BRAND-07). We ONLY
        // write if hex→oklch conversion succeeds for all 6 colors;
        // invalid hex mid-typing (e.g. user deleted chars) is silently
        // skipped for the cache write but still stored in draft so the
        // input reflects exactly what the user typed.
        try {
          const prevCache = queryClient.getQueryData<Settings>(["settings"]);
          if (prevCache) {
            queryClient.setQueryData<Settings>(
              ["settings"],
              draftToCacheSettings(next, prevCache),
            );
          }
        } catch {
          // Intentional: mid-edit invalid hex should not crash the app;
          // the cache simply stays at its last valid value and the UI
          // shows the in-progress input until the user completes a valid
          // hex. Save() will re-throw on submit if still invalid.
        }
        return next;
      });
    },
    [queryClient],
  );

  const save = useCallback(async () => {
    if (!draft) return;
    setIsSaving(true);
    try {
      const payload = draftToPutPayload(draft);   // may throw on invalid hex
      const response = await updateSettings(payload);
      // Success: rotate snapshot to response, sync cache to response (Pitfall 6)
      const nextSnapshot = settingsToDraft(response);
      setSnapshot(nextSnapshot);
      setDraft(nextSnapshot);
      queryClient.setQueryData<Settings>(["settings"], response);
    } finally {
      setIsSaving(false);
    }
    // NOTE: On error the caller (SettingsPage) catches via try/catch on
    // save() and fires toast.error. Draft is NOT reverted — per D-10 and
    // UX-02 the failed save preserves the draft state so the user can
    // retry or fix. This function re-throws implicitly because we do not
    // wrap updateSettings() in try/catch.
  }, [draft, queryClient]);

  const discard = useCallback(() => {
    if (!snapshot) return;
    setDraft(snapshot);
    // Revert the live preview too: push snapshot (in oklch form) back
    // into the cache so ThemeProvider re-applies the pre-edit palette.
    const prevCache = queryClient.getQueryData<Settings>(["settings"]);
    if (prevCache) {
      queryClient.setQueryData<Settings>(
        ["settings"],
        draftToCacheSettings(snapshot, prevCache),
      );
    }
  }, [snapshot, queryClient]);

  const resetToDefaults = useCallback(async () => {
    setIsSaving(true);
    try {
      // Per D-12: PUT with DEFAULT_SETTINGS verbatim — backend detects
      // exact match and clears logo_data/logo_mime/logo_updated_at.
      const payload: SettingsUpdatePayload = {
        color_primary: DEFAULT_SETTINGS.color_primary,
        color_accent: DEFAULT_SETTINGS.color_accent,
        color_background: DEFAULT_SETTINGS.color_background,
        color_foreground: DEFAULT_SETTINGS.color_foreground,
        color_muted: DEFAULT_SETTINGS.color_muted,
        color_destructive: DEFAULT_SETTINGS.color_destructive,
        app_name: DEFAULT_SETTINGS.app_name,
      };
      const response = await updateSettings(payload);
      const nextSnapshot = settingsToDraft(response);
      setSnapshot(nextSnapshot);
      setDraft(nextSnapshot);
      queryClient.setQueryData<Settings>(["settings"], response);
    } finally {
      setIsSaving(false);
    }
  }, [queryClient]);

  return {
    isLoading,
    isError,
    draft,
    snapshot,
    isDirty,
    isSaving,
    setField,
    save,
    discard,
    resetToDefaults,
  };
}
