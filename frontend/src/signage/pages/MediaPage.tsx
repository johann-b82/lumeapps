import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Code, FileText, Link as LinkIcon, Presentation } from "lucide-react";

import { signageKeys } from "@/lib/queryKeys";
import { getAccessToken } from "@/lib/apiClient";
import {
  ApiErrorWithBody,
  signageApi,
} from "@/signage/lib/signageApi";
import type { SignageMedia } from "@/signage/lib/signageTypes";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { DeleteButton } from "@/components/ui/delete-button";
import { MediaUploadDropZone } from "@/signage/components/MediaUploadDropZone";
import { MediaRegisterUrlForm } from "@/signage/components/MediaRegisterUrlForm";
import { MediaStatusPill } from "@/signage/components/MediaStatusPill";
import { MediaInUseDialog } from "@/signage/components/MediaInUseDialog";

const DIRECTUS_URL =
  (import.meta.env.VITE_DIRECTUS_URL as string | undefined) ??
  (typeof window !== "undefined"
    ? `${window.location.origin}/directus`
    : "http://localhost/directus");

function thumbnailUrl(media: SignageMedia): string | null {
  if (
    (media.kind === "image" || media.kind === "video") &&
    media.uri
  ) {
    const token = getAccessToken();
    const qs = token ? `?access_token=${encodeURIComponent(token)}` : "";
    return `${DIRECTUS_URL}/assets/${media.uri}${qs}`;
  }
  return null;
}

function PlaceholderIcon({ kind }: { kind: SignageMedia["kind"] }) {
  const className = "w-10 h-10 text-muted-foreground";
  switch (kind) {
    case "pdf":
      return <FileText className={className} aria-hidden />;
    case "url":
      return <LinkIcon className={className} aria-hidden />;
    case "html":
      return <Code className={className} aria-hidden />;
    case "pptx":
      return <Presentation className={className} aria-hidden />;
    default:
      return <FileText className={className} aria-hidden />;
  }
}

interface InUseTarget {
  name: string;
  playlistIds: string[];
}

export function MediaPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const [inUseTarget, setInUseTarget] = useState<InUseTarget | null>(null);
  // Tracks the media currently being deleted so the 409 onError handler can
  // recover its title for the in-use dialog. Cleared on settle.
  const [pendingDelete, setPendingDelete] = useState<{
    id: string;
    title: string;
  } | null>(null);

  const mediaQuery = useQuery({
    queryKey: signageKeys.media(),
    queryFn: signageApi.listMedia,
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => signageApi.deleteMedia(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: signageKeys.media() });
      toast.success(t("signage.admin.media.delete_title"));
      setPendingDelete(null);
    },
    onError: (err: unknown) => {
      if (err instanceof ApiErrorWithBody && err.status === 409) {
        const body = err.body as { playlist_ids?: string[] } | null;
        const playlistIds = body?.playlist_ids ?? [];
        setInUseTarget({
          name: pendingDelete?.title ?? "",
          playlistIds,
        });
        setPendingDelete(null);
        return;
      }
      const message =
        err instanceof Error ? err.message : "unknown error";
      toast.error(t("signage.admin.error.generic", { detail: message }));
      setPendingDelete(null);
    },
  });

  return (
    // v1.34: top-level page header dropped — SubHeader dropdown shows the active section.
    // v1.40: unified into a single Card. Top half is the entry points (drop
    // zone + register form), an <hr> separates from the bottom half which
    // is the existing-content grid. Element chrome is flat — no per-section
    // dashed borders or muted fills — so the page reads like the settings
    // sub-pages.
    <Card>
      <CardContent className="space-y-6">
        <section aria-labelledby="add-media-heading" className="space-y-3">
          <h2 id="add-media-heading" className="text-base font-semibold">
            {t("signage.admin.media.add_section_title")}
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <MediaUploadDropZone />
            <div className="rounded-md border-2 border-border p-6">
              <MediaRegisterUrlForm />
            </div>
          </div>
        </section>

        <hr className="border-border" />

        {mediaQuery.isLoading && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, idx) => (
              <div
                key={idx}
                className="h-48 rounded-md bg-muted animate-pulse"
              />
            ))}
          </div>
        )}

        {mediaQuery.isError && (
          <p className="text-sm text-destructive">
            {t("signage.admin.error.loading")}
          </p>
        )}

        {mediaQuery.data && mediaQuery.data.length === 0 && (
          <div className="p-8 text-center">
            <h2 className="text-xl font-semibold">
              {t("signage.admin.media.empty_title")}
            </h2>
            <p className="mt-2 text-sm text-muted-foreground">
              {t("signage.admin.media.empty_body")}
            </p>
          </div>
        )}

        {mediaQuery.data && mediaQuery.data.length > 0 && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {mediaQuery.data.map((media) => {
            const thumb = thumbnailUrl(media);
            return (
              <article
                key={media.id}
                className="rounded-md border border-border bg-card overflow-hidden flex flex-col"
              >
                <div className="h-32 bg-muted flex items-center justify-center overflow-hidden">
                  {thumb ? (
                    <img
                      src={thumb}
                      alt={media.title}
                      className="h-32 object-cover w-full"
                    />
                  ) : (
                    <PlaceholderIcon kind={media.kind} />
                  )}
                </div>
                <div className="p-3 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <h3 className="text-sm font-semibold truncate">
                      {media.title}
                    </h3>
                    <Badge
                      variant="outline"
                      className="text-xs shrink-0"
                    >
                      {media.kind}
                    </Badge>
                  </div>
                  {media.kind === "pptx" && (
                    <MediaStatusPill
                      mediaId={media.id}
                      initialStatus={media.conversion_status}
                      initialError={media.conversion_error}
                    />
                  )}
                  {media.tags && media.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {media.tags.map((tag) => (
                        <Badge
                          key={tag.id}
                          variant="secondary"
                          className="text-xs"
                        >
                          {tag.name}
                        </Badge>
                      ))}
                    </div>
                  )}
                  <div className="flex justify-end pt-1">
                    <DeleteButton
                      itemLabel={media.title}
                      aria-label={t("ui.delete.ariaLabel", {
                        itemLabel: media.title,
                      })}
                      onConfirm={async () => {
                        setPendingDelete({ id: media.id, title: media.title });
                        try {
                          await deleteMutation.mutateAsync(media.id);
                        } catch {
                          // onError handles toast / 409 dialog; swallow so
                          // DeleteButton closes its own confirm dialog cleanly.
                        }
                      }}
                    />
                  </div>
                </div>
              </article>
              );
            })}
          </div>
        )}
      </CardContent>

      {/* v1.36: register form is now inline in the top-of-page grid; the
          old dialog instantiation lived here. v1.40: dialog instances stay
          outside the Card so they portal cleanly. */}
      <MediaInUseDialog
        open={!!inUseTarget}
        onOpenChange={(o) => !o && setInUseTarget(null)}
        itemLabel={inUseTarget?.name ?? ""}
        playlistIds={inUseTarget?.playlistIds ?? []}
      />
    </Card>
  );
}
