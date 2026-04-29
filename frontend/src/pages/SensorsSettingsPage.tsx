import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import { toast } from "sonner";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ActionBar } from "@/components/settings/ActionBar";
import { UnsavedChangesDialog } from "@/components/settings/UnsavedChangesDialog";
import { useSensorDraft } from "@/hooks/useSensorDraft";
import { useUnsavedGuard } from "@/hooks/useUnsavedGuard";
import { useSensorDraftStatus } from "@/contexts/SensorDraftContext";
import { useRole } from "@/auth/useAuth";
import { SectionHeader } from "@/components/ui/section-header";
import { SensorRowList } from "@/components/settings/sensors/SensorRowList";
import { PollIntervalCard } from "@/components/settings/sensors/PollIntervalCard";
import { ThresholdCard } from "@/components/settings/sensors/ThresholdCard";
import { SnmpWalkCard } from "@/components/settings/sensors/SnmpWalkCard";

/**
 * Phase 40-01 — admin-only sensor configuration sub-page.
 *
 * Route: /settings/sensors (declared BEFORE /settings in App.tsx so wouter's
 * first-match resolves to this page and not the main SettingsPage).
 *
 * Access: useRole()-guarded shell renders "admin only" content for Viewer;
 * backend enforces the same check via router-level require_admin (defense
 * in depth). The page body wires the same SettingsDraft / UnsavedGuard /
 * ActionBar infrastructure as /settings, with a multi-row draft (see
 * useSensorDraft).
 */
export function SensorsSettingsPage() {
  const { t } = useTranslation();
  const [, navigate] = useLocation();
  const role = useRole();

  const {
    isLoading,
    isError,
    rows,
    globals,
    isDirty,
    isSaving,
    addRow,
    updateRow,
    markRowDeleted,
    setGlobal,
    save,
    discard,
  } = useSensorDraft();

  const [unsavedDialogOpen, setUnsavedDialogOpen] = useState(false);
  const [pendingNav, setPendingNav] = useState<string | null>(null);

  const handleShowUnsavedDialog = useCallback((to: string) => {
    setPendingNav(to);
    setUnsavedDialogOpen(true);
  }, []);

  // Scope the guard to /settings/sensors specifically (default is /settings).
  useUnsavedGuard(isDirty, handleShowUnsavedDialog, "/settings/sensors");

  // Sync isDirty into the app-level SensorDraft context (mirrors the
  // SettingsPage pattern for NavBar integration).
  const draftStatus = useSensorDraftStatus();
  useEffect(() => {
    draftStatus?.setDirty(isDirty);
    return () => {
      draftStatus?.setDirty(false);
    };
  }, [isDirty, draftStatus]);

  // ----- Role guard -----
  if (role !== "admin") {
    return (
      <div className="max-w-7xl mx-auto px-6 pt-4 pb-8 space-y-4">
        <h1 className="text-3xl font-semibold">{t("auth.admin_only.title")}</h1>
        <p className="text-base text-muted-foreground">
          {t("auth.admin_only.body")}
        </p>
      </div>
    );
  }

  // ----- Loading / error -----
  if (isLoading || !rows || !globals) {
    return null;
  }
  if (isError) {
    return (
      <div className="max-w-7xl mx-auto px-6 pt-4 pb-8">
        <h1 className="text-3xl font-semibold">
          {t("settings.error.heading")}
        </h1>
      </div>
    );
  }

  // ----- Save -----
  const handleSave = async () => {
    try {
      await save();
      toast.success(t("sensors.admin.save.success"));
    } catch (err) {
      const message = err instanceof Error ? err.message : "Unknown error";
      // Validation errors are i18n keys; backend/network errors are raw text.
      // t() falls back to the key verbatim if not found, which is acceptable
      // for surfacing HTTP error bodies.
      const translated =
        message.startsWith("sensors.admin.") ||
        message.startsWith("sensors.admin.validation.") ||
        message.startsWith("sensors.admin.poll_interval.")
          ? t(message)
          : message;
      toast.error(t("sensors.admin.save.error", { detail: translated }));
    }
  };

  // ----- Unsaved-guard Stay / Discard handlers -----
  const handleStay = () => {
    setUnsavedDialogOpen(false);
    setPendingNav(null);
  };

  const handleDiscardAndLeave = () => {
    discard();
    setUnsavedDialogOpen(false);
    const to = pendingNav;
    setPendingNav(null);
    if (to === "__back__") {
      window.history.go(-2);
    } else if (to) {
      navigate(to);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-32 space-y-8">
      <SectionHeader
        title={t("section.settings.sensors.title")}
        description={t("section.settings.sensors.description")}
        className="mt-8"
      />

      <Card>
        <CardHeader>
          <CardTitle className="text-xl font-semibold">
            {t("sensors.admin.sensors.title")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <SensorRowList
            rows={rows}
            onUpdate={updateRow}
            onRemove={markRowDeleted}
          />
          <Button type="button" variant="outline" onClick={addRow}>
            {t("sensors.admin.add_sensor")}
          </Button>
        </CardContent>
      </Card>

      <SnmpWalkCard rows={rows} onUpdateRow={updateRow} />

      <PollIntervalCard
        value={globals.sensor_poll_interval_s}
        onChange={(next) => setGlobal("sensor_poll_interval_s", next)}
      />

      <ThresholdCard globals={globals} setGlobal={setGlobal} />

      <ActionBar
        isDirty={isDirty}
        isSaving={isSaving}
        onSave={handleSave}
        onDiscard={discard}
        onResetClick={() => {
          /* no-op — hideReset */
        }}
        hideReset
      />

      <UnsavedChangesDialog
        open={unsavedDialogOpen}
        onOpenChange={(open) => {
          if (!open) handleStay();
        }}
        onStay={handleStay}
        onDiscardAndLeave={handleDiscardAndLeave}
      />
    </div>
  );
}
