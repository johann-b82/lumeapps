import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation } from "wouter";
import { toast } from "sonner";
import { Thermometer } from "lucide-react";
import { AdminOnly } from "@/auth/AdminOnly";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSettings } from "@/hooks/useSettings";
import { useSettingsDraft, type DraftFields } from "@/hooks/useSettingsDraft";
import { useUnsavedGuard } from "@/hooks/useUnsavedGuard";
import { hexToOklch, WHITE_OKLCH } from "@/lib/color";
import { ColorPicker } from "@/components/settings/ColorPicker";
import { ContrastBadge } from "@/components/settings/ContrastBadge";
import { LogoUpload } from "@/components/settings/LogoUpload";
import { PersonioCard } from "@/components/settings/PersonioCard";
import { HrTargetsCard } from "@/components/settings/HrTargetsCard";
import { ActionBar } from "@/components/settings/ActionBar";
import { ResetDialog } from "@/components/settings/ResetDialog";
import { UnsavedChangesDialog } from "@/components/settings/UnsavedChangesDialog";
import { useSettingsDraftStatus } from "@/contexts/SettingsDraftContext";

export function SettingsPage() {
  const { t } = useTranslation();
  const [, navigate] = useLocation();
  const { data: settingsData } = useSettings();
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
  } = useSettingsDraft();

  // Local UI state — dialogs and pending navigation target for UX-01
  const [resetDialogOpen, setResetDialogOpen] = useState(false);
  const [unsavedDialogOpen, setUnsavedDialogOpen] = useState(false);
  const [pendingNav, setPendingNav] = useState<string | null>(null);

  // Stable callback for useUnsavedGuard — fires when the guard
  // intercepts a nav. Stores the destination and opens the dialog.
  const handleShowUnsavedDialog = useCallback((to: string) => {
    setPendingNav(to);
    setUnsavedDialogOpen(true);
  }, []);

  useUnsavedGuard(isDirty, handleShowUnsavedDialog);

  // Sync draft dirty-state into the App-level context so NavBar can read it
  // (D-13, D-14). Cleanup sets dirty=false on unmount so navigating off
  // /settings immediately clears the NavBar's disabled state.
  const draftStatus = useSettingsDraftStatus();
  useEffect(() => {
    draftStatus?.setDirty(isDirty);
    return () => {
      draftStatus?.setDirty(false);
    };
  }, [isDirty, draftStatus]);

  // ----- Error and loading states -----
  if (isLoading) {
    // ThemeProvider already shows a global skeleton during the initial
    // settings fetch, so in practice we rarely hit this branch. Kept
    // as a belt-and-braces fallback for edge cases.
    return null;
  }
  if (isError || !draft) {
    return (
      <div className="max-w-7xl mx-auto px-6 pt-4 pb-8 space-y-8">
        <h1 className="text-3xl font-semibold">
          {t("settings.error.heading")}
        </h1>
        <p className="mt-4 text-base text-muted-foreground">
          {t("settings.error.body")}
        </p>
      </div>
    );
  }

  // ----- Save flow with toast wiring (UX-02) -----
  const handleSave = async () => {
    try {
      await save();
      toast.success(t("settings.toasts.saved"));
    } catch (err) {
      const detail =
        err instanceof Error ? err.message : "Unknown error";
      toast.error(t("settings.toasts.save_error", { detail }));
    }
  };

  // ----- Reset flow (D-12) -----
  const handleResetConfirm = async () => {
    try {
      await resetToDefaults();
      toast.success(t("settings.toasts.reset_success"));
      setResetDialogOpen(false);
    } catch (err) {
      const detail =
        err instanceof Error ? err.message : "Unknown error";
      toast.error(t("settings.toasts.reset_error", { detail }));
      setResetDialogOpen(false);
    }
  };

  // ----- Unsaved-guard: Stay and Discard & leave handlers -----
  const handleStay = () => {
    setUnsavedDialogOpen(false);
    setPendingNav(null);
  };

  const handleDiscardAndLeave = () => {
    discard(); // revert draft + cache
    setUnsavedDialogOpen(false);
    const to = pendingNav;
    setPendingNav(null);
    if (to === "__back__") {
      // useUnsavedGuard already pushed /settings back onto history to keep
      // the user on the page while the dialog was open. To actually navigate
      // back we need to go(-2): once to undo our pushState and once more to
      // perform the original back navigation the user triggered.
      window.history.go(-2);
    } else if (to) {
      navigate(to);
    }
  };

  // ----- Contrast pair inputs (BRAND-08, D-21, D-22) -----
  // Primary/primary-foreground: primary comes from draft (hex), and
  // primary-foreground is read from :root CSS var at render time. We
  // MUST NOT write primary-foreground ourselves — it's a derived token
  // maintained by index.css. getComputedStyle returns whatever value
  // index.css has set (e.g. "oklch(0.985 0 0)").
  const primaryFg = (
    typeof window !== "undefined"
      ? getComputedStyle(document.documentElement)
          .getPropertyValue("--primary-foreground")
          .trim()
      : ""
  ) || WHITE_OKLCH;

  // Helper: a strongly-typed setter that routes through setField
  const setDraftField = <K extends keyof DraftFields>(
    field: K,
    value: DraftFields[K],
  ) => setField(field, value);

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-32 space-y-8">
      {/* pb-32 reserves vertical space so the sticky ActionBar never overlaps the last card */}
      <header className="mb-12">
        <h1 className="text-3xl font-semibold leading-tight">
          {t("settings.page_title")}
        </h1>
      </header>

      {/* General Card — merges identity + colors as subsections */}
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
                onChange={(e) => setDraftField("app_name", e.target.value)}
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
            <h3 className="text-base font-semibold">
              {t("settings.colors.title")}
            </h3>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            <ColorPicker
              label={t("settings.colors.primary")}
              value={draft.color_primary}
              onChange={(hex) => setDraftField("color_primary", hex)}
              contrastBadge={
                <ContrastBadge
                  colorA={safeHexToOklch(draft.color_primary)}
                  colorB={primaryFg}
                />
              }
            />
            <ColorPicker
              label={t("settings.colors.accent")}
              value={draft.color_accent}
              onChange={(hex) => setDraftField("color_accent", hex)}
            />
            <ColorPicker
              label={t("settings.colors.background")}
              value={draft.color_background}
              onChange={(hex) => setDraftField("color_background", hex)}
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
              onChange={(hex) => setDraftField("color_foreground", hex)}
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
              onChange={(hex) => setDraftField("color_muted", hex)}
            />
            <ColorPicker
              label={t("settings.colors.destructive")}
              value={draft.color_destructive}
              onChange={(hex) => setDraftField("color_destructive", hex)}
              contrastBadge={
                <ContrastBadge
                  colorA={safeHexToOklch(draft.color_destructive)}
                  colorB={WHITE_OKLCH}
                />
              }
            />
            </div>
          </section>
        </CardContent>
      </Card>

      {/* HR Card — embeds Personio + Sollwerte as subsections */}
      <Card>
        <CardHeader>
          <CardTitle className="text-xl font-semibold">
            {t("settings.hr.title")}
          </CardTitle>
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

      {/* Phase 40-02 — admin-only link to /settings/sensors */}
      <AdminOnly>
        <Card>
          <CardHeader>
            <CardTitle className="text-xl font-semibold">
              {t("settings.sensors_link.title")}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-4">
              {t("settings.sensors_link.body")}
            </p>
            <Link
              to="/settings/sensors"
              className={buttonVariants({ variant: "outline" })}
            >
              <Thermometer className="h-4 w-4 mr-1" aria-hidden="true" />
              {t("settings.sensors_link.cta")}
            </Link>
          </CardContent>
        </Card>
      </AdminOnly>

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
          // If the Dialog is closed via Escape key / backdrop click,
          // treat it as "Stay" — do not navigate.
          if (!open) handleStay();
        }}
        onStay={handleStay}
        onDiscardAndLeave={handleDiscardAndLeave}
      />
    </div>
  );
}

/**
 * Wraps hexToOklch to swallow errors mid-typing so the contrast badge
 * for the primary/destructive pickers doesn't crash the render when
 * the user has a half-typed hex. Returns oklch(0 0 0) as a safe fallback.
 */
function safeHexToOklch(hex: string): string {
  try {
    return hexToOklch(hex);
  } catch {
    return "oklch(0 0 0)";
  }
}
