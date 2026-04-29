import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import {
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "sonner";
import { formatDistanceToNow } from "date-fns";
import { Pencil, ShieldOff } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { signageKeys } from "@/lib/queryKeys";
import { signageApi } from "@/signage/lib/signageApi";
import type {
  SignageDevice,
  SignageDeviceAnalytics,
} from "@/signage/lib/signageTypes";
import { DeviceStatusChip } from "@/signage/components/DeviceStatusChip";
import { DeviceEditDialog } from "@/signage/components/DeviceEditDialog";
import { UptimeBadge } from "@/signage/components/UptimeBadge";
import { SectionHeader } from "@/components/ui/section-header";

/**
 * /signage/devices — admin device table (SGN-ADM-06).
 *
 * Live status: TanStack Query refetches signageApi.listDevices every 30_000 ms
 * (D-13 cadence), so DeviceStatusChip transitions green→amber→red within one
 * polling cycle. Edit + Revoke actions per row; Pair-new CTA navigates to
 * /signage/pair (registered in Task 1). Empty state offers the same CTA.
 */
export function DevicesPage() {
  const { t } = useTranslation();
  const [, setLocation] = useLocation();
  const queryClient = useQueryClient();
  const [editTarget, setEditTarget] = useState<SignageDevice | null>(null);
  const [revokeTarget, setRevokeTarget] = useState<SignageDevice | null>(null);

  // Phase 70-04 (D-02, D-05): Directus row list. Resolved playlist + tag_ids
  // are fetched per-device via useQueries below and merged client-side.
  const { data: deviceRows = [], isLoading } = useQuery({
    queryKey: ["directus", "signage_devices"] as const,
    queryFn: signageApi.listDevices,
    refetchInterval: 30_000,
  });

  // Phase 70-04 (D-02, D-02a): per-device resolved playlist via FastAPI
  // /api/signage/resolved/{id}. Cache key per device aligns with SSE bridge
  // (D-02c, D-05a) — playlist-changed / device-changed events for device X
  // invalidate exactly that key. N parallel HTTP/2 requests acceptable for
  // typical device counts <20 (D-02b).
  const resolvedQueries = useQueries({
    queries: deviceRows.map((d) => ({
      queryKey: ["fastapi", "resolved", d.id] as const,
      queryFn: () => signageApi.getResolvedForDevice(d.id),
      staleTime: 30_000,
    })),
  });

  // Phase 70-04 (D-02, D-04): merge Directus row + resolved response.
  // Field names align with SignageDevice extras so the spread is loss-free
  // — current_playlist_id / current_playlist_name / tag_ids land directly
  // on the SignageDevice shape (D-04 / D-04a — no rename to resolved_*).
  const devices: SignageDevice[] = useMemo(
    () =>
      deviceRows.map((row, i) => ({
        ...row,
        ...(resolvedQueries[i]?.data ?? {
          current_playlist_id: null,
          current_playlist_name: null,
          tag_ids: null,
        }),
      })) as SignageDevice[],
    [deviceRows, resolvedQueries],
  );

  // Phase 53 SGN-ANA-01 — per-device analytics. Separate query so the two
  // streams poll/invalidate independently. 30 s matches existing cadence;
  // refetchOnWindowFocus covers the tab-visibility refresh requirement (D-11).
  const { data: analyticsByDevice = {} } = useQuery<
    Record<string, SignageDeviceAnalytics>
  >({
    queryKey: signageKeys.deviceAnalytics(),
    queryFn: async () => {
      const rows = await signageApi.listDeviceAnalytics();
      return Object.fromEntries(rows.map((r) => [r.device_id, r]));
    },
    refetchInterval: 30_000,
    refetchOnWindowFocus: true,
  });

  // 260421-r4b: resolve tag_ids → tag names via the shared tags query.
  const { data: tags = [] } = useQuery({
    queryKey: signageKeys.tags(),
    queryFn: signageApi.listTags,
    staleTime: 60_000,
  });
  const tagById = useMemo(
    () => new Map(tags.map((t) => [t.id, t])),
    [tags],
  );

  const revokeMutation = useMutation({
    mutationFn: (id: string) => signageApi.revokeDevice(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["directus", "signage_devices"] });
      queryClient.invalidateQueries({ queryKey: ["fastapi", "resolved"] });
      toast.success(t("signage.admin.device.revoked"));
      setRevokeTarget(null);
    },
    onError: (err: unknown) => {
      const detail = err instanceof Error ? err.message : String(err);
      toast.error(t("signage.admin.device.revoke_error", { detail }));
    },
  });

  // Empty state — only after first load returns zero rows.
  if (!isLoading && devices.length === 0) {
    return (
      <section className="rounded-md border border-border bg-card p-12 text-center">
        <h2 className="text-lg font-semibold">
          {t("signage.admin.devices.empty_title")}
        </h2>
        <p className="mt-2 text-sm text-muted-foreground">
          {t("signage.admin.devices.empty_body")}
        </p>
        <Button
          className="mt-4"
          onClick={() => setLocation("/signage/pair")}
        >
          {t("signage.admin.devices.empty_cta")}
        </Button>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <SectionHeader
        title={t("section.signage.devices.title")}
        description={t("section.signage.devices.description")}
        className="mt-8"
      />
      <div className="rounded-md border border-border bg-card">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("signage.admin.devices.col_name")}</TableHead>
              <TableHead>{t("signage.admin.devices.col_status")}</TableHead>
              <TableHead>
                {t("signage.admin.device.analytics.uptime24h.label")}
              </TableHead>
              <TableHead>
                {t("signage.admin.device.analytics.missed24h.label")}
              </TableHead>
              <TableHead>{t("signage.admin.devices.col_tags")}</TableHead>
              <TableHead>{t("signage.admin.devices.col_playlist")}</TableHead>
              <TableHead>{t("signage.admin.devices.col_last_seen")}</TableHead>
              <TableHead className="text-right">
                {t("signage.admin.devices.col_actions")}
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {devices.map((d) => (
              <TableRow key={d.id}>
                <TableCell>
                  <span className="text-sm font-semibold">{d.name}</span>
                </TableCell>
                <TableCell>
                  <DeviceStatusChip lastSeenAt={d.last_seen_at} />
                </TableCell>
                <TableCell>
                  <UptimeBadge
                    variant="uptime"
                    data={analyticsByDevice[d.id]}
                  />
                </TableCell>
                <TableCell>
                  <UptimeBadge
                    variant="missed"
                    data={analyticsByDevice[d.id]}
                  />
                </TableCell>
                <TableCell>
                  <div className="flex flex-wrap gap-1">
                    {(d.tag_ids ?? []).map((tagId) => {
                      const tag = tagById.get(tagId);
                      if (!tag) return null;
                      return (
                        <Badge
                          key={tag.id}
                          variant="secondary"
                          className="text-xs"
                        >
                          {tag.name}
                        </Badge>
                      );
                    })}
                  </div>
                </TableCell>
                <TableCell>
                  <span className="text-sm text-muted-foreground">
                    {d.current_playlist_name ?? d.current_playlist_id ?? "—"}
                  </span>
                </TableCell>
                <TableCell>
                  <span className="text-sm text-muted-foreground">
                    {d.last_seen_at
                      ? formatDistanceToNow(new Date(d.last_seen_at), {
                          addSuffix: true,
                        })
                      : "—"}
                  </span>
                </TableCell>
                <TableCell className="text-right">
                  <div className="flex justify-end gap-1">
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => setEditTarget(d)}
                      aria-label={t("signage.admin.device.edit_title")}
                    >
                      <Pencil className="h-4 w-4" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => setRevokeTarget(d)}
                      aria-label={t("signage.admin.device.revoke_title")}
                    >
                      <ShieldOff className="h-4 w-4 text-destructive" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="flex justify-end">
        <Button onClick={() => setLocation("/signage/pair")}>
          {t("signage.admin.devices.pair_button")}
        </Button>
      </div>

      {/* Edit-device dialog (controlled by editTarget). */}
      <DeviceEditDialog
        open={editTarget !== null}
        onOpenChange={(next) => {
          if (!next) setEditTarget(null);
        }}
        device={editTarget}
      />

      {/* Revoke-confirm dialog. */}
      <Dialog
        open={revokeTarget !== null}
        onOpenChange={(next) => {
          if (!next) setRevokeTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {t("signage.admin.device.revoke_title")}
            </DialogTitle>
            <DialogDescription>
              {t("signage.admin.device.revoke_confirm_body", {
                name: revokeTarget?.name ?? "",
              })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setRevokeTarget(null)}
              disabled={revokeMutation.isPending}
            >
              {t("signage.admin.device.revoke_cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                if (revokeTarget) revokeMutation.mutate(revokeTarget.id);
              }}
              disabled={revokeMutation.isPending}
            >
              {t("signage.admin.device.revoke_confirm")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </section>
  );
}
