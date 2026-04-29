import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { toast } from "sonner";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { signageKeys } from "@/lib/queryKeys";
import { signageApi } from "@/signage/lib/signageApi";

export interface PlaylistNewDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Phase 46 Plan 46-05 — minimal "New playlist" dialog.
 *
 * Creates a playlist with just `name` (backend ignores tag_ids on create —
 * see signageApi createPlaylist note), then redirects to the editor where
 * tags + items are managed.
 */
export function PlaylistNewDialog({ open, onOpenChange }: PlaylistNewDialogProps) {
  const { t } = useTranslation();
  const [, navigate] = useLocation();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");

  const createMutation = useMutation({
    mutationFn: (n: string) => signageApi.createPlaylist({ name: n }),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: signageKeys.playlists() });
      onOpenChange(false);
      setName("");
      navigate(`/signage/playlists/${created.id}`);
    },
    onError: (err) => {
      const detail = err instanceof Error ? err.message : "Unknown error";
      toast.error(
        t("signage.admin.editor.save_error", { detail }),
      );
    },
  });

  const trimmed = name.trim();
  const canSubmit = trimmed.length > 0 && !createMutation.isPending;

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!canSubmit) return;
    createMutation.mutate(trimmed);
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o && createMutation.isPending) return;
        if (!o) setName("");
        onOpenChange(o);
      }}
    >
      <DialogContent>
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>
              {t("signage.admin.playlists.new_button")}
            </DialogTitle>
            <DialogDescription>
              {t("signage.admin.playlists.empty_body")}
            </DialogDescription>
          </DialogHeader>
          <div className="py-4 space-y-2">
            <Label htmlFor="playlist-name">
              {t("signage.admin.editor.name_placeholder")}
            </Label>
            <Input
              id="playlist-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder={t("signage.admin.editor.name_placeholder")}
              autoFocus
              required
              maxLength={128}
            />
          </div>
          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={createMutation.isPending}
            >
              {t("signage.admin.editor.cancel")}
            </Button>
            <Button type="submit" disabled={!canSubmit}>
              {t("signage.admin.editor.save")}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
