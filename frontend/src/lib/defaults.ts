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
  // v1.66 Quality targets
  target_complaint_rate_customer: null,
  target_complaint_rate_internal: null,
  target_complaint_rate_supplier: null,
  target_complaint_rate_subcontractor: null,
  target_audit_findings_level1: null,
  target_audit_findings_level2: null,
  target_inspection_large: null,
  target_inspection_small: null,
  // v1.71 / v1.72 Finance targets (cost ratios)
  target_material_cost_ratio: null,
  target_personnel_cost_ratio: null,
  target_produktion_verzug: null,
  // v1.55 Sales-dashboard weekly targets
  target_sales_erstkontakte: null,
  target_sales_interessenten: null,
  target_sales_besuche: null,
  target_sales_angebote_eur: null,
  // v1.56 — €/week/rep goal on the OrdersDistributionCard tile.
  target_sales_orders_per_rep_eur: null,
  // Phase 38 sensor globals (v1.15): 60s poll matches scheduler baseline;
  // null thresholds = "no threshold set" (matches useSensorDraft
  // buildGlobalsPayload empty-string early-exit contract).
  sensor_poll_interval_s: 60,
  sensor_temperature_min: null,
  sensor_temperature_max: null,
  sensor_humidity_min: null,
  sensor_humidity_max: null,
  // v1.57 World Cup signage
  worldcup_has_api_key: false,
  worldcup_refresh_seconds: 60,
  // ATR fileserver defaults — null = "not configured yet".
  atr_smb_host: null,
  atr_smb_share: null,
  atr_smb_domain: null,
  atr_smb_user: null,
  atr_smb_has_password: false,
  atr_input_path: null,
  atr_output_path: null,
  atr_archive_path: null,
  atr_scan_interval_s: 60,
  atr_auto_mode: false,
  // v1.83 E-Mail (Office 365 / Graph) defaults — null/false = "not configured".
  email_tenant_id: null,
  email_client_id: null,
  email_sender_address: null,
  email_sender_name: null,
  email_has_secret: false,
  email_enabled: false,
  email_auth_mode: "app",
  email_delegated_account: null,
  email_delegated_connected: false,
};

export const THEME_TOKEN_MAP = {
  color_primary: "--primary",
  color_accent: "--accent",
  color_background: "--background",
  color_foreground: "--foreground",
  color_muted: "--muted",
  color_destructive: "--destructive",
} as const;
