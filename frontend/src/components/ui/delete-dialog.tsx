import type { ReactNode } from "react";
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

export interface DeleteDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title?: string;
  body: ReactNode;
  cancelLabel?: string;
  confirmLabel?: string;
  onConfirm: () => void | Promise<void>;
  confirmDisabled?: boolean;
}

export function DeleteDialog({
  open,
  onOpenChange,
  title,
  body,
  cancelLabel,
  confirmLabel,
  onConfirm,
  confirmDisabled,
}: DeleteDialogProps) {
  const { t } = useTranslation();
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{title ?? t("ui.delete.title")}</DialogTitle>
          <DialogDescription render={<div />}>{body}</DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="outline"
            autoFocus
            onClick={() => onOpenChange(false)}
          >
            {cancelLabel ?? t("ui.delete.cancel")}
          </Button>
          <Button
            variant="destructive"
            disabled={confirmDisabled}
            onClick={() => void onConfirm()}
          >
            {confirmLabel ?? t("ui.delete.confirm")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
