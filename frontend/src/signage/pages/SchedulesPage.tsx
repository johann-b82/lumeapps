import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "sonner";
import { Pencil } from "lucide-react";

import { signageKeys } from "@/lib/queryKeys";
import { signageApi } from "@/signage/lib/signageApi";
import type { SignageSchedule } from "@/signage/lib/signageTypes";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";
import { SectionHeader } from "@/components/ui/section-header";
import { DeleteButton } from "@/components/ui/delete-button";
import { ScheduleEditDialog } from "@/signage/components/ScheduleEditDialog";
import {
  hhmmToString,
  weekdayMaskToArray,
} from "@/signage/lib/scheduleAdapters";
import { useAdminSignageEvents } from "@/signage/lib/useAdminSignageEvents";

const WEEKDAY_KEYS = [
  "signage.admin.schedules.weekday.mo",
  "signage.admin.schedules.weekday.tu",
  "signage.admin.schedules.weekday.we",
  "signage.admin.schedules.weekday.th",
  "signage.admin.schedules.weekday.fr",
  "signage.admin.schedules.weekday.sa",
  "signage.admin.schedules.weekday.su",
] as const;

/**
 * Phase 52 Plan 02 — Schedules admin list page (SGN-SCHED-UI-01).
 *
 * Table sorted priority desc, then updated_at desc (D-01). Inline enabled
 * Switch fires an optimistic PATCH (D-02): snapshot cache, flip locally,
 * await signageApi.updateSchedule; on error restore snapshot + toast.
 *
 * Highlight (D-14): ?highlight=id1,id2 on mount adds ring-1 ring-primary/40
 * for ~5s; first match scrolls into view; URL is cleaned via
 * history.replaceState(null, '', '/signage/schedules') so back-nav doesn't
 * restore the param.
 *
 * SSE (D-03): admin mutations own-invalidate; useAdminSignageEvents() also
 * reacts to schedule-changed broadcasts from other admin sessions.
 */
export function SchedulesPage() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  useAdminSignageEvents();

  const {
    data: schedules = [],
    isLoading,
    isError,
  } = useQuery({
    queryKey: signageKeys.schedules(),
    queryFn: signageApi.listSchedules,
  });

  const { data: playlists = [] } = useQuery({
    queryKey: signageKeys.playlists(),
    queryFn: signageApi.listPlaylists,
  });

  const playlistNameById = useMemo(() => {
    const m = new Map<string, string>();
    for (const p of playlists) m.set(p.id, p.name);
    return m;
  }, [playlists]);

  // undefined = dialog closed; null = create; object = edit.
  const [editing, setEditing] = useState<
    SignageSchedule | null | undefined
  >(undefined);

  // Highlight handling (D-14)
  const [highlightedIds, setHighlightedIds] = useState<Set<string>>(new Set());
  const firstHighlightRef = useRef<HTMLTableRowElement | null>(null);
  useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const raw = params.get("highlight");
    if (!raw) return;
    const ids = raw.split(",").filter(Boolean);
    if (ids.length === 0) return;
    setHighlightedIds(new Set(ids));
    // Clean URL so back-nav doesn't restore the param.
    window.history.replaceState(null, "", "/signage/schedules");
    const to = window.setTimeout(() => setHighlightedIds(new Set()), 5000);
    return () => window.clearTimeout(to);
  }, []);
  // Scroll first matched row into view after rows render.
  useEffect(() => {
    if (highlightedIds.size === 0) return;
    firstHighlightRef.current?.scrollIntoView({
      behavior: "smooth",
      block: "nearest",
    });
  }, [highlightedIds, schedules]);

  const sorted = useMemo(
    () =>
      [...schedules].sort(
        (a, b) =>
          b.priority - a.priority ||
          b.updated_at.localeCompare(a.updated_at),
      ),
    [schedules],
  );

  // Inline enabled toggle (optimistic + rollback, D-02)
  const toggleEnabled = useMutation({
    mutationFn: ({ id, enabled }: { id: string; enabled: boolean }) =>
      signageApi.updateSchedule(id, { enabled }),
  });

  function handleToggle(row: SignageSchedule, next: boolean) {
    const key = signageKeys.schedules();
    const prev = queryClient.getQueryData<SignageSchedule[]>(key);
    queryClient.setQueryData<SignageSchedule[]>(
      key,
      (list) =>
        (list ?? []).map((s) =>
          s.id === row.id ? { ...s, enabled: next } : s,
        ),
    );
    toggleEnabled.mutate(
      { id: row.id, enabled: next },
      {
        onSuccess: () => {
          queryClient.invalidateQueries({ queryKey: key });
          toast.success(
            t(
              next
                ? "signage.admin.schedules.toast.enabled"
                : "signage.admin.schedules.toast.disabled",
            ),
          );
        },
        onError: (err) => {
          if (prev) queryClient.setQueryData(key, prev);
          const detail = err instanceof Error ? err.message : String(err);
          toast.error(
            t("signage.admin.schedules.error.save_failed", { detail }),
          );
        },
      },
    );
  }

  const deleteMutation = useMutation({
    mutationFn: (id: string) => signageApi.deleteSchedule(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: signageKeys.schedules() });
      toast.success(t("signage.admin.schedules.toast.deleted"));
    },
    onError: (err) => {
      const detail = err instanceof Error ? err.message : String(err);
      toast.error(
        t("signage.admin.schedules.error.delete_failed", { detail }),
      );
    },
  });

  if (isLoading) {
    return (
      <section className="space-y-4">
        <SectionHeader
          title={t("section.signage.schedules.title")}
          description={t("section.signage.schedules.description")}
          className="mt-8"
        />
        <div className="rounded-md border border-border bg-card p-6 text-sm text-muted-foreground">
          {t("signage.admin.schedules.page_title")}…
        </div>
      </section>
    );
  }
  if (isError) {
    return (
      <section className="space-y-4">
        <SectionHeader
          title={t("section.signage.schedules.title")}
          description={t("section.signage.schedules.description")}
          className="mt-8"
        />
        <div className="rounded-md border border-border bg-card p-6 text-sm text-destructive">
          {t("signage.admin.schedules.error.load_failed")}
        </div>
      </section>
    );
  }

  const isEmpty = sorted.length === 0;

  return (
    <section className="space-y-4">
      <SectionHeader
        title={t("section.signage.schedules.title")}
        description={t("section.signage.schedules.description")}
        className="mt-8"
      />
      {isEmpty ? (
        <section className="rounded-md border border-border bg-card p-12 text-center space-y-3">
          <h2 className="text-lg font-semibold">
            {t("signage.admin.schedules.empty_title")}
          </h2>
          <p className="text-sm text-muted-foreground">
            {t("signage.admin.schedules.empty_body")}
          </p>
          <Button type="button" onClick={() => setEditing(null)}>
            {t("signage.admin.schedules.empty_cta")}
          </Button>
        </section>
      ) : (
        <div className="rounded-md border border-border bg-card overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>
                  {t("signage.admin.schedules.col.playlist")}
                </TableHead>
                <TableHead>{t("signage.admin.schedules.col.days")}</TableHead>
                <TableHead>{t("signage.admin.schedules.col.time")}</TableHead>
                <TableHead>
                  {t("signage.admin.schedules.col.priority")}
                </TableHead>
                <TableHead>
                  {t("signage.admin.schedules.col.enabled")}
                </TableHead>
                <TableHead className="text-right">
                  {t("signage.admin.schedules.col.actions")}
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sorted.map((s, idx) => {
                const isHighlight = highlightedIds.has(s.id);
                const firstHighlightIdx = sorted.findIndex((r) =>
                  highlightedIds.has(r.id),
                );
                const refProp =
                  isHighlight && idx === firstHighlightIdx
                    ? firstHighlightRef
                    : undefined;
                const days = weekdayMaskToArray(s.weekday_mask);
                const name =
                  playlistNameById.get(s.playlist_id) ??
                  `${s.playlist_id.slice(0, 8)}…`;
                return (
                  <TableRow
                    key={s.id}
                    ref={refProp}
                    data-testid={`schedule-row-${s.id}`}
                    className={
                      isHighlight ? "ring-1 ring-primary/40 rounded" : undefined
                    }
                  >
                    <TableCell className="font-medium">{name}</TableCell>
                    <TableCell>
                      <div className="flex gap-1 text-sm">
                        {WEEKDAY_KEYS.map((k, i) => (
                          <span
                            key={k}
                            className={
                              days[i]
                                ? "font-semibold"
                                : "text-muted-foreground"
                            }
                          >
                            {t(k)}
                          </span>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">
                      {hhmmToString(s.start_hhmm)} – {hhmmToString(s.end_hhmm)}
                    </TableCell>
                    <TableCell className="text-sm">{s.priority}</TableCell>
                    <TableCell>
                      <label className="flex items-center gap-2 cursor-pointer">
                        <Input
                          type="checkbox"
                          role="switch"
                          aria-label={t(
                            "signage.admin.schedules.col.enabled",
                          )}
                          checked={s.enabled}
                          onChange={(e) =>
                            handleToggle(s, e.target.checked)
                          }
                          className="h-auto w-auto min-w-0 rounded-none border-0 bg-transparent px-0 py-0"
                        />
                      </label>
                    </TableCell>
                    <TableCell className="text-right space-x-1">
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => setEditing(s)}
                        aria-label={`Edit ${name}`}
                      >
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <DeleteButton
                        itemLabel={name}
                        onConfirm={async () => {
                          await deleteMutation.mutateAsync(s.id);
                        }}
                        aria-label={t("ui.delete.ariaLabel", { itemLabel: name })}
                      />
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </div>
      )}

      {!isEmpty && (
        <div className="flex justify-end">
          <Button type="button" onClick={() => setEditing(null)}>
            {t("signage.admin.schedules.new_cta")}
          </Button>
        </div>
      )}

      <ScheduleEditDialog
        open={editing !== undefined}
        onOpenChange={(o) => {
          if (!o) setEditing(undefined);
        }}
        schedule={editing ?? null}
      />
    </section>
  );
}
