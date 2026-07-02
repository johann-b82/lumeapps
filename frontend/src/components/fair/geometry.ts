/**
 * Pure coordinate helpers for the FAIR editor. Kept free of React/DOM so they
 * are trivially unit-testable. All normalized values are fractions [0,1] of the
 * drawing's natural page size; the on-screen transform is
 * `translate(tx,ty) scale(scale)` with transform-origin 0 0.
 */
import type { FairBalloon } from "@/lib/fairApi";

export interface Transform {
  scale: number;
  tx: number;
  ty: number;
}

export interface Point {
  x: number;
  y: number;
}

export interface NormRect {
  x: number;
  y: number;
  w: number;
  h: number;
}

export function clamp01(v: number): number {
  return v < 0 ? 0 : v > 1 ? 1 : v;
}

export function clamp(v: number, lo: number, hi: number): number {
  return v < lo ? lo : v > hi ? hi : v;
}

/**
 * Convert a pointer position (viewport-relative px) to a normalized page point,
 * inverting the current zoom/pan transform. `offsetX/Y` are `clientX - rect.left`.
 */
export function screenToNorm(
  offsetX: number,
  offsetY: number,
  t: Transform,
  naturalW: number,
  naturalH: number,
): Point {
  const pageX = (offsetX - t.tx) / t.scale;
  const pageY = (offsetY - t.ty) / t.scale;
  return { x: clamp01(pageX / naturalW), y: clamp01(pageY / naturalH) };
}

/** Forward transform: normalized page point -> viewport-relative px. */
export function normToScreen(
  p: Point,
  t: Transform,
  naturalW: number,
  naturalH: number,
): Point {
  return {
    x: p.x * naturalW * t.scale + t.tx,
    y: p.y * naturalH * t.scale + t.ty,
  };
}

/** Build a normalized rect from two normalized corners (drag start/end). */
export function rectFromCorners(a: Point, b: Point): NormRect {
  const x = Math.min(a.x, b.x);
  const y = Math.min(a.y, b.y);
  return { x, y, w: Math.abs(a.x - b.x), h: Math.abs(a.y - b.y) };
}

/** Arrow tip = centre of the marked region (derived, never stored). */
export function regionCenter(b: {
  region_x: number;
  region_y: number;
  region_w: number;
  region_h: number;
}): Point {
  return { x: b.region_x + b.region_w / 2, y: b.region_y + b.region_h / 2 };
}

/** Round a normalized value to 6 decimals for a compact, idempotent payload. */
export function round6(v: number): number {
  return Math.round(v * 1_000_000) / 1_000_000;
}

/**
 * Fit-to-view transform: scale so the whole page fits inside the viewport with
 * a small margin, centred.
 */
export function fitTransform(
  viewportW: number,
  viewportH: number,
  naturalW: number,
  naturalH: number,
  margin = 24,
): Transform {
  const availW = Math.max(1, viewportW - margin * 2);
  const availH = Math.max(1, viewportH - margin * 2);
  const scale = Math.min(availW / naturalW, availH / naturalH);
  const tx = (viewportW - naturalW * scale) / 2;
  const ty = (viewportH - naturalH * scale) / 2;
  return { scale, tx, ty };
}

/**
 * Zoom around a fixed viewport anchor (cursor) so the page point under the
 * cursor stays put. `factor` > 1 zooms in.
 */
export function zoomAround(
  t: Transform,
  anchorX: number,
  anchorY: number,
  factor: number,
  minScale = 0.1,
  maxScale = 12,
): Transform {
  const scale = clamp(t.scale * factor, minScale, maxScale);
  const k = scale / t.scale;
  return {
    scale,
    tx: anchorX - (anchorX - t.tx) * k,
    ty: anchorY - (anchorY - t.ty) * k,
  };
}

// ── Rotation (view-only; balloons are always stored in canonical coords) ──

export type Rotation = 0 | 90 | 180 | 270;

export function nextRotation(rot: Rotation): Rotation {
  return (((rot + 90) % 360) as Rotation);
}

/** Normalise any number to the nearest valid Rotation (0/90/180/270). */
export function asRotation(v: number): Rotation {
  const r = ((((Math.round(v / 90) * 90) % 360) + 360) % 360) as Rotation;
  return r === 90 || r === 180 || r === 270 ? r : 0;
}

/** Visible bounding-box dims after rotating a canonical wc×hc page clockwise. */
export function rotatedDims(
  wc: number,
  hc: number,
  rot: Rotation,
): { w: number; h: number } {
  return rot === 90 || rot === 270 ? { w: hc, h: wc } : { w: wc, h: hc };
}

/** Canonical px → rotated-box px (content rotated clockwise by `rot`). */
export function rotatePx(
  cx: number,
  cy: number,
  wc: number,
  hc: number,
  rot: Rotation,
): Point {
  switch (rot) {
    case 90:
      return { x: hc - cy, y: cx };
    case 180:
      return { x: wc - cx, y: hc - cy };
    case 270:
      return { x: cy, y: wc - cx };
    default:
      return { x: cx, y: cy };
  }
}

/** Rotated-box px → canonical px (inverse of {@link rotatePx}). */
export function invRotatePx(
  rx: number,
  ry: number,
  wc: number,
  hc: number,
  rot: Rotation,
): Point {
  switch (rot) {
    case 90:
      return { x: ry, y: hc - rx };
    case 180:
      return { x: wc - rx, y: hc - ry };
    case 270:
      return { x: wc - ry, y: rx };
    default:
      return { x: rx, y: ry };
  }
}

/** CSS transform (origin 0 0) that rotates the canonical layer into its box. */
export function rotationCss(wc: number, hc: number, rot: Rotation): string {
  switch (rot) {
    case 90:
      return `translate(${hc}px, 0px) rotate(90deg)`;
    case 180:
      return `translate(${wc}px, ${hc}px) rotate(180deg)`;
    case 270:
      return `translate(0px, ${wc}px) rotate(270deg)`;
    default:
      return "none";
  }
}

/** Shared balloon colours — kept identical between the live overlay and export. */
export const FAIR_COLORS = {
  stroke: "#dc2626",
  bubbleFill: "#ffffff",
  text: "#dc2626",
  region: "#dc2626",
} as const;

export interface BalloonPixels {
  tip: Point;
  tail: Point;
  region: { x: number; y: number; w: number; h: number };
  r: number;
  fontSize: number;
  /** Solid filled leader: a wedge (triangle) from the bubble to the tip. */
  arrowPoints: string;
}

/**
 * Points of a solid filled arrow wedge: a sharp point at `tip` widening to a
 * base at the bubble edge (radius `r`) on the side facing the tip.
 */
export function wedgePoints(tail: Point, tip: Point, r: number): string {
  const dx = tip.x - tail.x;
  const dy = tip.y - tail.y;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  const px = -uy;
  const py = ux;
  const baseX = tail.x + ux * r * 0.9;
  const baseY = tail.y + uy * r * 0.9;
  const bw = r * 0.8;
  return (
    `${tip.x},${tip.y} ` +
    `${baseX + px * bw},${baseY + py * bw} ` +
    `${baseX - px * bw},${baseY - py * bw}`
  );
}

/**
 * Point where the ray from a rectangle's centre toward `target` crosses the
 * rectangle boundary, pushed `gap` px further out. Used to place the arrow tip
 * just OUTSIDE the marked region (on the side facing the bubble).
 */
export function rectExitPoint(
  cx: number,
  cy: number,
  hw: number,
  hh: number,
  target: Point,
  gap: number,
): Point {
  const dx = target.x - cx;
  const dy = target.y - cy;
  if (dx === 0 && dy === 0) return { x: cx, y: cy };
  const tX = dx !== 0 ? hw / Math.abs(dx) : Infinity;
  const tY = dy !== 0 ? hh / Math.abs(dy) : Infinity;
  const tEdge = Math.min(tX, tY);
  const bx = cx + dx * tEdge;
  const by = cy + dy * tEdge;
  const len = Math.hypot(dx, dy);
  return { x: bx + (dx / len) * gap, y: by + (dy / len) * gap };
}

/**
 * Resolve a balloon to pixel geometry for a page of size (pageW,pageH). Shared
 * by the on-screen SVG overlay AND the PDF export so both render identically.
 * The bubble radius scales with the page so it stays proportional under zoom.
 * The tip sits just OUTSIDE the marked rectangle so it never covers the value.
 */
export function balloonPixels(
  b: FairBalloon,
  pageW: number,
  pageH: number,
  sizeScale = 1,
): BalloonPixels {
  const region = {
    x: b.region_x * pageW,
    y: b.region_y * pageH,
    w: b.region_w * pageW,
    h: b.region_h * pageH,
  };
  const cx = region.x + region.w / 2;
  const cy = region.y + region.h / 2;
  const tail = { x: b.tail_x * pageW, y: b.tail_y * pageH };
  const base = Math.min(pageW, pageH);
  const r = Math.max(9, base * 0.02) * sizeScale;
  const tip = rectExitPoint(cx, cy, region.w / 2, region.h / 2, tail, r * 0.4);
  return {
    tip,
    tail,
    region,
    r,
    fontSize: r * 1.05,
    arrowPoints: wedgePoints(tail, tip, r),
  };
}

/**
 * Make a string safe as a Windows filename component: strip characters that
 * are invalid in file/folder names (`< > : " / \ | ? *`, control chars),
 * collapse whitespace to `_`, trim leading/trailing separators, and cap length.
 * Returns `fallback` if nothing usable remains.
 */
export function sanitizeFilename(s: string, fallback = "drawing"): string {
  const cleaned = s
    .replace(/[<>:"/\\|?*-]/g, "_")
    .replace(/\s+/g, "_")
    .replace(/_+/g, "_")
    .replace(/^[_.]+|[_.]+$/g, "")
    .slice(0, 100);
  return cleaned || fallback;
}

/** Triangle points for an arrowhead at `tip`, pointing away from `from`. */
export function arrowHeadPoints(from: Point, tip: Point, size: number): string {
  const dx = tip.x - from.x;
  const dy = tip.y - from.y;
  const len = Math.hypot(dx, dy) || 1;
  const ux = dx / len;
  const uy = dy / len;
  // Perpendicular.
  const px = -uy;
  const py = ux;
  const baseX = tip.x - ux * size;
  const baseY = tip.y - uy * size;
  const half = size * 0.55;
  const p1 = `${tip.x},${tip.y}`;
  const p2 = `${baseX + px * half},${baseY + py * half}`;
  const p3 = `${baseX - px * half},${baseY - py * half}`;
  return `${p1} ${p2} ${p3}`;
}

/** Escape a cell for tab-separated Excel paste (tabs/newlines break columns). */
function tsvCell(v: string): string {
  return v.replace(/[\t\r\n]+/g, " ").trim();
}

/** Build a TSV table (header + rows) for clipboard paste into Excel. */
export function buildTsv(
  rows: readonly Pick<FairBalloon, "number" | "value_text">[],
  header: readonly [string, string] = ["Nr", "Wert"],
): string {
  const lines = [header.join("\t")];
  for (const r of [...rows].sort((a, b) => a.number - b.number)) {
    lines.push(`${r.number}\t${tsvCell(r.value_text)}`);
  }
  return lines.join("\r\n");
}

/** Build a CSV table (semicolon-separated — the German Excel default). */
export function buildCsv(
  rows: readonly Pick<FairBalloon, "number" | "value_text">[],
  header: readonly [string, string] = ["Nr", "Wert"],
): string {
  const cell = (v: string) => `"${v.replace(/"/g, '""')}"`;
  const lines = [header.map(cell).join(";")];
  for (const r of [...rows].sort((a, b) => a.number - b.number)) {
    lines.push(`${r.number};${cell(r.value_text)}`);
  }
  return lines.join("\r\n");
}
