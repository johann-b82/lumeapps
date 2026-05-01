import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import { toast } from "sonner";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { useSettings } from "@/hooks/useSettings";
import { useSettingsDraft } from "@/hooks/useSettingsDraft";
import { useUnsavedGuard } from "@/hooks/useUnsavedGuard";
import { PersonioCard } from "@/components/settings/PersonioCard";
import { HrTargetsCard } from "@/components/settings/HrTargetsCard";
import { ActionBar } from "@/components/settings/ActionBar";
import { ResetDialog } from "@/components/settings/ResetDialog";
import { UnsavedChangesDialog } from "@/components/settings/UnsavedChangesDialog";
import { useSettingsDraftStatus } from "@/contexts/SettingsDraftContext";

const SCOPE_PATH = "/settings/hr";

export function HrSettingsPage() {
  const { t } = useTranslation();
  const [, navigate] = useLocation();
  const { data: settingsData } = useSettings();
  const draftCtx = useSettingsDraftStatus();
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
  } = useSettingsDraft({ slice: "hr" });

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
      data-testid="settings-page-hr"
      className="max-w-7xl mx-auto px-6 pt-4 pb-32 space-y-8"
    >
      {isError && (
        <div className="p-6 text-destructive">{t("theme.error_toast")}</div>
      )}
      {(isLoading || !draft) && !isError && <div className="p-6">…</div>}
      {!isLoading && !isError && draft && (
        <>
          <header className="mb-12">
            <h1 className="text-3xl font-semibold leading-tight">
              {t("settings.section.hr")}
            </h1>
          </header>

          <Card>
            <CardHeader>
              <CardTitle className="text-xl font-semibold">{t("settings.hr.title")}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-8">
              <PersonioCard
                draft={draft}
                setField={setField}
                hasCredentials={settingsData?.personio_has_credentials ?? false}
                embedded
              />
              <hr className="border-border" />
              <HrTargetsCard draft={draft} setField={setField} embedded />
            </CardContent>
          </Card>

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
