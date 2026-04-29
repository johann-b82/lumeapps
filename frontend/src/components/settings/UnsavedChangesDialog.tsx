import { useTranslation } from "react-i18next";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

export interface UnsavedChangesDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Fired when user clicks "Stay" — caller should just close the dialog. */
  onStay: () => void;
  /** Fired when user clicks "Discard & leave" — caller reverts draft then navigates. */
  onDiscardAndLeave: () => void;
}

/**
 * Confirm dialog for leaving the Settings page with unsaved changes
 * (UX-01, D-18, D-19). Shown when useUnsavedGuard intercepts a nav.
 *
 * Two actions only: Stay (cancel) and Discard & leave (destructive).
 * No "Save & leave" option — deliberately omitted per CONTEXT.md D-19.
 */
export function UnsavedChangesDialog({
  open,
  onOpenChange,
  onStay,
  onDiscardAndLeave,
}: UnsavedChangesDialogProps) {
  const { t } = useTranslation();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>{t("settings.unsaved_dialog.title")}</DialogTitle>
          <DialogDescription>
            {t("settings.unsaved_dialog.body")}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button type="button" variant="ghost" onClick={onStay}>
            {t("settings.unsaved_dialog.cancel")}
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={onDiscardAndLeave}
          >
            {t("settings.unsaved_dialog.confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
