import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Code, FileText, Link as LinkIcon, Presentation } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { signageKeys } from "@/lib/queryKeys";
import { signageApi } from "@/signage/lib/signageApi";
import type { SignageMedia } from "@/signage/lib/signageTypes";

const DIRECTUS_URL =
  (import.meta.env.VITE_DIRECTUS_URL as string | undefined) ??
  "http://localhost:8055";

function thumbnailUrl(media: SignageMedia): string | null {
  if (
    (media.kind === "image" || media.kind === "video") &&
    media.uri
  ) {
    return `${DIRECTUS_URL}/assets/${media.uri}`;
  }
  return null;
}

function PlaceholderIcon({ kind }: { kind: SignageMedia["kind"] }) {
  const cls = "w-10 h-10 text-muted-foreground";
  switch (kind) {
    case "pdf":
      return <FileText className={cls} aria-hidden />;
    case "url":
      return <LinkIcon className={cls} aria-hidden />;
    case "html":
      return <Code className={cls} aria-hidden />;
    case "pptx":
      return <Presentation className={cls} aria-hidden />;
    default:
      return <FileText className={cls} aria-hidden />;
  }
}

export interface MediaPickerDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onPick: (media: SignageMedia) => void;
}

/**
 * Phase 46 Plan 46-05 — picker grid for adding a media row to a playlist.
 *
 * Fetches the same /api/signage/media list the Media tab uses (cached
 * under signageKeys.media()) and lets the admin filter by title client-side.
 * Clicking a card fires `onPick(media)` and closes the dialog.
 */
export function MediaPickerDialog({
  open,
  onOpenChange,
  onPick,
}: MediaPickerDialogProps) {
  const { t } = useTranslation();
  const [search, setSearch] = useState("");

  const { data: media = [], isLoading } = useQuery({
    queryKey: signageKeys.media(),
    queryFn: signageApi.listMedia,
    enabled: open,
  });

  const term = search.trim().toLowerCase();
  const filtered = term
    ? media.filter((m) => m.title.toLowerCase().includes(term))
    : media;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-3xl">
        <DialogHeader>
          <DialogTitle>{t("signage.admin.editor.add_item")}</DialogTitle>
        </DialogHeader>

        <Input
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder={t("signage.admin.tag_picker.placeholder")}
          aria-label={t("signage.admin.editor.add_item")}
          className="mb-3"
        />

        {isLoading ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            {t("signage.admin.error.loading")}
          </div>
        ) : filtered.length === 0 ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            {t("signage.admin.media.empty_title")}
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-3 max-h-[60vh] overflow-y-auto">
            {filtered.map((m) => {
              const thumb = thumbnailUrl(m);
              return (
                <Button
                  key={m.id}
                  type="button"
                  variant="outline"
                  onClick={() => {
                    onPick(m);
                    onOpenChange(false);
                  }}
                  className="h-auto flex-col items-stretch p-2 text-left hover:border-primary whitespace-normal"
                >
                  <div className="aspect-video w-full rounded bg-muted overflow-hidden flex items-center justify-center mb-2">
                    {thumb ? (
                      <img
                        src={thumb}
                        alt=""
                        className="w-full h-full object-cover"
                      />
                    ) : (
                      <PlaceholderIcon kind={m.kind} />
                    )}
                  </div>
                  <div className="text-sm font-medium truncate" title={m.title}>
                    {m.title}
                  </div>
                  <div className="text-xs text-muted-foreground">{m.kind}</div>
                </Button>
              );
            })}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
