import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import { toast } from "sonner";
import { useSettingsDraft } from "@/hooks/useSettingsDraft";
import { useUnsavedGuard } from "@/hooks/useUnsavedGuard";
import { QualityTargetsCard } from "@/components/settings/QualityTargetsCard";
import { ActionBar } from "@/components/settings/ActionBar";
import { UnsavedChangesDialog } from "@/components/settings/UnsavedChangesDialog";
import { useSettingsDraftStatus } from "@/contexts/SettingsDraftContext";

const SCOPE_PATH = "/settings/quality";

export function QualitySettingsPage() {
  const { t } = useTranslation();
  const [, navigate] = useLocation();
  const draftCtx = useSettingsDraftStatus();
  const { draft, isDirty, isLoading, isError, isSaving, setField, save, discard } =
    useSettingsDraft({ slice: "quality" });

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

  return (
    <div
      data-testid="settings-page-quality"
      className="max-w-7xl mx-auto px-6 pt-4 pb-32 space-y-4"
    >
      {isError && <div className="p-6 text-destructive">{t("theme.error_toast")}</div>}
      {(isLoading || !draft) && !isError && <div className="p-6">…</div>}
      {!isLoading && !isError && draft && (
        <>
          <QualityTargetsCard draft={draft} setField={setField} />

          {/* No reset-to-defaults flow: there are no defaults for these
              targets — each one is a user-supplied threshold. Hide the
              reset button entirely. */}
          <ActionBar
            isDirty={isDirty}
            isSaving={isSaving}
            onSave={handleSave}
            onDiscard={discard}
            onResetClick={() => {}}
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
        </>
      )}
    </div>
  );
}
