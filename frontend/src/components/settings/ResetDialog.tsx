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

export interface ResetDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Fired when user clicks the Reset confirm button. Caller runs resetToDefaults + toast. */
  onConfirm: () => void;
  /** True while the reset mutation is in flight — disables buttons. */
  isPending?: boolean;
}

/**
 * Confirm dialog for "Reset to defaults" (SET-04 UI surface, D-12).
 * Uses destructive variant on the confirm button because reset is
 * irreversible and also clears the uploaded logo.
 */
export function ResetDialog({
  open,
  onOpenChange,
  onConfirm,
  isPending = false,
}: ResetDialogProps) {
  const { t } = useTranslation();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent showCloseButton={false}>
        <DialogHeader>
          <DialogTitle>{t("settings.reset_dialog.title")}</DialogTitle>
          <DialogDescription>
            {t("settings.reset_dialog.body")}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            type="button"
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={isPending}
          >
            {t("settings.reset_dialog.cancel")}
          </Button>
          <Button
            type="button"
            variant="destructive"
            onClick={onConfirm}
            disabled={isPending}
          >
            {t("settings.reset_dialog.confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
