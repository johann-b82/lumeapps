import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Trash2, Plus } from "lucide-react";

import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Badge } from "@/components/ui/badge";
import { AssigneeSelect } from "@/components/kpireview/AssigneeSelect";
import { useAuth } from "@/auth/useAuth";
import { kpiReviewKeys } from "@/lib/queryKeys";
import {
  fetchKpiComments,
  createKpiComment,
  deleteKpiComment,
  fetchKpiMeasures,
  createKpiMeasure,
  updateKpiMeasure,
  deleteKpiMeasure,
  type KpiRating,
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

const selectCls =
  "h-8 rounded-lg border border-border bg-background px-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring";

export function KpiDetailPanel({ kpiKey, label }: { kpiKey: string; label: string }) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const qc = useQueryClient();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const comments = useQuery({
    queryKey: kpiReviewKeys.comments(kpiKey),
    queryFn: () => fetchKpiComments(kpiKey),
  });
  const measures = useQuery({
    queryKey: kpiReviewKeys.measures(kpiKey),
    queryFn: () => fetchKpiMeasures({ kpi_key: kpiKey }),
  });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: kpiReviewKeys.comments(kpiKey) });
    qc.invalidateQueries({ queryKey: kpiReviewKeys.measures(kpiKey) });
    qc.invalidateQueries({ queryKey: kpiReviewKeys.summary() });
  };

  // ── Comment form state ──
  const [body, setBody] = useState("");
  const [rating, setRating] = useState<KpiRating | "">("");
  const addComment = useMutation({
    mutationFn: () =>
      createKpiComment({
        kpi_key: kpiKey,
        body: body.trim(),
        rating: rating || null,
        author_name: user?.email,
      }),
    onSuccess: () => {
      setBody("");
      setRating("");
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  // ── Measure form state ──
  const [mTitle, setMTitle] = useState("");
  const [mDesc, setMDesc] = useState("");
  const [mAssignee, setMAssignee] = useState<{ id: string; name: string } | null>(null);
  const [mDue, setMDue] = useState("");
  const [mPrio, setMPrio] = useState<KpiMeasurePriority>("medium");
  const addMeasure = useMutation({
    mutationFn: () =>
      createKpiMeasure({
        kpi_key: kpiKey,
        title: mTitle.trim(),
        description: mDesc.trim(),
        assignee_personio_id: mAssignee?.id ?? null,
        assignee_name: mAssignee?.name ?? null,
        due_date: mDue || null,
        priority: mPrio,
      }),
    onSuccess: () => {
      setMTitle("");
      setMDesc("");
      setMAssignee(null);
      setMDue("");
      setMPrio("medium");
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const setStatus = useMutation({
    mutationFn: (v: { id: string; status: KpiMeasureStatus }) =>
      updateKpiMeasure(v.id, { status: v.status }),
    onSuccess: invalidate,
    onError: (e: Error) => toast.error(e.message),
  });
  const delMeasure = useMutation({
    mutationFn: (id: string) => deleteKpiMeasure(id),
    onSuccess: invalidate,
    onError: (e: Error) => toast.error(e.message),
  });
  const delComment = useMutation({
    mutationFn: (id: string) => deleteKpiComment(id),
    onSuccess: invalidate,
    onError: (e: Error) => toast.error(e.message),
  });

  const fmtDate = (d: string | null) =>
    d ? new Intl.DateTimeFormat(locale, { dateStyle: "medium" }).format(new Date(d)) : "—";

  return (
    <Card className="p-6 space-y-6">
      <h3 className="text-lg font-semibold">{label}</h3>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* ── Kommentare ── */}
        <section className="space-y-3">
          <p className="text-sm font-semibold">{t("kpireview.comments.title")}</p>
          {isAdmin && (
            <div className="space-y-2 rounded-md border border-border p-3">
              <Textarea
                rows={2}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder={t("kpireview.comments.placeholder")}
              />
              <div className="flex items-center gap-2">
                <select
                  className={selectCls}
                  value={rating}
                  onChange={(e) => setRating(e.target.value as KpiRating | "")}
                >
                  <option value="">{t("kpireview.rating.none")}</option>
                  <option value="green">{t("kpireview.rating.green")}</option>
                  <option value="yellow">{t("kpireview.rating.yellow")}</option>
                  <option value="red">{t("kpireview.rating.red")}</option>
                </select>
                <Button
                  size="sm"
                  className="ml-auto"
                  disabled={body.trim() === "" || addComment.isPending}
                  onClick={() => addComment.mutate()}
                >
                  <Plus className="h-4 w-4" /> {t("kpireview.comments.add")}
                </Button>
              </div>
            </div>
          )}
          <div className="space-y-2">
            {comments.data?.length === 0 && (
              <p className="text-sm text-muted-foreground">{t("kpireview.comments.empty")}</p>
            )}
            {comments.data?.map((c) => (
              <div key={c.id} className="rounded-md border border-border p-2.5 text-sm">
                <div className="flex items-center gap-2">
                  {c.rating && (
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-full"
                      style={{ background: RATING_DOT[c.rating] }}
                      aria-hidden
                    />
                  )}
                  <span className="text-xs text-muted-foreground">
                    {c.author_name ?? "—"} · {fmtDate(c.created_at)}
                  </span>
                  {isAdmin && (
                    <button
                      className="ml-auto text-muted-foreground hover:text-destructive"
                      onClick={() => delComment.mutate(c.id)}
                      title={t("kpireview.delete")}
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
                <p className="mt-1 whitespace-pre-wrap">{c.body}</p>
              </div>
            ))}
          </div>
        </section>

        {/* ── Maßnahmen ── */}
        <section className="space-y-3">
          <p className="text-sm font-semibold">{t("kpireview.measures.title")}</p>
          {isAdmin && (
            <div className="space-y-2 rounded-md border border-border p-3">
              <Input
                value={mTitle}
                onChange={(e) => setMTitle(e.target.value)}
                placeholder={t("kpireview.measures.titlePlaceholder")}
              />
              <Textarea
                rows={2}
                value={mDesc}
                onChange={(e) => setMDesc(e.target.value)}
                placeholder={t("kpireview.measures.descPlaceholder")}
              />
              <div className="grid grid-cols-2 gap-2">
                <AssigneeSelect
                  value={mAssignee?.id ?? null}
                  onChange={setMAssignee}
                  placeholder={t("kpireview.measures.assignee")}
                />
                <Input type="date" value={mDue} onChange={(e) => setMDue(e.target.value)} />
                <select
                  className={selectCls}
                  value={mPrio}
                  onChange={(e) => setMPrio(e.target.value as KpiMeasurePriority)}
                >
                  <option value="low">{t("kpireview.priority.low")}</option>
                  <option value="medium">{t("kpireview.priority.medium")}</option>
                  <option value="high">{t("kpireview.priority.high")}</option>
                </select>
                <Button
                  size="sm"
                  disabled={mTitle.trim() === "" || addMeasure.isPending}
                  onClick={() => addMeasure.mutate()}
                >
                  <Plus className="h-4 w-4" /> {t("kpireview.measures.add")}
                </Button>
              </div>
            </div>
          )}
          <div className="space-y-2">
            {measures.data?.length === 0 && (
              <p className="text-sm text-muted-foreground">{t("kpireview.measures.empty")}</p>
            )}
            {measures.data?.map((m) => (
              <div key={m.id} className="rounded-md border border-border p-2.5 text-sm">
                <div className="flex items-start gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="font-medium">{m.title}</p>
                    {m.description && (
                      <p className="text-xs text-muted-foreground whitespace-pre-wrap">{m.description}</p>
                    )}
                    <p className="mt-1 text-xs text-muted-foreground">
                      {m.assignee_name ?? t("kpireview.measures.unassigned")} · {t("kpireview.measures.due")}{" "}
                      {fmtDate(m.due_date)} · {t(`kpireview.priority.${m.priority}`)}
                    </p>
                  </div>
                  <Badge variant={STATUS_VARIANT[m.status]}>
                    {t(`kpireview.status.${m.status}`)}
                  </Badge>
                </div>
                {isAdmin && (
                  <div className="mt-2 flex items-center gap-2">
                    <select
                      className={selectCls}
                      value={m.status}
                      onChange={(e) =>
                        setStatus.mutate({ id: m.id, status: e.target.value as KpiMeasureStatus })
                      }
                    >
                      <option value="open">{t("kpireview.status.open")}</option>
                      <option value="in_progress">{t("kpireview.status.in_progress")}</option>
                      <option value="done">{t("kpireview.status.done")}</option>
                      <option value="dropped">{t("kpireview.status.dropped")}</option>
                    </select>
                    <button
                      className="ml-auto text-muted-foreground hover:text-destructive"
                      onClick={() => delMeasure.mutate(m.id)}
                      title={t("kpireview.delete")}
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </section>
      </div>
    </Card>
  );
}
