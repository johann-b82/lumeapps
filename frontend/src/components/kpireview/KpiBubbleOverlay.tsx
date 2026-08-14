import { useRef, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Plus, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/auth/useAuth";
import { kpiReviewKeys } from "@/lib/queryKeys";
import {
  fetchKpiComments,
  createKpiComment,
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

/**
 * Overlay a KPI chart with FAIR-style bubbles: toggle "add", drag a region on
 * the chart, a numbered bubble appears and a comment box opens to describe the
 * problem. Regions are stored normalized (0..1) so they stay put across sizes.
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
  const containerRef = useRef<HTMLDivElement>(null);

  const comments = useQuery({
    queryKey: kpiReviewKeys.comments(kpiKey),
    queryFn: () => fetchKpiComments(kpiKey),
  });
  const bubbles = (comments.data ?? []).filter(
    (c) => c.region_x != null && c.number != null,
  );

  const [adding, setAdding] = useState(false);
  const [start, setStart] = useState<Norm | null>(null);
  const [current, setCurrent] = useState<Norm | null>(null);
  const [pending, setPending] = useState<Region | null>(null);
  const [openBubble, setOpenBubble] = useState<string | null>(null);
  const [body, setBody] = useState("");
  const [rating, setRating] = useState<KpiRating | "">("");

  const toNorm = (e: React.MouseEvent): Norm => {
    const r = containerRef.current!.getBoundingClientRect();
    return { x: clamp01((e.clientX - r.left) / r.width), y: clamp01((e.clientY - r.top) / r.height) };
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

  const drawRect =
    start && current
      ? {
          x: Math.min(start.x, current.x),
          y: Math.min(start.y, current.y),
          w: Math.abs(current.x - start.x),
          h: Math.abs(current.y - start.y),
        }
      : null;

  const pct = (v: number) => `${v * 100}%`;

  return (
    <div className="relative" ref={containerRef}>
      {children}

      {/* Bubble-Layer */}
      <div
        className="absolute inset-0"
        style={{ pointerEvents: adding ? "auto" : "none", cursor: adding ? "crosshair" : "default" }}
        onMouseDown={(e) => {
          if (!adding || pending) return;
          setStart(toNorm(e));
          setCurrent(toNorm(e));
        }}
        onMouseMove={(e) => {
          if (!adding || !start || pending) return;
          setCurrent(toNorm(e));
        }}
        onMouseUp={(e) => {
          if (!adding || !start) return;
          const end = toNorm(e);
          const region = {
            x: Math.min(start.x, end.x),
            y: Math.min(start.y, end.y),
            w: Math.abs(end.x - start.x),
            h: Math.abs(end.y - start.y),
          };
          setStart(null);
          setCurrent(null);
          if (region.w < 0.01 || region.h < 0.01) return; // ignore stray clicks
          setPending(region);
          setAdding(false);
        }}
      >
        {/* vorhandene Bubbles */}
        {bubbles.map((b) => (
          <div key={b.id} style={{ pointerEvents: "auto" }}>
            <div
              className="absolute rounded-sm border-2"
              style={{
                left: pct(b.region_x!),
                top: pct(b.region_y!),
                width: pct(b.region_w!),
                height: pct(b.region_h!),
                borderColor: b.rating ? RATING_DOT[b.rating] : "var(--color-destructive)",
                background: "color-mix(in srgb, var(--color-destructive) 8%, transparent)",
              }}
            />
            <button
              type="button"
              onClick={() => setOpenBubble(openBubble === b.id ? null : b.id)}
              className="absolute -translate-x-1/2 -translate-y-1/2 flex h-6 w-6 items-center justify-center rounded-full text-xs font-bold text-white shadow"
              style={{
                left: pct(b.region_x! + b.region_w! / 2),
                top: pct(b.region_y!),
                background: b.rating ? RATING_DOT[b.rating] : "var(--color-destructive)",
              }}
              title={b.body}
            >
              {b.number}
            </button>
            {openBubble === b.id && (
              <div
                className="absolute z-10 w-64 rounded-md border border-border bg-popover p-2.5 text-xs text-popover-foreground shadow-lg"
                style={{ left: pct(b.region_x!), top: `calc(${pct(b.region_y! + b.region_h!)} + 6px)`, pointerEvents: "auto" }}
              >
                <div className="mb-1 flex items-center gap-1.5 text-muted-foreground">
                  <span className="font-semibold text-foreground">#{b.number}</span>
                  {b.rating && (
                    <span className="inline-block h-2 w-2 rounded-full" style={{ background: RATING_DOT[b.rating] }} />
                  )}
                  <span className="ml-auto">{b.author_name ?? ""}</span>
                </div>
                <p className="whitespace-pre-wrap">{b.body}</p>
              </div>
            )}
          </div>
        ))}

        {/* Live-Auswahlrechteck */}
        {drawRect && (
          <div
            className="absolute rounded-sm border-2 border-dashed border-primary bg-primary/10"
            style={{ left: pct(drawRect.x), top: pct(drawRect.y), width: pct(drawRect.w), height: pct(drawRect.h) }}
          />
        )}
      </div>

      {/* Add-Button */}
      {isAdmin && !pending && (
        <Button
          size="sm"
          variant={adding ? "secondary" : "outline"}
          className="absolute right-2 top-2 z-20 gap-1"
          onClick={() => {
            setAdding((v) => !v);
            setStart(null);
            setCurrent(null);
          }}
        >
          <Plus className="h-4 w-4" />
          {adding ? t("kpireview.bubble.cancel") : t("kpireview.bubble.add")}
        </Button>
      )}

      {/* Kommentar-Popup nach dem Aufziehen */}
      {pending && (
        <div
          className="absolute z-30 w-72 rounded-lg border border-border bg-popover p-3 shadow-xl"
          style={{ left: pct(pending.x), top: `calc(${pct(pending.y + pending.h)} + 6px)`, maxWidth: "90%" }}
        >
          <div className="mb-2 flex items-center justify-between">
            <span className="text-sm font-semibold">{t("kpireview.bubble.describe")}</span>
            <button className="text-muted-foreground hover:text-foreground" onClick={() => setPending(null)}>
              <X className="h-4 w-4" />
            </button>
          </div>
          <Textarea
            autoFocus
            rows={3}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            placeholder={t("kpireview.bubble.placeholder")}
          />
          <div className="mt-2 flex items-center gap-2">
            <select
              className="h-8 rounded-lg border border-border bg-background px-2 text-sm"
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
    </div>
  );
}
