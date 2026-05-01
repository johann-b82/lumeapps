import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import { toast } from "sonner";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSettings } from "@/hooks/useSettings";
import { useSettingsDraft } from "@/hooks/useSettingsDraft";
import { useUnsavedGuard } from "@/hooks/useUnsavedGuard";
import { hexToOklch, WHITE_OKLCH } from "@/lib/color";
import { ColorPicker } from "@/components/settings/ColorPicker";
import { ContrastBadge } from "@/components/settings/ContrastBadge";
import { LogoUpload } from "@/components/settings/LogoUpload";
import { ActionBar } from "@/components/settings/ActionBar";
import { ResetDialog } from "@/components/settings/ResetDialog";
import { UnsavedChangesDialog } from "@/components/settings/UnsavedChangesDialog";
import { useSettingsDraftStatus } from "@/contexts/SettingsDraftContext";

const SCOPE_PATH = "/settings/general";

function safeHexToOklch(hex: string): string | null {
  try { return hexToOklch(hex); } catch { return null; }
}

export function GeneralSettingsPage() {
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
  } = useSettingsDraft({ slice: "general" });

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

  const primaryFg = draft
    ? safeHexToOklch(draft.color_foreground) ?? draft.color_foreground
    : "";

  return (
    <div
      data-testid="settings-page-general"
      className="max-w-7xl mx-auto px-6 pt-4 pb-32 space-y-4"
    >
      {isError && (
        <div className="p-6 text-destructive">{t("theme.error_toast")}</div>
      )}
      {(isLoading || !draft) && !isError && <div className="p-6">…</div>}
      {!isLoading && !isError && draft && (<>
      {/* v1.29: redundant H1 removed — the SubHeader dropdown shows the active section. */}

      <Card>
        <CardHeader>
          <CardTitle className="text-xl font-semibold">
            {t("settings.identity.title")}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-8">
          <div className="grid grid-cols-1 md:grid-cols-6 gap-6">
            <div className="flex flex-col gap-2 md:col-span-2">
              <Label htmlFor="app-name" className="text-sm font-medium">
                {t("settings.identity.app_name.label")}
              </Label>
              <Input
                id="app-name"
                value={draft.app_name}
                onChange={(e) => setField("app_name", e.target.value)}
                placeholder={t("settings.identity.app_name.placeholder")}
              />
              <p className="text-xs text-muted-foreground">
                {t("settings.identity.app_name.help")}
              </p>
            </div>
            <div className="flex flex-col gap-2 md:col-span-4">
              <Label className="text-sm font-medium">
                {t("settings.identity.logo.label")}
              </Label>
              <LogoUpload logoUrl={settingsData?.logo_url ?? null} />
            </div>
          </div>

          <hr className="border-border" />

          <section className="space-y-4">
            <h3 className="text-base font-semibold">{t("settings.colors.title")}</h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
              <ColorPicker
                label={t("settings.colors.primary")}
                value={draft.color_primary}
                onChange={(hex) => setField("color_primary", hex)}
                contrastBadge={
                  <ContrastBadge
                    colorA={safeHexToOklch(draft.color_primary) ?? ""}
                    colorB={primaryFg}
                  />
                }
              />
              <ColorPicker
                label={t("settings.colors.accent")}
                value={draft.color_accent}
                onChange={(hex) => setField("color_accent", hex)}
              />
              <ColorPicker
                label={t("settings.colors.background")}
                value={draft.color_background}
                onChange={(hex) => setField("color_background", hex)}
                contrastBadge={
                  <ContrastBadge
                    colorA={draft.color_background}
                    colorB={draft.color_foreground}
                  />
                }
              />
              <ColorPicker
                label={t("settings.colors.foreground")}
                value={draft.color_foreground}
                onChange={(hex) => setField("color_foreground", hex)}
                contrastBadge={
                  <ContrastBadge
                    colorA={draft.color_foreground}
                    colorB={draft.color_background}
                  />
                }
              />
              <ColorPicker
                label={t("settings.colors.muted")}
                value={draft.color_muted}
                onChange={(hex) => setField("color_muted", hex)}
              />
              <ColorPicker
                label={t("settings.colors.destructive")}
                value={draft.color_destructive}
                onChange={(hex) => setField("color_destructive", hex)}
                contrastBadge={
                  <ContrastBadge
                    colorA={safeHexToOklch(draft.color_destructive) ?? ""}
                    colorB={WHITE_OKLCH}
                  />
                }
              />
            </div>
          </section>
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
      </>)}
    </div>
  );
}
