import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { toast } from "sonner";
import { Pencil, Copy } from "lucide-react";

import { signageKeys } from "@/lib/queryKeys";
import { signageApi, ApiErrorWithBody } from "@/signage/lib/signageApi";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { SectionHeader } from "@/components/ui/section-header";
import { DeleteButton } from "@/components/ui/delete-button";
import { PlaylistNewDialog } from "@/signage/components/PlaylistNewDialog";
import type { SignagePlaylist } from "@/signage/lib/signageTypes";

/**
 * Phase 46 Plan 46-05 — Playlists list page (SGN-ADM-05).
 *
 * Phase 57 Plan 57-06 migration — adds SectionHeader at the top, replaces
 * the row Trash trigger with the standardized <DeleteButton>, and DELETES
 * the inline `<Dialog>` block (the fourth ad-hoc delete variant identified
 * by RESEARCH Pitfall 1).
 *
 * Renders a table of all playlists with Edit / Duplicate / Delete actions
 * and a "New playlist" CTA in the page-level button area.
 *
 * Notes on backend response shape (verified):
 *   - GET /api/signage/playlists returns `SignagePlaylistRead[]` — does NOT
 *     include nested tags or item counts. We therefore omit the items
 *     count column (tracked as tech debt to add a `_count` field). Tags
 *     are also not surfaced here; the editor exposes tag editing.
 *   - Duplicate clones name+description+priority. Items are NOT carried
 *     over (kept simple per plan; the admin can add items in the editor).
 */
export function PlaylistsPage() {
  const { t, i18n } = useTranslation();
  const [, navigate] = useLocation();
  const queryClient = useQueryClient();

  const [newOpen, setNewOpen] = useState(false);

  const { data: playlists = [], isLoading, isError } = useQuery({
    queryKey: signageKeys.playlists(),
    queryFn: signageApi.listPlaylists,
  });

  const duplicateMutation = useMutation({
    mutationFn: async (source: SignagePlaylist) => {
      // Clone metadata only — items are NOT copied (plan documents this choice).
      return signageApi.createPlaylist({
        name: `${source.name} (copy)`,
        description: source.description ?? null,
        priority: source.priority,
        enabled: source.enabled,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: signageKeys.playlists() });
      toast.success(t("signage.admin.editor.saved"));
    },
    onError: (err) => {
      const detail = err instanceof Error ? err.message : "Unknown error";
      toast.error(t("signage.admin.editor.save_error", { detail }));
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => signageApi.deletePlaylist(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: signageKeys.playlists() });
      toast.success(t("signage.admin.editor.saved"));
    },
    onError: (err) => {
      // Phase 52 D-13: detect 409 { detail, schedule_ids } and deep-link to
      // the Schedules tab with ?highlight=<ids> so the operator can fix the
      // referring schedules first.
      if (
        err instanceof ApiErrorWithBody &&
        err.status === 409 &&
        err.body &&
        typeof err.body === "object" &&
        "schedule_ids" in err.body &&
        Array.isArray((err.body as { schedule_ids: unknown }).schedule_ids)
      ) {
        const scheduleIds = (err.body as { schedule_ids: string[] })
          .schedule_ids;
        toast.error(
          t("signage.admin.playlists.error.schedules_active_title"),
          {
            description: t(
              "signage.admin.playlists.error.schedules_active_body",
            ),
            action: {
              label: t("signage.admin.nav.schedules"),
              onClick: () =>
                navigate(
                  `/signage/schedules?highlight=${scheduleIds.join(",")}`,
                ),
            },
          },
        );
        return;
      }
      const detail = err instanceof Error ? err.message : "Unknown error";
      toast.error(t("signage.admin.editor.save_error", { detail }));
    },
  });

  const dateFmt = new Intl.DateTimeFormat(i18n.language, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });

  return (
    <section className="space-y-4">
      <SectionHeader
        title={t("section.signage.playlists.title")}
        description={t("section.signage.playlists.description")}
        className="mt-8"
      />

      {isLoading ? (
        <div className="rounded-md border border-border bg-card p-6 text-sm text-muted-foreground">
          {t("signage.admin.error.loading")}
        </div>
      ) : isError ? (
        <div className="rounded-md border border-border bg-card p-6 text-sm text-destructive">
          {t("signage.admin.error.generic")}
        </div>
      ) : playlists.length === 0 ? (
        <div className="rounded-md border border-border bg-card p-12 text-center space-y-3">
          <h2 className="text-lg font-semibold">
            {t("signage.admin.playlists.empty_title")}
          </h2>
          <p className="text-sm text-muted-foreground">
            {t("signage.admin.playlists.empty_body")}
          </p>
          <Button type="button" onClick={() => setNewOpen(true)}>
            {t("signage.admin.playlists.empty_cta")}
          </Button>
        </div>
      ) : (
        <div className="rounded-md border border-border bg-card overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>{t("signage.admin.playlists.col_name")}</TableHead>
                <TableHead>{t("signage.admin.playlists.col_created")}</TableHead>
                <TableHead className="text-right">
                  {t("signage.admin.playlists.col_actions")}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {playlists.map((p) => (
                <TableRow key={p.id}>
                  <TableCell className="font-medium">{p.name}</TableCell>
                  <TableCell className="text-muted-foreground">
                    {dateFmt.format(new Date(p.created_at))}
                  </TableCell>
                  <TableCell className="text-right space-x-1">
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => navigate(`/signage/playlists/${p.id}`)}
                      aria-label={`Edit ${p.name}`}
                    >
                      <Pencil className="w-4 h-4" />
                    </Button>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => duplicateMutation.mutate(p)}
                      disabled={duplicateMutation.isPending}
                      aria-label={`Duplicate ${p.name}`}
                    >
                      <Copy className="w-4 h-4" />
                    </Button>
                    <DeleteButton
                      itemLabel={p.name}
                      onConfirm={async () => {
                        await deleteMutation.mutateAsync(p.id);
                      }}
                      aria-label={t("ui.delete.ariaLabel", { itemLabel: p.name })}
                    />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      )}

      {playlists.length > 0 && (
        <div className="flex justify-end">
          <Button type="button" onClick={() => setNewOpen(true)}>
            {t("signage.admin.playlists.new_button")}
          </Button>
        </div>
      )}

      <PlaylistNewDialog open={newOpen} onOpenChange={setNewOpen} />
    </section>
  );
}
