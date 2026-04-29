import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { Check, RotateCcw, Undo2 } from "lucide-react";
import { AdminOnly } from "@/auth/AdminOnly";

export interface ActionBarProps {
  isDirty: boolean;
  isSaving: boolean;
  onSave: () => void;
  onDiscard: () => void;
  onResetClick: () => void; // Opens the ResetDialog; actual PUT is inside the dialog flow
  /**
   * When true, the "Reset to defaults" button is not rendered. Added in
   * Phase 40-01 for /settings/sensors, which does not expose a
   * reset-everything flow (sensor CRUD is non-reversible at row level).
   * Defaults to false to preserve the original /settings behavior.
   */
  hideReset?: boolean;
}

/**
 * Sticky bottom action bar (D-09).
 * Layout:
 *   Left:  "Unsaved changes" indicator (only when isDirty)
 *   Right: [Discard (ghost, dirty-only)] [Reset to defaults (outline, always)] [Save changes (primary, disabled when pristine)]
 *
 * All three action buttons are individually wrapped with <AdminOnly> —
 * Viewer sees the ActionBar region but no buttons (settings becomes
 * effectively read-only from their perspective).
 */
export function ActionBar({
  isDirty,
  isSaving,
  onSave,
  onDiscard,
  onResetClick,
  hideReset = false,
}: ActionBarProps) {
  const { t } = useTranslation();
  return (
    <div
      role="region"
      aria-label="Save actions"
      className="fixed bottom-0 inset-x-0 bg-card border-t border-border shadow-lg z-40"
    >
      <div className="max-w-5xl mx-auto px-6 py-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2 min-h-[36px]">
          {isDirty && (
            <span className="text-sm font-medium text-muted-foreground">
              {t("settings.actions.unsaved")}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          {isDirty && (
            <AdminOnly>
              <Button
                type="button"
                variant="ghost"
                onClick={onDiscard}
                disabled={isSaving}
              >
                <Undo2 className="h-4 w-4 mr-1" aria-hidden="true" />
                {t("settings.actions.discard")}
              </Button>
            </AdminOnly>
          )}
          {!hideReset && (
            <AdminOnly>
              <Button
                type="button"
                variant="outline"
                onClick={onResetClick}
                disabled={isSaving}
              >
                <RotateCcw className="h-4 w-4 mr-1" aria-hidden="true" />
                {t("settings.actions.reset")}
              </Button>
            </AdminOnly>
          )}
          <AdminOnly>
            <Button
              type="button"
              variant="default"
              onClick={onSave}
              disabled={!isDirty || isSaving}
            >
              <Check className="h-4 w-4 mr-1" aria-hidden="true" />
              {t("settings.actions.save")}
            </Button>
          </AdminOnly>
        </div>
      </div>
    </div>
  );
}
