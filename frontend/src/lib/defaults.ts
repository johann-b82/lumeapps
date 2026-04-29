import type { Settings } from "./api";

export const DEFAULT_SETTINGS: Settings = {
  color_primary: "oklch(0.55 0.15 250)",
  color_accent: "oklch(0.70 0.18 150)",
  color_background: "oklch(1.00 0 0)",
  color_foreground: "oklch(0.15 0 0)",
  color_muted: "oklch(0.90 0 0)",
  color_destructive: "oklch(0.55 0.22 25)",
  app_name: "KPI Dashboard",
  logo_url: null,
  logo_updated_at: null,
  // Phase 13 Personio fields — defaults used for reset-to-defaults
  personio_has_credentials: false,
  personio_sync_interval_h: 1,
  personio_sick_leave_type_id: [],
  personio_production_dept: [],
  personio_skill_attr_key: [],
  target_overtime_ratio: null,
  target_sick_leave_ratio: null,
  target_fluctuation: null,
  target_revenue_per_employee: null,
  // Phase 38 sensor globals (v1.15): 60s poll matches scheduler baseline;
  // null thresholds = "no threshold set" (matches useSensorDraft
  // buildGlobalsPayload empty-string early-exit contract).
  sensor_poll_interval_s: 60,
  sensor_temperature_min: null,
  sensor_temperature_max: null,
  sensor_humidity_min: null,
  sensor_humidity_max: null,
};

export const THEME_TOKEN_MAP = {
  color_primary: "--primary",
  color_accent: "--accent",
  color_background: "--background",
  color_foreground: "--foreground",
  color_muted: "--muted",
  color_destructive: "--destructive",
} as const;
