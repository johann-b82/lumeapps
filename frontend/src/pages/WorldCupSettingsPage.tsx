import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import { toast } from "sonner";
import { useSettings } from "@/hooks/useSettings";
import { useSettingsDraft } from "@/hooks/useSettingsDraft";
import { useUnsavedGuard } from "@/hooks/useUnsavedGuard";
import { WorldCupSettingsCard } from "@/components/settings/WorldCupSettingsCard";
import { ActionBar } from "@/components/settings/ActionBar";
import { ResetDialog } from "@/components/settings/ResetDialog";
import { UnsavedChangesDialog } from "@/components/settings/UnsavedChangesDialog";
import { useSettingsDraftStatus } from "@/contexts/SettingsDraftContext";

const SCOPE_PATH = "/settings/worldcup";

export function WorldCupSettingsPage() {
  const { t } = useTranslation();
  const [, navigate] = useLocation();
  const draftCtx = useSettingsDraftStatus();
  const { data: settings } = useSettings();
  const {
    draft,
    isDirty,
    isLoading,
    isError,
    isSaving,
    setField,
    save,
    discard,
    resetToDefaults,
  } = useSettingsDraft({ slice: "worldcup" });

  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [unsavedDialogOpen, setUnsavedDialogOpen] = useState(false);
  const [pendingNav, setPendingNav] = useState<string | null>(null);

  useEffect(() => {
    draftCtx?.setDirty(isDirty);
  }, [draftCtx, isDirty]);

  useEffect(() => {
    if (!draftCtx?.pendingSection) return;
    setPendingNav(`/settings/${draftCtx.pendingSection}`);
    setUnsavedDialogOpen(true);
  }, [draftCtx?.pendingSection]);

  const handleStay = useCallback(() => {
    setUnsavedDialogOpen(false);
    setPendingNav(null);
    draftCtx?.clearPendingSection();
  }, [draftCtx]);

  const handleDiscardAndLeave = useCallback(() => {
    discard();
    setUnsavedDialogOpen(false);
    const dest = pendingNav;
    setPendingNav(null);
    draftCtx?.clearPendingSection();
    if (dest && dest !== "__back__") navigate(dest);
    if (dest === "__back__") window.history.back();
  }, [discard, navigate, pendingNav, draftCtx]);

  const handleShowDialog = useCallback((to: string) => {
    setPendingNav(to);
    setUnsavedDialogOpen(true);
  }, []);
  useUnsavedGuard(isDirty, handleShowDialog, SCOPE_PATH);

  const handleSave = useCallback(async () => {
    try {
      await save();
      toast.success(t("settings.toasts.saved"));
    } catch (err) {
      toast.error((err as Error).message ?? t("settings.toasts.save_error"));
    }
  }, [save, t]);

  const handleResetConfirm = useCallback(async () => {
    try {
      await resetToDefaults();
      setResetDialogOpen(false);
      toast.success(t("settings.toasts.saved"));
    } catch (err) {
      toast.error((err as Error).message ?? t("settings.toasts.save_error"));
    }
  }, [resetToDefaults, t]);

  return (
    <div
      data-testid="settings-page-worldcup"
      className="max-w-7xl mx-auto px-6 pt-4 pb-32 space-y-4"
    >
      {isError && (
        <div className="p-6 text-destructive">{t("theme.error_toast")}</div>
      )}
      {(isLoading || !draft) && !isError && <div className="p-6">…</div>}
      {!isLoading && !isError && draft && (
        <>
          <WorldCupSettingsCard
            draft={draft}
            setField={setField}
            hasApiKey={settings?.worldcup_has_api_key ?? false}
          />

          <ActionBar
            isDirty={isDirty}
            isSaving={isSaving}
            onSave={handleSave}
            onDiscard={discard}
            onResetClick={() => setResetDialogOpen(true)}
          />

          <ResetDialog
            open={resetDialogOpen}
            onOpenChange={setResetDialogOpen}
            onConfirm={handleResetConfirm}
            isPending={isSaving}
          />

          <UnsavedChangesDialog
            open={unsavedDialogOpen}
            onOpenChange={(open) => {
              if (!open) handleStay();
            }}
            onStay={handleStay}
            onDiscardAndLeave={handleDiscardAndLeave}
          />
        </>
      )}
    </div>
  );
}
