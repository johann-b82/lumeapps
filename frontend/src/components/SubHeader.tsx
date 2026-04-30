import { Link, useLocation } from "wouter";
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { Upload as UploadIcon } from "lucide-react";
import { AdminOnly } from "@/auth/AdminOnly";
import { Toggle } from "@/components/ui/toggle";
import { SegmentedControl } from "@/components/ui/segmented-control";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { DateRangeFilter } from "@/components/dashboard/DateRangeFilter";
import { FreshnessIndicator } from "@/components/dashboard/FreshnessIndicator";
import { SensorTimeWindowPicker } from "@/components/sensors/SensorTimeWindow";
import { PollNowButton } from "@/components/sensors/PollNowButton";
import { useDateRange } from "@/contexts/DateRangeContext";
import { fetchSyncMeta, fetchSensorStatus } from "@/lib/api";
import { syncKeys, sensorKeys } from "@/lib/queryKeys";
import { cn } from "@/lib/utils";

function HrFreshnessIndicator() {
  const { t, i18n } = useTranslation();
  const { data, isLoading } = useQuery({
    queryKey: syncKeys.meta(),
    queryFn: fetchSyncMeta,
  });

  if (isLoading) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }
  if (!data?.last_synced_at) {
    return (
      <span className="text-xs text-muted-foreground">
        {t("hr.sync.never")}
      </span>
    );
  }
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const formatted = new Intl.DateTimeFormat(locale, {
    dateStyle: "short",
    timeStyle: "short",
  }).format(new Date(data.last_synced_at));
  return (
    <span className="text-xs text-muted-foreground">
      {t("hr.sync.lastSynced")} {formatted}
    </span>
  );
}

/**
 * Sensor freshness — aggregate "last measured" across all enabled sensors.
 * Uses sensorKeys.status() with D-07 refetch config (15s foreground, stop in
 * background, refetch on focus, 5s stale). Next-poll display is deferred to a
 * later plan: sensor_poll_interval_s lives on AppSettings but isn't exposed
 * via /api/settings yet (Phase 40 scope).
 */
function SensorFreshnessIndicator() {
  const { t } = useTranslation();
  const { data, isLoading } = useQuery({
    queryKey: sensorKeys.status(),
    queryFn: fetchSensorStatus,
    refetchInterval: 15_000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
    staleTime: 5_000,
  });

  if (isLoading) {
    return <span className="text-xs text-muted-foreground">—</span>;
  }

  const successTimestamps = (data ?? [])
    .map((s) => s.last_success_at)
    .filter((v): v is string => v != null)
    .map((ts) => new Date(ts).getTime())
    .filter((n) => Number.isFinite(n));

  if (successTimestamps.length === 0) {
    return (
      <span className="text-xs text-muted-foreground">
        {t("sensors.subheader.never")}
      </span>
    );
  }

  const latest = Math.max(...successTimestamps);
  const seconds = Math.max(0, Math.floor((Date.now() - latest) / 1000));
  return (
    <span className="text-xs text-muted-foreground">
      {t("sensors.subheader.lastMeasured", { seconds })}
    </span>
  );
}

export function SubHeader() {
  const { t } = useTranslation();
  const [location, navigate] = useLocation();
  const { preset, range, handleFilterChange } = useDateRange();

  // Launcher surface hides chrome entirely — return null after all hooks
  // so React's rules-of-hooks (constant hook order) are preserved across
  // navigation between / and other routes.
  if (location === "/") return null;

  const isDashboard = location === "/sales" || location === "/hr";

  // Signage admin routes share a 4-tab pill. /signage/pair is a standalone
  // pairing screen and keeps the default SubHeader layout (no tabs).
  const signageTabs = [
    { id: "media",     path: "/signage/media",     labelKey: "signage.admin.nav.media" },
    { id: "playlists", path: "/signage/playlists", labelKey: "signage.admin.nav.playlists" },
    { id: "devices",   path: "/signage/devices",   labelKey: "signage.admin.nav.devices" },
    { id: "schedules", path: "/signage/schedules", labelKey: "signage.admin.nav.schedules" },
  ] as const;
  const signageActive = location.startsWith("/signage/playlists")
    ? "playlists"
    : location.startsWith("/signage/devices")
    ? "devices"
    : location.startsWith("/signage/schedules")
    ? "schedules"
    : location.startsWith("/signage/media")
    ? "media"
    : null;
  const showSignageTabs = signageActive !== null && location !== "/signage/pair";

  return (
    <div className="fixed top-16 inset-x-0 h-12 bg-background z-40 shadow-sm">
      <div className="max-w-7xl mx-auto px-6 h-full flex items-center justify-between">
        <div className="flex items-center gap-3">
          {isDashboard && (
            <Toggle
              segments={[
                { value: "/sales", label: t("nav.sales") },
                { value: "/hr", label: t("nav.hr") },
              ] as const}
              value={location === "/hr" ? "/hr" : "/sales"}
              onChange={(path) => navigate(path)}
              aria-label={t("nav.dashboardToggleLabel")}
              variant="muted"
            />
          )}
          {isDashboard && (
            <DateRangeFilter
              value={range}
              preset={preset}
              onChange={handleFilterChange}
            />
          )}
          {location === "/sensors" && <SensorTimeWindowPicker />}
          {showSignageTabs && (
            <>
              <div data-testid="signage-tabs-desktop" className="hidden md:block">
                <SegmentedControl
                  segments={signageTabs.map((tab) => ({ value: tab.id, label: t(tab.labelKey) }))}
                  value={signageActive}
                  onChange={(id) => {
                    const target = signageTabs.find((tab) => tab.id === id);
                    if (target) navigate(target.path);
                  }}
                  aria-label={t("signage.admin.page_title")}
                />
              </div>
              <div data-testid="signage-tabs-mobile" className="md:hidden">
                <Select
                  value={signageActive}
                  onValueChange={(id) => {
                    const target = signageTabs.find((tab) => tab.id === id);
                    if (target) navigate(target.path);
                  }}
                >
                  <SelectTrigger className="w-40" aria-label={t("signage.admin.page_title")}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {signageTabs.map((tab) => (
                      <SelectItem key={tab.id} value={tab.id}>
                        {t(tab.labelKey)}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </>
          )}
        </div>
        <div className="flex items-center gap-3">
          {location === "/sales" && (
            <AdminOnly>
              <Link
                href="/upload"
                aria-label={t("nav.upload")}
                className={cn(
                  "inline-flex items-center justify-center rounded-md p-1.5 hover:bg-accent/10 transition-colors",
                  "text-foreground",
                )}
              >
                <UploadIcon className="h-4 w-4" />
              </Link>
            </AdminOnly>
          )}
          {location === "/sensors" && <PollNowButton size="sm" />}
          {location === "/sensors" ? (
            <SensorFreshnessIndicator />
          ) : location === "/hr" ? (
            <HrFreshnessIndicator />
          ) : (
            <FreshnessIndicator />
          )}
        </div>
      </div>
    </div>
  );
}
