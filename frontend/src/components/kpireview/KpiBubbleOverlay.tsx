import { useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "wouter";
import { toast } from "sonner";
import { X, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { DeleteDialog } from "@/components/ui/delete-dialog";
import { useAuth } from "@/auth/useAuth";
import { useBubbleMode } from "@/contexts/BubbleModeContext";
import { kpiReviewKeys } from "@/lib/queryKeys";
import {
  fetchKpiComments,
  createKpiComment,
  deleteKpiComment,
  fetchKpiMeasures,
  type KpiComment,
  type KpiRating,
} from "@/lib/api";

const RATING_DOT: Record<KpiRating, string> = {
  red: "var(--color-destructive)",
  yellow: "#eab308",
  green: "#22c55e",
};

type Norm = { x: number; y: number };
type Region = { x: number; y: number; w: number; h: number };

const clamp01 = (v: number) => Math.max(0, Math.min(1, v));
const pct = (v: number) => `${v * 100}%`;

/**
 * KPI chart with FAIR-style bubbles: chart on the left, bubble/comment list on
 * the right. The global "Bubble" mode (BubbleModeContext) enables drawing a
 * region on the chart; a numbered marker appears and a comment box opens in the
 * right panel. Markers are neutral (no persistent red fill); the region only
 * outlines on hover/selection.
 */
export function KpiBubbleOverlay({
  kpiKey,
  children,
}: {
  kpiKey: string;
  children: ReactNode;
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";
  const { active: bubbleMode } = useBubbleMode();
  const containerRef = useRef<HTMLDivElement>(null);

  const comments = useQuery({
    queryKey: kpiReviewKeys.comments(kpiKey),
    queryFn: () => fetchKpiComments(kpiKey),
  });
  const bubbles = (comments.data ?? []).filter(
    (c) => c.region_x != null && c.number != null,
  );

  const [start, setStart] = useState<Norm | null>(null);
  const [current, setCurrent] = useState<Norm | null>(null);
  const [pending, setPending] = useState<Region | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [body, setBody] = useState("");
  const [rating, setRating] = useState<KpiRating | "">("");

  const toNorm = (e: React.MouseEvent): Norm => {
    const r = containerRef.current!.getBoundingClientRect();
    return {
      x: clamp01((e.clientX - r.left) / r.width),
      y: clamp01((e.clientY - r.top) / r.height),
    };
  };

  const save = useMutation({
    mutationFn: () =>
      createKpiComment({
        kpi_key: kpiKey,
        body: body.trim(),
        rating: rating || null,
        author_name: user?.email,
        region_x: pending!.x,
        region_y: pending!.y,
        region_w: pending!.w,
        region_h: pending!.h,
      }),
    onSuccess: () => {
      setPending(null);
      setBody("");
      setRating("");
      qc.invalidateQueries({ queryKey: kpiReviewKeys.comments(kpiKey) });
      qc.invalidateQueries({ queryKey: kpiReviewKeys.summary() });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const measures = useQuery({
    queryKey: kpiReviewKeys.measures(kpiKey),
    queryFn: () => fetchKpiMeasures({ kpi_key: kpiKey }),
  });
  const measureCount = (id: string) =>
    (measures.data ?? []).filter((m) => m.comment_id === id).length;

  const [deleteTarget, setDeleteTarget] = useState<KpiComment | null>(null);
  const delBubble = useMutation({
    mutationFn: (id: string) => deleteKpiComment(id),
    onSuccess: () => {
      setDeleteTarget(null);
      setSelected(null);
      qc.invalidateQueries({ queryKey: kpiReviewKeys.comments(kpiKey) });
      qc.invalidateQueries({ queryKey: kpiReviewKeys.summary() });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const drawRect =
    start && current
      ? {
          x: Math.min(start.x, current.x),
          y: Math.min(start.y, current.y),
          w: Math.abs(current.x - start.x),
          h: Math.abs(current.y - start.y),
        }
      : null;

  // Neutral region outline shown for the drawing rect, the pending region, or
  // the selected bubble — never a persistent red fill.
  const selBubble = bubbles.find((b) => b.id === selected);
  const outline: Region | null =
    drawRect ??
    pending ??
    (selBubble
      ? {
          x: selBubble.region_x!,
          y: selBubble.region_y!,
          w: selBubble.region_w!,
          h: selBubble.region_h!,
        }
      : null);

  const showPanel = bubbleMode || bubbles.length > 0 || pending != null;

  return (
    <div className="flex gap-4">
      {/* Chart + bubble markers */}
      <div ref={containerRef} className="relative flex-1 min-w-0">
        {children}
        <div
          className="absolute inset-0"
          style={{
            pointerEvents: bubbleMode ? "auto" : "none",
            cursor: bubbleMode ? "crosshair" : "default",
          }}
          onMouseDown={(e) => {
            if (!bubbleMode || pending) return;
            setStart(toNorm(e));
            setCurrent(toNorm(e));
          }}
          onMouseMove={(e) => {
            if (!bubbleMode || !start || pending) return;
            setCurrent(toNorm(e));
          }}
          onMouseUp={(e) => {
            if (!bubbleMode || !start) return;
            const end = toNorm(e);
            const region = {
              x: Math.min(start.x, end.x),
              y: Math.min(start.y, end.y),
              w: Math.abs(end.x - start.x),
              h: Math.abs(end.y - start.y),
            };
            setStart(null);
            setCurrent(null);
            if (region.w < 0.01 || region.h < 0.01) return;
            setPending(region);
          }}
        >
          {/* neutral region outline (draw / pending / selected) */}
          {outline && (
            <div
              className="absolute rounded-sm border-2 border-dashed border-primary/70 bg-primary/5"
              style={{
                left: pct(outline.x),
                top: pct(outline.y),
                width: pct(outline.w),
                height: pct(outline.h),
              }}
            />
          )}
          {/* numbered markers — clickable even when mode is off */}
          {bubbles.map((b) => (
            <button
              key={b.id}
              type="button"
              style={{
                left: pct(b.region_x! + b.region_w! / 2),
                top: pct(b.region_y!),
                background: b.rating ? RATING_DOT[b.rating] : "var(--color-primary)",
                pointerEvents: "auto",
              }}
              className="absolute -translate-x-1/2 -translate-y-1/2 flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold text-white shadow ring-2 ring-background"
              title={b.body}
              onMouseDown={(e) => e.stopPropagation()}
              onClick={() => setSelected(selected === b.id ? null : b.id)}
            >
              {b.number}
            </button>
          ))}
        </div>
      </div>

      {/* Right-side bubble panel */}
      {showPanel && (
        <aside className="w-64 shrink-0 rounded-lg border border-border bg-card p-3">
          <p className="text-sm font-semibold mb-2">
            {t("kpireview.bubble.panelTitle")}{" "}
            <span className="text-muted-foreground font-normal">({bubbles.length})</span>
          </p>

          {/* comment form for a freshly-drawn region */}
          {pending && (
            <div className="mb-3 rounded-md border border-primary/40 bg-primary/5 p-2.5 space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold">{t("kpireview.bubble.describe")}</span>
                <button className="text-muted-foreground hover:text-foreground" onClick={() => setPending(null)}>
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
              <Textarea
                autoFocus
                rows={3}
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder={t("kpireview.bubble.placeholder")}
              />
              <div className="flex items-center gap-2">
                <select
                  className="h-8 rounded-lg border border-border bg-background px-2 text-xs"
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
                  disabled={body.trim() === "" || save.isPending}
                  onClick={() => save.mutate()}
                >
                  {t("kpireview.bubble.save")}
                </Button>
              </div>
            </div>
          )}

          {/* list of bubbles */}
          {bubbles.length === 0 && !pending ? (
            <p className="text-xs text-muted-foreground">
              {bubbleMode ? t("kpireview.bubble.panelHint") : t("kpireview.bubble.panelEmpty")}
            </p>
          ) : (
            <ul className="space-y-1.5">
              {bubbles.map((b) => (
                <li
                  key={b.id}
                  className={`rounded-md border p-2 text-xs transition-colors ${
                    selected === b.id ? "border-primary bg-primary/5" : "border-border hover:bg-muted/50"
                  }`}
                >
                  <button
                    type="button"
                    onClick={() => setSelected(selected === b.id ? null : b.id)}
                    className="w-full text-left"
                  >
                    <span className="flex items-center gap-1.5">
                      <span
                        className="flex h-4 w-4 items-center justify-center rounded-full text-[10px] font-bold text-white"
                        style={{ background: b.rating ? RATING_DOT[b.rating] : "var(--color-primary)" }}
                      >
                        {b.number}
                      </span>
                      <span className="text-muted-foreground">{b.author_name ?? ""}</span>
                    </span>
                    <span className="mt-1 block whitespace-pre-wrap">{b.body}</span>
                  </button>
                  {selected === b.id && (
                    <div className="mt-2 space-y-1.5 border-t border-border pt-2">
                      <p className="text-[11px] text-muted-foreground">
                        {t("kpireview.measures.countLabel", { count: measureCount(b.id) })}
                      </p>
                      {isAdmin && (
                        <div className="flex items-center justify-between gap-2">
                          <Link
                            href="/kpi-review"
                            className="text-[11px] text-primary hover:underline"
                            onClick={(e) => e.stopPropagation()}
                          >
                            {t("kpireview.bubble.manage")}
                          </Link>
                          <button
                            type="button"
                            className="text-muted-foreground hover:text-destructive"
                            title={t("kpireview.bubble.deleteAria")}
                            onClick={(e) => {
                              e.stopPropagation();
                              setDeleteTarget(b);
                            }}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      )}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </aside>
      )}

      <DeleteDialog
        open={deleteTarget !== null}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
        title={t("kpireview.bubble.deleteTitle")}
        body={t("kpireview.bubble.deleteBody")}
        onConfirm={() => {
          if (deleteTarget) delBubble.mutate(deleteTarget.id);
        }}
        confirmDisabled={delBubble.isPending}
      />
    </div>
  );
}
