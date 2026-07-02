/**
 * FAIR editor canvas — the heart of the module.
 *
 * Renders the drawing (PDF page or image) at natural size inside a single
 * CSS-transformed wrapper that also hosts the SVG balloon overlay, so zoom/pan
 * moves and scales bubbles in lock-step. Owns the marking state machine
 * (drag rect → OCR → correct value → click to place tail → save), balloon drag,
 * multi-page navigation, and PDF export.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { fairApi, fetchDrawingBlob } from "@/lib/fairApi";
import type { FairBalloon, FairProjectDetail } from "@/lib/fairApi";
import { fairKeys } from "@/lib/queryKeys";
import {
  asRotation,
  clamp,
  clamp01,
  invRotatePx,
  nextRotation,
  rectFromCorners,
  rotatePx,
  rotatedDims,
  rotationCss,
  round6,
  sanitizeFilename,
} from "./geometry";
import type { NormRect, Point, Rotation } from "./geometry";
import {
  cropImageRegion,
  padCanvas,
  rotateCanvas,
  renderPdfRegionToCanvas,
} from "./cropRegion";
import { useZoomPan } from "./useZoomPan";
import { useFairOcr } from "./useFairOcr";
import type { OcrMode } from "./useFairOcr";
import { exportFairPdf } from "./fairExport";
import { DrawingSurface } from "./DrawingSurface";
import { BalloonLayer } from "./BalloonLayer";
import { FairToolbar } from "./FairToolbar";
import type { FairTool } from "./FairToolbar";
import { OcrCorrectionInput } from "./OcrCorrectionInput";

const MIN_REGION = 0.004;
// Zoom-proportional oversampling caps: sharp when zoomed in, bounded memory.
const MIN_DPR = 2;
const MAX_DPR = 6;
// OCR tries the crop in all four orientations, preferring the drag direction,
// and keeps the highest-confidence reading; it stops early once one is strong.
const OCR_ORIENTATIONS: Rotation[] = [0, 90, 180, 270];
const OCR_EARLY_CONFIDENCE = 80;

/**
 * Score an OCR candidate. Real letters/digits are rewarded; OCR-noise symbols
 * (typical of a wrong/rotated read, e.g. `< > | = ~ ^`) are heavily penalised,
 * so the correct orientation beats a high-confidence-but-garbage one. `clean`
 * marks a symbol-free reading fit for an early exit.
 */
function analyzeOcr(
  text: string,
  confidence: number,
  preferred: boolean,
): { score: number; clean: boolean } {
  const s = text.trim();
  const letters = (s.match(/[A-Za-zÄÖÜäöüß]/g) || []).length;
  const digits = (s.match(/\d/g) || []).length;
  const weird = (s.match(/[<>|~^`{}[\]\\_=]/g) || []).length;
  const alnum = letters + digits;
  if (alnum === 0) return { score: -Infinity, clean: false };
  const score = confidence + (preferred ? 5 : 0) + alnum * 2 - weird * 20;
  return { score, clean: weird === 0 };
}

/** Drag direction → preferred reading orientation (top-left→bottom-right = 0°). */
function preferredRotation(start: Point, current: Point): Rotation {
  const dx = current.x - start.x;
  const dy = current.y - start.y;
  if (dx >= 0 && dy >= 0) return 0;
  if (dx < 0 && dy < 0) return 180;
  if (dx >= 0 && dy < 0) return 270;
  return 90;
}

type Mark =
  | { phase: "idle" }
  | { phase: "rect"; start: Point; current: Point }
  | { phase: "ocr"; region: NormRect }
  // After OCR the value is shown (editable) and the NEXT click on the drawing
  // both places the tail AND confirms the value — no separate confirm step.
  | { phase: "await-tail"; region: NormRect; value: string };

export function FairEditorCanvas({
  project,
  registerReocr,
}: {
  project: FairProjectDetail;
  /** Hand a "re-run OCR for one balloon" function up to the parent so the
   *  results table can trigger it per row (drawing + OCR live here). */
  registerReocr?: (fn: (b: FairBalloon) => Promise<string | null>) => void;
}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const viewportRef = useRef<HTMLDivElement>(null);

  // ── Drawing bytes (object URL for display + ArrayBuffer for OCR/export) ──
  const { data: blob } = useQuery({
    queryKey: [...fairKeys.project(project.id), "file"],
    queryFn: () => fetchDrawingBlob(project.id),
    staleTime: Infinity,
    gcTime: Infinity,
  });
  const [drawing, setDrawing] = useState<{ url: string; buffer: ArrayBuffer } | null>(
    null,
  );
  useEffect(() => {
    if (!blob) return;
    const url = URL.createObjectURL(blob);
    let cancelled = false;
    void blob.arrayBuffer().then((buffer) => {
      if (!cancelled) setDrawing({ url, buffer });
    });
    return () => {
      cancelled = true;
      URL.revokeObjectURL(url);
      setDrawing(null);
    };
  }, [blob]);

  // `natural` is the CANONICAL (unrotated) page size. Balloons are always
  // stored in canonical normalized coords; rotation is a pure view transform.
  const [natural, setNatural] = useState<{ w: number; h: number } | null>(null);
  const [numPages, setNumPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [tool, setTool] = useState<FairTool>("add");
  const [rotation, setRotation] = useState<Rotation>(() =>
    asRotation(project.rotation),
  );
  const [renderDpr, setRenderDpr] = useState(MIN_DPR);
  // Global bubble size — persisted across sessions/projects via localStorage.
  const [balloonScale, setBalloonScale] = useState<number>(() => {
    const v = parseFloat(localStorage.getItem("fair.balloonScale") ?? "1");
    return Number.isFinite(v) && v > 0 ? clamp(v, 0.4, 3) : 1;
  });
  useEffect(() => {
    localStorage.setItem("fair.balloonScale", String(balloonScale));
  }, [balloonScale]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [mark, setMark] = useState<Mark>({ phase: "idle" });
  const [dragOverrides, setDragOverrides] = useState<Record<string, Point>>({});
  const [exporting, setExporting] = useState(false);

  // Visible (rotated) page dims drive zoom/pan/fit.
  const viewNatural = useMemo(
    () => (natural ? rotatedDims(natural.w, natural.h, rotation) : null),
    [natural, rotation],
  );

  const { transform, setTransform, fit, zoomByButton } = useZoomPan(
    viewportRef,
    viewNatural,
  );
  const ocr = useFairOcr();

  // Reset per-drawing state when the source changes (keep the saved rotation).
  useEffect(() => {
    setNatural(null);
    setNumPages(0);
    setCurrentPage(1);
    setRotation(asRotation(project.rotation));
    setMark({ phase: "idle" });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id]);

  // Rotate one step and persist the new orientation (no refetch → no flicker).
  const handleRotate = useCallback(() => {
    const nr = nextRotation(rotation);
    setRotation(nr);
    void fairApi.patchProject(project.id, { rotation: nr }).catch(() => {});
  }, [rotation, project.id]);

  // Raise the PDF backing-store resolution with zoom (debounced) so dimension
  // text stays sharp instead of upscaling a low-DPI raster. Capped by page size
  // so an A1/A0 sheet doesn't blow up the canvas (long edge ≲ 5000 backing px).
  useEffect(() => {
    const longEdge = natural ? Math.max(natural.w, natural.h) : 1000;
    const cap = clamp(Math.floor(5000 / longEdge), MIN_DPR, MAX_DPR);
    const target = clamp(Math.ceil(transform.scale) + 1, MIN_DPR, cap);
    if (target === renderDpr) return;
    const id = window.setTimeout(() => setRenderDpr(target), 200);
    return () => window.clearTimeout(id);
  }, [transform.scale, renderDpr, natural]);

  // Persist the discovered PDF page count once.
  useEffect(() => {
    if (numPages > 0 && numPages !== project.page_count) {
      void fairApi
        .patchProject(project.id, { page_count: numPages })
        .then(() =>
          queryClient.invalidateQueries({ queryKey: fairKeys.project(project.id) }),
        )
        .catch(() => {});
    }
  }, [numPages, project.page_count, project.id, queryClient]);

  // OCR image source (image kind): a natural-size Image for cropping.
  const imgSourceRef = useRef<HTMLImageElement | null>(null);
  useEffect(() => {
    imgSourceRef.current = null;
    if (drawing && project.file_kind === "image") {
      const img = new Image();
      img.onload = () => {
        imgSourceRef.current = img;
      };
      img.src = drawing.url;
    }
  }, [drawing, project.file_kind]);

  // Screen → CANONICAL normalized point: undo zoom/pan, then undo rotation.
  const clientToNorm = useCallback(
    (clientX: number, clientY: number): Point => {
      const el = viewportRef.current;
      if (!el || !natural) return { x: 0, y: 0 };
      const rect = el.getBoundingClientRect();
      const rx = (clientX - rect.left - transform.tx) / transform.scale;
      const ry = (clientY - rect.top - transform.ty) / transform.scale;
      const c = invRotatePx(rx, ry, natural.w, natural.h, rotation);
      return { x: clamp01(c.x / natural.w), y: clamp01(c.y / natural.h) };
    },
    [transform, natural, rotation],
  );

  const invalidate = useCallback(
    () => queryClient.invalidateQueries({ queryKey: fairKeys.project(project.id) }),
    [queryClient, project.id],
  );

  // The padded crop of the last marked region, reused by "Maß"/"Text" re-checks.
  const ocrCropRef = useRef<{ crop: HTMLCanvasElement; preferred: Rotation } | null>(
    null,
  );
  const [rechecking, setRechecking] = useState(false);

  // Recognise `padded` in every orientation (preferred first) with the given
  // mode and return the best-scoring reading.
  const recognizeBest = useCallback(
    async (padded: HTMLCanvasElement, preferred: Rotation, mode: OcrMode) => {
      const order = [preferred, ...OCR_ORIENTATIONS.filter((r) => r !== preferred)];
      let best = { text: "", score: -Infinity };
      for (const rot of order) {
        const { text: guess, confidence } = await ocr.recognize(
          rotateCanvas(padded, rot),
          mode,
        );
        const a = analyzeOcr(guess, confidence, rot === preferred);
        if (a.score > best.score) best = { text: guess, score: a.score };
        if (a.clean && confidence >= OCR_EARLY_CONFIDENCE) break;
      }
      return best.text;
    },
    [ocr],
  );

  const runOcr = useCallback(
    async (region: NormRect, preferred: Rotation) => {
      let text = "";
      try {
        // Render the region at high resolution — independent of display zoom.
        let crop: HTMLCanvasElement | null = null;
        if (project.file_kind === "image") {
          const src = imgSourceRef.current;
          if (src) crop = cropImageRegion(src, region);
        } else if (drawing) {
          crop = await renderPdfRegionToCanvas(drawing.buffer, currentPage, region);
        }
        if (crop) {
          // White quiet-zone around the text improves recognition markedly.
          const padded = padCanvas(crop);
          ocrCropRef.current = { crop: padded, preferred };
          text = await recognizeBest(padded, preferred, "auto");
        } else {
          ocrCropRef.current = null;
        }
      } catch (e) {
        console.error("FAIR OCR failed", e);
      }
      setMark({ phase: "await-tail", region, value: text });
    },
    [project.file_kind, drawing, currentPage, recognizeBest],
  );

  // Re-run OCR on the same region forcing "measure" (digits) or "text".
  const recheckOcr = useCallback(
    async (mode: OcrMode) => {
      const cached = ocrCropRef.current;
      if (!cached) return;
      setRechecking(true);
      try {
        const text = await recognizeBest(cached.crop, cached.preferred, mode);
        setMark((m) => (m.phase === "await-tail" ? { ...m, value: text } : m));
      } finally {
        setRechecking(false);
      }
    },
    [recognizeBest],
  );

  // Re-run OCR for an existing balloon's stored region (on its own page).
  // Returns the fresh text, or null if nothing could be rendered/read.
  const reocrBalloon = useCallback(
    async (b: FairBalloon): Promise<string | null> => {
      try {
        const region: NormRect = {
          x: b.region_x,
          y: b.region_y,
          w: b.region_w,
          h: b.region_h,
        };
        let crop: HTMLCanvasElement | null = null;
        if (project.file_kind === "image") {
          const src = imgSourceRef.current;
          if (src) crop = cropImageRegion(src, region);
        } else if (drawing) {
          crop = await renderPdfRegionToCanvas(drawing.buffer, b.page_no, region);
        }
        if (!crop) return null;
        return await recognizeBest(padCanvas(crop), 0, "auto");
      } catch (e) {
        console.error("FAIR re-OCR failed", e);
        return null;
      }
    },
    [project.file_kind, drawing, recognizeBest],
  );

  useEffect(() => {
    registerReocr?.(reocrBalloon);
  }, [registerReocr, reocrBalloon]);

  const commitCreate = useCallback(
    async (region: NormRect, value: string, tail: Point) => {
      try {
        await fairApi.createBalloon(project.id, {
          page_no: currentPage,
          region_x: round6(region.x),
          region_y: round6(region.y),
          region_w: round6(region.w),
          region_h: round6(region.h),
          tail_x: round6(tail.x),
          tail_y: round6(tail.y),
          value_text: value,
        });
        await invalidate();
      } catch (e) {
        toast.error((e as Error).message);
      }
    },
    [project.id, currentPage, invalidate],
  );

  const onTailChange = useCallback(
    (id: string, tail: Point, commit: boolean) => {
      setDragOverrides((o) => ({ ...o, [id]: tail }));
      if (!commit) return;
      void (async () => {
        try {
          await fairApi.patchBalloon(id, {
            tail_x: round6(tail.x),
            tail_y: round6(tail.y),
          });
          await invalidate();
        } catch (e) {
          toast.error((e as Error).message);
        } finally {
          setDragOverrides((o) => {
            const next = { ...o };
            delete next[id];
            return next;
          });
        }
      })();
    },
    [invalidate],
  );

  // ── Viewport pointer handlers (pan + marking) ──
  const panRef = useRef<{ cx: number; cy: number; tx: number; ty: number } | null>(
    null,
  );

  const startPan = (e: React.PointerEvent<HTMLDivElement>) => {
    panRef.current = {
      cx: e.clientX,
      cy: e.clientY,
      tx: transform.tx,
      ty: transform.ty,
    };
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    // Right mouse button pans in ANY tool mode (like a CAD viewer).
    if (e.button === 2) {
      e.preventDefault();
      startPan(e);
      return;
    }
    if (e.button !== 0) return; // ignore middle/back/forward
    if (tool === "pan") {
      startPan(e);
      return;
    }
    // add mode
    e.preventDefault();
    if (mark.phase === "await-tail") {
      const tail = clientToNorm(e.clientX, e.clientY);
      const { region, value } = mark;
      setMark({ phase: "idle" });
      void commitCreate(region, value, tail);
      return;
    }
    if (mark.phase === "idle") {
      const p = clientToNorm(e.clientX, e.clientY);
      setMark({ phase: "rect", start: p, current: p });
      e.currentTarget.setPointerCapture(e.pointerId);
    }
  };

  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (panRef.current) {
      const { cx, cy, tx, ty } = panRef.current;
      setTransform({
        scale: transform.scale,
        tx: tx + (e.clientX - cx),
        ty: ty + (e.clientY - cy),
      });
      return;
    }
    if (mark.phase === "rect") {
      setMark({ ...mark, current: clientToNorm(e.clientX, e.clientY) });
    }
  };

  const onPointerUp = (e: React.PointerEvent<HTMLDivElement>) => {
    try {
      e.currentTarget.releasePointerCapture(e.pointerId);
    } catch {
      /* not captured */
    }
    if (panRef.current) {
      panRef.current = null;
      return;
    }
    if (mark.phase === "rect") {
      const region = rectFromCorners(mark.start, mark.current);
      if (region.w < MIN_REGION || region.h < MIN_REGION) {
        setMark({ phase: "idle" });
        return;
      }
      const preferred = preferredRotation(mark.start, mark.current);
      setMark({ phase: "ocr", region });
      void runOcr(region, preferred);
    }
  };

  // Escape cancels the in-progress marking / clears selection.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setMark({ phase: "idle" });
        setSelectedId(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  const pageBalloons = useMemo<FairBalloon[]>(
    () =>
      project.balloons
        .filter((b) => b.page_no === currentPage)
        .map((b) => {
          const o = dragOverrides[b.id];
          return o ? { ...b, tail_x: o.x, tail_y: o.y } : b;
        }),
    [project.balloons, currentPage, dragOverrides],
  );

  const markRect: NormRect | null = useMemo(() => {
    if (mark.phase === "rect") return rectFromCorners(mark.start, mark.current);
    if (mark.phase === "ocr" || mark.phase === "await-tail") return mark.region;
    return null;
  }, [mark]);

  const ocrAnchor = useMemo(() => {
    if (!natural) return null;
    if (mark.phase !== "ocr" && mark.phase !== "await-tail") return null;
    // canonical region centre (px) → rotated-box px → screen px.
    const cx = (mark.region.x + mark.region.w / 2) * natural.w;
    const cy = (mark.region.y + mark.region.h / 2) * natural.h;
    const r = rotatePx(cx, cy, natural.w, natural.h, rotation);
    return {
      x: r.x * transform.scale + transform.tx,
      y: r.y * transform.scale + transform.ty,
    };
  }, [mark, natural, transform, rotation]);

  const handleExport = useCallback(async () => {
    if (!drawing || !natural) return;
    setExporting(true);
    try {
      const base = sanitizeFilename(project.part_number || project.name || "drawing");
      const fileName = `${base}_ballooned.pdf`;
      if (project.file_kind === "image") {
        await exportFairPdf({
          kind: "image",
          fileName,
          imageUrl: drawing.url,
          rotation,
          sizeScale: balloonScale,
          balloons: project.balloons,
        });
      } else {
        const byPage = new Map<number, FairBalloon[]>();
        for (const b of project.balloons) {
          const arr = byPage.get(b.page_no) ?? [];
          arr.push(b);
          byPage.set(b.page_no, arr);
        }
        await exportFairPdf({
          kind: "pdf",
          fileName,
          pdfData: drawing.buffer,
          rotation,
          sizeScale: balloonScale,
          balloonsByPage: byPage,
        });
      }
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setExporting(false);
    }
  }, [drawing, natural, project, rotation, balloonScale]);

  const hint =
    tool === "add" && mark.phase === "await-tail"
      ? t("fair.hint.placeTail")
      : tool === "add" && mark.phase === "idle"
        ? t("fair.hint.markRegion")
        : null;

  return (
    <div className="space-y-2">
      <FairToolbar
        tool={tool}
        onToolChange={setTool}
        onZoomIn={() => zoomByButton(1.2)}
        onZoomOut={() => zoomByButton(1 / 1.2)}
        onFit={fit}
        onRotate={handleRotate}
        onBubbleSmaller={() => setBalloonScale((s) => clamp(s / 1.18, 0.4, 3))}
        onBubbleLarger={() => setBalloonScale((s) => clamp(s * 1.18, 0.4, 3))}
        page={currentPage}
        pageCount={numPages || project.page_count}
        onPage={(p) => {
          setCurrentPage(p);
          setMark({ phase: "idle" });
        }}
        onExport={() => void handleExport()}
        exporting={exporting}
        ocrReady={ocr.ready || ocr.failed}
      />

      <div
        ref={viewportRef}
        className="relative h-[82vh] w-full overflow-hidden rounded-md border bg-muted/40"
        style={{
          cursor: panRef.current
            ? "grabbing"
            : tool === "pan"
              ? "grab"
              : "crosshair",
          touchAction: "none",
        }}
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerUp}
        onPointerCancel={onPointerUp}
        onContextMenu={(e) => e.preventDefault()}
      >
        {!drawing && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        )}

        {drawing && (
          // Outer = zoom/pan layer, sized to the VISIBLE (rotated) bounding box.
          <div
            style={{
              position: "absolute",
              top: 0,
              left: 0,
              width: viewNatural ? viewNatural.w : "auto",
              height: viewNatural ? viewNatural.h : "auto",
              transform: `translate(${transform.tx}px, ${transform.ty}px) scale(${transform.scale})`,
              transformOrigin: "0 0",
            }}
          >
            {/* Inner = rotation layer, sized to the CANONICAL page. Drawing +
                overlay live here so balloons rotate with the drawing. */}
            <div
              style={{
                position: "absolute",
                top: 0,
                left: 0,
                width: natural ? natural.w : "auto",
                height: natural ? natural.h : "auto",
                transform: natural
                  ? rotationCss(natural.w, natural.h, rotation)
                  : "none",
                transformOrigin: "0 0",
              }}
            >
              <DrawingSurface
                url={drawing.url}
                kind={project.file_kind}
                pageNo={currentPage}
                naturalW={natural?.w ?? null}
                naturalH={natural?.h ?? null}
                renderDpr={renderDpr}
                onNatural={setNatural}
                onNumPages={setNumPages}
              />
              {natural && (
                <BalloonLayer
                  pageW={natural.w}
                  pageH={natural.h}
                  sizeScale={balloonScale}
                  rotation={rotation}
                  balloons={pageBalloons}
                  markRect={markRect}
                  selectedId={selectedId}
                  clientToNorm={clientToNorm}
                  onSelect={setSelectedId}
                  onTailChange={onTailChange}
                />
              )}
            </div>
          </div>
        )}

        {ocrAnchor && (mark.phase === "ocr" || mark.phase === "await-tail") && (
          <OcrCorrectionInput
            screenX={ocrAnchor.x}
            screenY={ocrAnchor.y}
            busy={mark.phase === "ocr"}
            rechecking={rechecking}
            value={mark.phase === "await-tail" ? mark.value : ""}
            onChange={(v) =>
              setMark((m) =>
                m.phase === "await-tail" ? { ...m, value: v } : m,
              )
            }
            onRecheck={(mode) => void recheckOcr(mode)}
            onCancel={() => setMark({ phase: "idle" })}
          />
        )}

        {hint && (
          <div className="pointer-events-none absolute bottom-3 left-1/2 -translate-x-1/2 rounded-full bg-foreground/80 px-3 py-1 text-xs text-background">
            {hint}
          </div>
        )}
      </div>
    </div>
  );
}
