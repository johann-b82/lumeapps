// Phase 57 Plan 05 — MediaInUseDialog
// Single-mode dialog covering the 409 "media is in use by N playlists"
// follow-up after a delete attempt is rejected (RESEARCH Pitfall 2).
// The destructive confirm branch now lives in `<DeleteButton>`; this
// narrow variant keeps the existing `signage.admin.media.delete_in_use_*`
// i18n keys verbatim.
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

export interface MediaInUseDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** Media title — currently unused in the body copy but kept for accessibility/UX hooks. */
  itemLabel: string;
  /** Playlist IDs blocking deletion. Length drives the i18n count. */
  playlistIds: string[];
}

export function MediaInUseDialog({
  open,
  onOpenChange,
  playlistIds,
}: MediaInUseDialogProps) {
  const { t } = useTranslation();
  const count = playlistIds.length;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            {t("signage.admin.media.delete_in_use_title")}
          </DialogTitle>
          <DialogDescription>
            {t("signage.admin.media.delete_in_use_body", { count })}
          </DialogDescription>
        </DialogHeader>
        <DialogFooter>
          <Button
            variant="outline"
            autoFocus
            onClick={() => onOpenChange(false)}
          >
            {t("signage.admin.media.delete_in_use_close")}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
