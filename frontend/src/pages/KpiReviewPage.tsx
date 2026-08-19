import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "wouter";
import { ExternalLink, Loader2, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DeleteDialog } from "@/components/ui/delete-dialog";
import { AssigneeSelect } from "@/components/kpireview/AssigneeSelect";
import { useAuth } from "@/auth/useAuth";
import { kpiReviewKeys } from "@/lib/queryKeys";
import {
  fetchKpiReviewSummary,
  fetchKpiComments,
  fetchKpiMeasures,
  createKpiMeasure,
  updateKpiMeasure,
  deleteKpiMeasure,
  getBubbles,
  markBubbleViewed,
  deleteKpiComment,
  type KpiComment,
  type KpiRating,
  type KpiMeasure,
  type KpiMeasurePriority,
  type KpiMeasureStatus,
} from "@/lib/api";

const RATING_DOT: Record<KpiRating, string> = {
  red: "var(--color-destructive)",
  yellow: "#eab308",
  green: "#22c55e",
};
const STATUS_VARIANT: Record<KpiMeasureStatus, "default" | "secondary" | "outline" | "destructive"> = {
  open: "default",
  in_progress: "secondary",
  done: "outline",
  dropped: "destructive",
};
const DOMAIN_ORDER = ["sales", "hr", "quality", "finance", "procurement", "production"];
const selectCls =
  "h-8 rounded-lg border border-border bg-background px-2 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring";

type StatusFilter = KpiMeasureStatus | "all";

/**
 * Dedicated measures management page ("Maßnahmen") — the single place to create,
 * assign, plan and track every KPI measure across all dashboards (mirrors the
 * feedback inbox). Bubbles/comments are still created on the real charts; here
 * a measure is linked to its KPI and optionally to one of that KPI's bubbles.
 */
export function KpiReviewPage() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const qc = useQueryClient();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [filter, setFilter] = useState<StatusFilter>("all");

  const summary = useQuery({
    queryKey: kpiReviewKeys.summary(),
    queryFn: fetchKpiReviewSummary,
  });
  const measuresQ = useQuery({
    queryKey: kpiReviewKeys.measures(undefined, filter),
    queryFn: () => fetchKpiMeasures(filter === "all" ? {} : { status: filter }),
  });

  // KPIs grouped by domain for the create-form dropdown.
  const kpisByDomain = useMemo(() => {
    const map = new Map<string, { kpi_key: string }[]>();
    for (const it of summary.data ?? []) {
      if (!map.has(it.domain)) map.set(it.domain, []);
      map.get(it.domain)!.push({ kpi_key: it.kpi_key });
    }
    return map;
  }, [summary.data]);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: kpiReviewKeys.all });
  };

  const kpiLabel = (key: string) => t(`kpireview.kpi.${key}`);
  const fmtDate = (d: string | null) =>
    d ? new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(new Date(d)) : "—";

  // ── Create form ──
  const [kpiKey, setKpiKey] = useState("");
  const [commentId, setCommentId] = useState("");
  const [title, setTitle] = useState("");
  const [assignee, setAssignee] = useState<{ id: string; name: string } | null>(null);
  const [due, setDue] = useState("");
  const [prio, setPrio] = useState<KpiMeasurePriority>("medium");

  // Bubbles of the picked KPI, to optionally link the measure to one.
  const bubblesQ = useQuery({
    queryKey: kpiReviewKeys.comments(kpiKey),
    queryFn: () => fetchKpiComments(kpiKey),
    enabled: kpiKey !== "",
  });
  const bubbles = (bubblesQ.data ?? []).filter((c) => c.number != null);

  const add = useMutation({
    mutationFn: () =>
      createKpiMeasure({
        kpi_key: kpiKey,
        comment_id: commentId || null,
        title: title.trim(),
        assignee_personio_id: assignee?.id ?? null,
        assignee_name: assignee?.name ?? null,
        due_date: due || null,
        priority: prio,
      }),
    onSuccess: () => {
      setCommentId("");
      setTitle("");
      setAssignee(null);
      setDue("");
      setPrio("medium");
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const patch = useMutation({
    mutationFn: (v: { id: string; body: Parameters<typeof updateKpiMeasure>[1] }) =>
      updateKpiMeasure(v.id, v.body),
    onSuccess: invalidate,
    onError: (e: Error) => toast.error(e.message),
  });
  const [deleteTarget, setDeleteTarget] = useState<KpiMeasure | null>(null);
  const del = useMutation({
    mutationFn: (id: string) => deleteKpiMeasure(id),
    onSuccess: () => {
      setDeleteTarget(null);
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const measures = measuresQ.data ?? [];

  // ── Bubbles (KPI-Bewertung) — every bubble across all KPIs, newest first ──
  const bubblesAllQ = useQuery({
    queryKey: ["kpi-review", "bubbles-all"],
    queryFn: getBubbles,
    enabled: isAdmin,
  });
  const bubblesAll = bubblesAllQ.data ?? [];
  const viewBubble = useMutation({
    mutationFn: (id: string) => markBubbleViewed(id),
    onSuccess: invalidate,
  });
  const [deleteBubble, setDeleteBubble] = useState<KpiComment | null>(null);
  const delBubble = useMutation({
    mutationFn: (id: string) => deleteKpiComment(id),
    onSuccess: () => {
      setDeleteBubble(null);
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-16 space-y-6">
      <div>
        <h2 className="text-xl font-semibold">{t("kpireview.title")}</h2>
        <p className="text-sm text-muted-foreground">{t("kpireview.subtitle")}</p>
      </div>

      {/* Bubbles (KPI-Bewertung) — auto-listed across all KPIs */}
      {isAdmin && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">
              {t("kpireview.bubbles.title")}{" "}
              <span className="text-sm font-normal text-muted-foreground">
                ({bubblesAll.length})
              </span>
            </CardTitle>
          </CardHeader>
          <CardContent>
            {bubblesAllQ.isLoading && (
              <div className="flex justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            )}
            {bubblesAllQ.data && bubblesAll.length === 0 && (
              <p className="py-8 text-center text-muted-foreground">
                {t("kpireview.bubbles.empty")}
              </p>
            )}
            {bubblesAll.length > 0 && (
              <ul className="divide-y divide-border">
                {bubblesAll.map((b) => (
                  <li
                    key={b.id}
                    className={`flex items-start gap-3 rounded-md px-1 py-2.5 ${
                      b.viewed_at ? "" : "bg-primary/5"
                    }`}
                  >
                    <button
                      type="button"
                      onClick={() => {
                        if (!b.viewed_at) viewBubble.mutate(b.id);
                      }}
                      className="flex min-w-0 flex-1 items-start gap-3 text-left"
                      title={b.viewed_at ? undefined : t("kpireview.bubbles.markViewed")}
                    >
                      <span
                        className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[11px] font-bold text-white"
                        style={{
                          background: b.rating ? RATING_DOT[b.rating] : "var(--color-primary)",
                        }}
                        aria-hidden
                      >
                        {b.number ?? "•"}
                      </span>
                      <span className="min-w-0">
                        <span className="flex flex-wrap items-center gap-x-2">
                          {!b.viewed_at && (
                            <span
                              className="inline-block h-2 w-2 rounded-full bg-primary"
                              aria-label={t("kpireview.bubbles.new")}
                            />
                          )}
                          <span className="text-xs font-medium text-muted-foreground">
                            {t(`kpireview.domain.${b.kpi_key}`)}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {b.author_name ? `· ${b.author_name} ` : ""}· {fmtDate(b.created_at)}
                          </span>
                        </span>
                        <span className="mt-0.5 block whitespace-pre-wrap text-sm">{b.body}</span>
                      </span>
                    </button>
                    <Link
                      href={`/${b.kpi_key}`}
                      className="mt-0.5 shrink-0 text-muted-foreground hover:text-primary"
                      title={t("kpireview.bubbles.goto")}
                    >
                      <ExternalLink className="h-4 w-4" />
                    </Link>
                    <button
                      type="button"
                      className="mt-0.5 shrink-0 text-muted-foreground hover:text-destructive"
                      onClick={() => setDeleteBubble(b)}
                      title={t("kpireview.delete")}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      )}

      {/* New measure */}
      {isAdmin && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">{t("kpireview.measures.new")}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="grid gap-2 sm:grid-cols-2">
              <select
                className={selectCls + " h-9 text-sm"}
                value={kpiKey}
                onChange={(e) => {
                  setKpiKey(e.target.value);
                  setCommentId("");
                }}
              >
                <option value="">{t("kpireview.measures.selectKpi")}</option>
                {DOMAIN_ORDER.filter((d) => kpisByDomain.has(d)).map((domain) => (
                  <optgroup key={domain} label={t(`kpireview.domain.${domain}`)}>
                    {kpisByDomain.get(domain)!.map((k) => (
                      <option key={k.kpi_key} value={k.kpi_key}>
                        {kpiLabel(k.kpi_key)}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
              <select
                className={selectCls + " h-9 text-sm"}
                value={commentId}
                onChange={(e) => setCommentId(e.target.value)}
                disabled={kpiKey === "" || bubbles.length === 0}
              >
                <option value="">{t("kpireview.measures.bubbleNone")}</option>
                {bubbles.map((b) => (
                  <option key={b.id} value={b.id}>
                    #{b.number} — {b.body.slice(0, 40)}
                  </option>
                ))}
              </select>
            </div>
            <Input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder={t("kpireview.measures.titlePlaceholder")}
            />
            <div className="grid gap-2 sm:grid-cols-[1fr_auto_auto_auto]">
              <AssigneeSelect
                value={assignee?.id ?? null}
                onChange={setAssignee}
                placeholder={t("kpireview.measures.assignee")}
              />
              <Input
                type="date"
                className="w-40"
                value={due}
                onChange={(e) => setDue(e.target.value)}
              />
              <select
                className={selectCls + " h-9 text-sm"}
                value={prio}
                onChange={(e) => setPrio(e.target.value as KpiMeasurePriority)}
              >
                <option value="low">{t("kpireview.priority.low")}</option>
                <option value="medium">{t("kpireview.priority.medium")}</option>
                <option value="high">{t("kpireview.priority.high")}</option>
              </select>
              <Button
                disabled={kpiKey === "" || title.trim() === "" || add.isPending}
                onClick={() => add.mutate()}
              >
                <Plus className="h-4 w-4" /> {t("kpireview.measures.add")}
              </Button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Measures table */}
      <Card>
        <CardHeader className="flex-row items-center justify-between space-y-0">
          <CardTitle className="text-base">
            {t("kpireview.measures.title")}{" "}
            <span className="text-sm font-normal text-muted-foreground">({measures.length})</span>
          </CardTitle>
          <select
            className={selectCls}
            value={filter}
            onChange={(e) => setFilter(e.target.value as StatusFilter)}
          >
            <option value="all">{t("kpireview.measures.filterAll")}</option>
            <option value="open">{t("kpireview.status.open")}</option>
            <option value="in_progress">{t("kpireview.status.in_progress")}</option>
            <option value="done">{t("kpireview.status.done")}</option>
            <option value="dropped">{t("kpireview.status.dropped")}</option>
          </select>
        </CardHeader>
        <CardContent>
          {measuresQ.isLoading && (
            <div className="flex justify-center py-10">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}
          {measuresQ.data && measures.length === 0 && (
            <p className="py-10 text-center text-muted-foreground">{t("kpireview.measures.empty")}</p>
          )}
          {measures.length > 0 && (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("kpireview.tracker.kpi")}</TableHead>
                    <TableHead>{t("kpireview.tracker.measure")}</TableHead>
                    <TableHead>{t("kpireview.tracker.assignee")}</TableHead>
                    <TableHead>{t("kpireview.tracker.due")}</TableHead>
                    <TableHead>{t("kpireview.measures.priorityLabel")}</TableHead>
                    <TableHead>{t("kpireview.tracker.status")}</TableHead>
                    {isAdmin && <TableHead />}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {measures.map((m) => (
                    <TableRow key={m.id}>
                      <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                        {kpiLabel(m.kpi_key)}
                      </TableCell>
                      <TableCell className="font-medium">{m.title}</TableCell>
                      <TableCell className="min-w-44">
                        {isAdmin ? (
                          <AssigneeSelect
                            value={m.assignee_personio_id}
                            onChange={(a) =>
                              patch.mutate({
                                id: m.id,
                                body: {
                                  assignee_personio_id: a?.id ?? null,
                                  assignee_name: a?.name ?? null,
                                },
                              })
                            }
                            placeholder={t("kpireview.measures.assignee")}
                          />
                        ) : (
                          <span className="text-sm">{m.assignee_name ?? t("kpireview.measures.unassigned")}</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {isAdmin ? (
                          <Input
                            type="date"
                            className="h-8 w-36 text-xs"
                            value={m.due_date ?? ""}
                            onChange={(e) =>
                              patch.mutate({ id: m.id, body: { due_date: e.target.value || null } })
                            }
                          />
                        ) : (
                          <span className="whitespace-nowrap text-sm">{fmtDate(m.due_date)}</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {isAdmin ? (
                          <select
                            className={selectCls}
                            value={m.priority}
                            onChange={(e) =>
                              patch.mutate({
                                id: m.id,
                                body: { priority: e.target.value as KpiMeasurePriority },
                              })
                            }
                          >
                            <option value="low">{t("kpireview.priority.low")}</option>
                            <option value="medium">{t("kpireview.priority.medium")}</option>
                            <option value="high">{t("kpireview.priority.high")}</option>
                          </select>
                        ) : (
                          <span className="text-sm">{t(`kpireview.priority.${m.priority}`)}</span>
                        )}
                      </TableCell>
                      <TableCell>
                        {isAdmin ? (
                          <select
                            className={selectCls}
                            value={m.status}
                            onChange={(e) =>
                              patch.mutate({
                                id: m.id,
                                body: { status: e.target.value as KpiMeasureStatus },
                              })
                            }
                          >
                            <option value="open">{t("kpireview.status.open")}</option>
                            <option value="in_progress">{t("kpireview.status.in_progress")}</option>
                            <option value="done">{t("kpireview.status.done")}</option>
                            <option value="dropped">{t("kpireview.status.dropped")}</option>
                          </select>
                        ) : (
                          <Badge variant={STATUS_VARIANT[m.status]}>
                            {t(`kpireview.status.${m.status}`)}
                          </Badge>
                        )}
                      </TableCell>
                      {isAdmin && (
                        <TableCell>
                          <button
                            className="text-muted-foreground hover:text-destructive"
                            onClick={() => setDeleteTarget(m)}
                            title={t("kpireview.delete")}
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </TableCell>
                      )}
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <DeleteDialog
        open={deleteTarget !== null}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
        title={t("kpireview.measures.deleteTitle")}
        body={deleteTarget?.title ?? ""}
        onConfirm={() => {
          if (deleteTarget) del.mutate(deleteTarget.id);
        }}
        confirmDisabled={del.isPending}
      />

      <DeleteDialog
        open={deleteBubble !== null}
        onOpenChange={(o) => !o && setDeleteBubble(null)}
        title={t("kpireview.bubble.deleteTitle")}
        body={t("kpireview.bubble.deleteBody")}
        onConfirm={() => {
          if (deleteBubble) delBubble.mutate(deleteBubble.id);
        }}
        confirmDisabled={delBubble.isPending}
      />
    </div>
  );
}
