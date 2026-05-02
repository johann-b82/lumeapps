import { useCallback, useEffect, useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useForm, Controller, useWatch } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useLocation, useParams } from "wouter";
import { toast } from "sonner";
import { Loader2, Plus } from "lucide-react";

import { signageKeys } from "@/lib/queryKeys";
import { getAccessToken } from "@/lib/apiClient";
import { signageApi } from "@/signage/lib/signageApi";
import type {
  SignageMedia,
  SignagePlaylistItem,
} from "@/signage/lib/signageTypes";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useUnsavedGuard } from "@/hooks/useUnsavedGuard";
import { TagPicker } from "@/signage/components/TagPicker";
import {
  PlaylistItemList,
  type PlaylistItemFormState,
  type PlaylistItemTransition,
} from "@/signage/components/PlaylistItemList";
import { MediaPickerDialog } from "@/signage/components/MediaPickerDialog";
import { UnsavedChangesDialog } from "@/signage/components/UnsavedChangesDialog";
import { PlayerRenderer } from "@/signage/player/PlayerRenderer";
import type { PlayerItem, PlayerItemKind } from "@/signage/player/types";

const DIRECTUS_URL =
  (import.meta.env.VITE_DIRECTUS_URL as string | undefined) ??
  (typeof window !== "undefined"
    ? `${window.location.origin}/directus`
    : "http://localhost/directus");

interface FormValues {
  name: string;
  tags: string[]; // tag names; resolved to ids on save (create-on-submit)
  items: PlaylistItemFormState[];
}

function resolveMediaUri(media: SignageMedia): string | null {
  if (!media.uri) return null;
  if (media.kind === "url") return media.uri;
  const token = getAccessToken();
  const qs = token ? `?access_token=${encodeURIComponent(token)}` : "";
  return `${DIRECTUS_URL}/assets/${media.uri}${qs}`;
}

function generateKey(): string {
  if (
    typeof crypto !== "undefined" &&
    typeof crypto.randomUUID === "function"
  ) {
    return crypto.randomUUID();
  }
  return `k-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

function toFormItem(
  it: SignagePlaylistItem,
): PlaylistItemFormState {
  const t =
    it.transition === "cut" ? "cut" : ("fade" as PlaylistItemTransition);
  return {
    key: generateKey(),
    media_id: it.media_id,
    duration_s: it.duration_s,
    transition: t,
  };
}

/**
 * Phase 46 Plan 46-05 — playlist editor (SGN-ADM-05 + SGN-DIFF-02 + SGN-ADM-09).
 *
 * Two-pane layout: left = item list + drag-reorder + duration/transition
 * inline edit; right = WYSIWYG preview powered by PlayerRenderer reading
 * the in-memory form state via useWatch (Pitfall 9 — preview MUST come
 * from form state, not server state, otherwise the preview lags the user
 * by one save cycle).
 *
 * Save path:
 *   1. Resolve tag names → ids (create-on-submit via signageApi.createTag).
 *   2. PATCH /playlists/{id}                 — name only (backend ignores tag_ids).
 *   3. PUT   /playlists/{id}/tags            — bulk-replace tag set.
 *   4. PUT   /playlists/{id}/items           — bulk-replace items in order.
 *
 * Dirty guard: useUnsavedGuard with scopePath="/signage/playlists/{id}".
 * Pending nav captured in local state; UnsavedChangesDialog confirms.
 */
export function PlaylistEditorPage() {
  const { t, i18n } = useTranslation();
  const params = useParams<{ id: string }>();
  const id = params.id;
  const [, navigate] = useLocation();
  const queryClient = useQueryClient();

  // ---- Data fetch (playlist meta + items + media list for join + tags) ----
  const { data, isLoading, isError } = useQuery({
    queryKey: signageKeys.playlistItem(id),
    queryFn: async () => {
      const [playlist, items, media, tags] = await Promise.all([
        signageApi.getPlaylist(id),
        signageApi.listPlaylistItems(id),
        signageApi.listMedia(),
        signageApi.listTags(),
      ]);
      return { playlist, items, media, tags };
    },
    enabled: !!id,
  });

  const mediaLookup = useMemo(() => {
    const m = new Map<string, SignageMedia>();
    if (data?.media) for (const x of data.media) m.set(x.id, x);
    return m;
  }, [data?.media]);

  // ---- Form ----
  const form = useForm<FormValues>({
    defaultValues: { name: "", tags: [], items: [] },
  });

  // Hydrate form once data lands.
  useEffect(() => {
    if (!data) return;
    const tagIds = data.playlist.tag_ids ?? [];
    const idToName = new Map(data.tags.map((tag) => [tag.id, tag.name]));
    const tagNames = tagIds
      .map((tid) => idToName.get(tid))
      .filter((n): n is string => typeof n === "string");
    form.reset({
      name: data.playlist.name,
      tags: tagNames,
      items: data.items.map(toFormItem),
    });
  }, [data, form]);

  // Live preview source (Pitfall 9): items from form state, NOT server.
  const formItems =
    useWatch({ control: form.control, name: "items" }) ??
    ([] as PlaylistItemFormState[]);

  const previewItems = useMemo<PlayerItem[]>(() => {
    const out: PlayerItem[] = [];
    for (const it of formItems) {
      const media = mediaLookup.get(it.media_id);
      if (!media) continue;
      const kind = media.kind as PlayerItemKind;
      out.push({
        id: it.key,
        kind,
        uri: resolveMediaUri(media),
        html: media.html_content,
        slide_paths: media.slide_paths,
        duration_s: it.duration_s,
        transition: it.transition,
      });
    }
    return out;
  }, [formItems, mediaLookup]);

  // ---- Save ----
  const saveMutation = useMutation({
    mutationFn: async (values: FormValues) => {
      // Resolve tag names → ids (create-on-submit per D-15).
      const existing = await signageApi.listTags();
      const nameToId = new Map(existing.map((tag) => [tag.name, tag.id]));
      const tagIds: number[] = [];
      for (const name of values.tags) {
        let tid = nameToId.get(name);
        if (tid === undefined) {
          const created = await signageApi.createTag(name);
          tid = created.id;
        }
        tagIds.push(tid);
      }
      await signageApi.updatePlaylist(id, { name: values.name });
      await signageApi.replacePlaylistTags(id, tagIds);
      await signageApi.bulkReplaceItems(
        id,
        values.items.map((it, idx) => ({
          media_id: it.media_id,
          position: idx,
          duration_s: it.duration_s,
          transition: it.transition,
        })),
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: signageKeys.playlists() });
      queryClient.invalidateQueries({ queryKey: signageKeys.playlistItem(id) });
      queryClient.invalidateQueries({ queryKey: signageKeys.tags() });
      toast.success(t("signage.admin.editor.saved"));
      // Reset dirty without losing values.
      form.reset(form.getValues());
    },
    onError: (err: unknown) => {
      const detail = err instanceof Error ? err.message : String(err);
      toast.error(t("signage.admin.editor.save_error", { detail }));
    },
  });

  // ---- Dirty guard (Pitfall 2: scopePath must be the exact editor URL) ----
  const isDirty = form.formState.isDirty;
  const [pendingNav, setPendingNav] = useState<string | null>(null);
  const [unsavedOpen, setUnsavedOpen] = useState(false);

  const handleShowUnsavedDialog = useCallback((to: string) => {
    setPendingNav(to);
    setUnsavedOpen(true);
  }, []);

  useUnsavedGuard(
    isDirty,
    handleShowUnsavedDialog,
    `/signage/playlists/${id}`,
  );

  function onConfirmDiscard() {
    form.reset();
    const to = pendingNav;
    setPendingNav(null);
    setUnsavedOpen(false);
    if (to === "__back__") {
      // useUnsavedGuard pushed the editor URL back onto history to keep us
      // visually on the page; go(-2) undoes that and replays the original
      // back navigation.
      window.history.go(-2);
    } else if (to) {
      navigate(to);
    }
  }

  // ---- Add / remove media ----
  const [pickerOpen, setPickerOpen] = useState(false);
  const handleAddMedia = (media: SignageMedia) => {
    const next: PlaylistItemFormState = {
      key: generateKey(),
      media_id: media.id,
      duration_s: 10,
      transition: "fade",
    };
    form.setValue("items", [...formItems, next], { shouldDirty: true });
  };
  const handleRemove = (key: string) => {
    form.setValue(
      "items",
      formItems.filter((i) => i.key !== key),
      { shouldDirty: true },
    );
  };
  const handleItemsChange = (next: PlaylistItemFormState[]) => {
    form.setValue("items", next, { shouldDirty: true });
  };

  // ---- Render ----
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-32">
        <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
      </div>
    );
  }
  if (isError || !data) {
    return (
      <div className="px-6 pt-4">
        <div className="rounded-md border border-border bg-card p-6 text-sm text-destructive">
          {t("signage.admin.error.generic")}
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-16">
      <header className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between mb-4">
        <div className="flex flex-1 items-end gap-6 min-w-0">
          <div className="flex-1 min-w-0">
            <Label className="text-xs text-muted-foreground">
              {t("signage.admin.editor.name_prefix")}
            </Label>
            <Input
              {...form.register("name", { required: true, maxLength: 128 })}
              placeholder={t("signage.admin.editor.name_placeholder")}
              aria-label={t("signage.admin.editor.name_placeholder")}
            />
          </div>
          <div className="flex-1 min-w-0 max-w-md">
            <Label className="text-xs text-muted-foreground">
              {t("signage.admin.pair.tags_label")}
            </Label>
            <Controller
              name="tags"
              control={form.control}
              render={({ field }) => (
                <TagPicker
                  value={field.value}
                  onChange={(next) =>
                    form.setValue("tags", next, { shouldDirty: true })
                  }
                  placeholder={t("signage.admin.pair.tags_placeholder")}
                  ariaLabel={t("signage.admin.pair.tags_label")}
                />
              )}
            />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="outline"
            onClick={() => form.reset()}
            disabled={!isDirty || saveMutation.isPending}
          >
            {t("signage.admin.editor.cancel")}
          </Button>
          <Button
            type="button"
            onClick={form.handleSubmit((values) =>
              saveMutation.mutate(values),
            )}
            disabled={!isDirty || saveMutation.isPending}
          >
            {saveMutation.isPending && (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            )}
            {t("signage.admin.editor.save")}
          </Button>
        </div>
      </header>

      <div className="space-y-6 mt-4">
        <section>
          <h2 className="text-base font-semibold">
            {t("signage.admin.editor.preview_title")}
          </h2>
          <p className="text-xs text-muted-foreground mb-2" lang={i18n.language}>
            {t("signage.admin.editor.preview_help")}
          </p>
          <div className="rounded-lg border border-border overflow-hidden aspect-video bg-background">
            <PlayerRenderer items={previewItems} />
          </div>
        </section>

        <section className="space-y-3">
          <div>
            <h2 className="text-base font-semibold">
              {t("signage.admin.editor.items_title")}
            </h2>
            <p className="text-xs text-muted-foreground" lang={i18n.language}>
              {t("signage.admin.editor.items_help")}
            </p>
          </div>
          {formItems.length === 0 ? (
            <div className="rounded-md border border-border bg-card p-6 text-center space-y-2">
              <p className="text-sm font-medium">
                {t("signage.admin.editor.empty_title")}
              </p>
              <p className="text-sm text-muted-foreground">
                {t("signage.admin.editor.empty_body")}
              </p>
            </div>
          ) : (
            <PlaylistItemList
              items={formItems}
              mediaLookup={mediaLookup}
              onChange={handleItemsChange}
              onRemove={handleRemove}
            />
          )}
          <Button
            type="button"
            variant="outline"
            onClick={() => setPickerOpen(true)}
            className="w-full"
          >
            <Plus className="w-4 h-4 mr-2" />
            {t("signage.admin.editor.add_item")}
          </Button>
        </section>
      </div>

      <MediaPickerDialog
        open={pickerOpen}
        onOpenChange={setPickerOpen}
        onPick={handleAddMedia}
      />

      <UnsavedChangesDialog
        open={unsavedOpen}
        onOpenChange={(o) => {
          if (!o) {
            setUnsavedOpen(false);
            setPendingNav(null);
          }
        }}
        onConfirm={onConfirmDiscard}
      />
    </div>
  );
}
