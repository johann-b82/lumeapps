import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Trash2, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { AssigneeSelect } from "@/components/kpireview/AssigneeSelect";
import { useAuth } from "@/auth/useAuth";
import { kpiReviewKeys } from "@/lib/queryKeys";
import {
  fetchKpiMeasures,
  createKpiMeasure,
  updateKpiMeasure,
  deleteKpiMeasure,
  type KpiMeasurePriority,
  type KpiMeasureStatus,
} from "@/lib/api";

const STATUS_VARIANT: Record<KpiMeasureStatus, "default" | "secondary" | "outline" | "destructive"> = {
  open: "default",
  in_progress: "secondary",
  done: "outline",
  dropped: "destructive",
};
const selectCls =
  "h-7 rounded-lg border border-border bg-background px-1.5 text-xs outline-none focus-visible:ring-2 focus-visible:ring-ring";

/** Measures linked to one bubble (comment). Add / assign (Personio) / track. */
export function BubbleMeasures({ kpiKey, commentId }: { kpiKey: string; commentId: string }) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const qc = useQueryClient();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const measuresQ = useQuery({
    queryKey: kpiReviewKeys.measures(kpiKey),
    queryFn: () => fetchKpiMeasures({ kpi_key: kpiKey }),
  });
  const measures = (measuresQ.data ?? []).filter((m) => m.comment_id === commentId);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: kpiReviewKeys.measures(kpiKey) });
    qc.invalidateQueries({ queryKey: kpiReviewKeys.summary() });
  };

  const [title, setTitle] = useState("");
  const [assignee, setAssignee] = useState<{ id: string; name: string } | null>(null);
  const [due, setDue] = useState("");
  const [prio, setPrio] = useState<KpiMeasurePriority>("medium");

  const add = useMutation({
    mutationFn: () =>
      createKpiMeasure({
        kpi_key: kpiKey,
        comment_id: commentId,
        title: title.trim(),
        assignee_personio_id: assignee?.id ?? null,
        assignee_name: assignee?.name ?? null,
        due_date: due || null,
        priority: prio,
      }),
    onSuccess: () => {
      setTitle("");
      setAssignee(null);
      setDue("");
      setPrio("medium");
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
  const del = useMutation({
    mutationFn: (id: string) => deleteKpiMeasure(id),
    onSuccess: invalidate,
    onError: (e: Error) => toast.error(e.message),
  });

  const fmtDate = (d: string | null) =>
    d ? new Intl.DateTimeFormat(locale, { dateStyle: "short" }).format(new Date(d)) : "—";

  return (
    <div className="mt-2 border-t border-border pt-2">
      <p className="text-xs font-semibold text-muted-foreground mb-1.5">
        {t("kpireview.measures.title")}
      </p>

      <div className="space-y-1.5">
        {measures.map((m) => (
          <div key={m.id} className="rounded-md border border-border p-1.5 text-xs">
            <div className="flex items-start gap-1.5">
              <span className="min-w-0 flex-1 font-medium">{m.title}</span>
              <Badge variant={STATUS_VARIANT[m.status]}>{t(`kpireview.status.${m.status}`)}</Badge>
            </div>
            <p className="mt-0.5 text-muted-foreground">
              {m.assignee_name ?? t("kpireview.measures.unassigned")} · {t("kpireview.measures.due")} {fmtDate(m.due_date)} · {t(`kpireview.priority.${m.priority}`)}
            </p>
            {isAdmin && (
              <div className="mt-1 flex items-center gap-1.5">
                <select
                  className={selectCls}
                  value={m.status}
                  onChange={(e) => setStatus.mutate({ id: m.id, status: e.target.value as KpiMeasureStatus })}
                >
                  <option value="open">{t("kpireview.status.open")}</option>
                  <option value="in_progress">{t("kpireview.status.in_progress")}</option>
                  <option value="done">{t("kpireview.status.done")}</option>
                  <option value="dropped">{t("kpireview.status.dropped")}</option>
                </select>
                <button className="ml-auto text-muted-foreground hover:text-destructive" onClick={() => del.mutate(m.id)} title={t("kpireview.delete")}>
                  <Trash2 className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
          </div>
        ))}
        {measures.length === 0 && (
          <p className="text-xs text-muted-foreground">{t("kpireview.measures.empty")}</p>
        )}
      </div>

      {isAdmin && (
        <div className="mt-2 space-y-1.5 rounded-md bg-muted/40 p-1.5">
          <Input
            className="h-7 text-xs"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder={t("kpireview.measures.titlePlaceholder")}
          />
          <AssigneeSelect value={assignee?.id ?? null} onChange={setAssignee} placeholder={t("kpireview.measures.assignee")} />
          <div className="flex items-center gap-1.5">
            <Input type="date" className="h-7 text-xs" value={due} onChange={(e) => setDue(e.target.value)} />
            <select className={selectCls} value={prio} onChange={(e) => setPrio(e.target.value as KpiMeasurePriority)}>
              <option value="low">{t("kpireview.priority.low")}</option>
              <option value="medium">{t("kpireview.priority.medium")}</option>
              <option value="high">{t("kpireview.priority.high")}</option>
            </select>
            <Button size="sm" className="ml-auto h-7" disabled={title.trim() === "" || add.isPending} onClick={() => add.mutate()}>
              <Plus className="h-3.5 w-3.5" /> {t("kpireview.measures.add")}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
