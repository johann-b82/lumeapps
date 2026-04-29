import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export interface UnsavedChangesDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /**
   * Fired when the admin clicks "Discard" — caller resets form + closes parent
   * (and may also navigate away). Either supply this OR the legacy
   * onStay+onDiscardAndLeave pair.
   */
  onConfirm?: () => void;
  /** Legacy API kept for 46-06 (DeviceEditDialog) compatibility. */
  onStay?: () => void;
  onDiscardAndLeave?: () => void;
}

/**
 * Signage-local dirty-guard dialog (D-09: SGN-ADM-09). Used by:
 *   - Plan 46-05 PlaylistEditorPage when navigating away from a dirty editor.
 *   - Plan 46-06 DeviceEditDialog when closing the modal with unsaved changes.
 *
 * Uses the dedicated `signage.admin.unsaved.*` i18n namespace (added by 46-01)
 * so signage-side copy can evolve independently of the settings dialog.
 *
 * API: prefer the `onConfirm` shape; the `onStay` + `onDiscardAndLeave` pair
 * is preserved for 46-06's existing call site (parallel-execution safety).
 */
export function UnsavedChangesDialog({
  open,
  onOpenChange,
  onConfirm,
  onStay,
  onDiscardAndLeave,
}: UnsavedChangesDialogProps) {
  const { t } = useTranslation();

  const handleStay = () => {
    if (onStay) onStay();
    else onOpenChange(false);
  };

  const handleConfirm = () => {
    if (onDiscardAndLeave) onDiscardAndLeave();
    else if (onConfirm) {
      onConfirm();
      onOpenChange(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>{t("signage.admin.unsaved.title")}</DialogTitle>
          <DialogDescription>
            {t("signage.admin.unsaved.body")}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={handleStay}>
            {t("signage.admin.unsaved.cancel")}
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={handleConfirm}
          >
            {t("signage.admin.unsaved.confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
