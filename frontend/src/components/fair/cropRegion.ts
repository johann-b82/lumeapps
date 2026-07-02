/**
 * Native-resolution region rendering for OCR. Always samples the SHARPEST
 * available source — the image's natural pixels, or a per-region high-scale
 * pdf.js render — never the on-screen, zoom-dependent canvas. The marked region
 * is rendered so its long edge reaches a target pixel size, so OCR quality does
 * NOT depend on how far the user zoomed in.
 */
import { pdfjs } from "react-pdf";
import type { NormRect, Rotation } from "./geometry";

/** Target long-edge pixels for the OCR crop (independent of display zoom). */
export const OCR_TARGET_LONG_PX = 1400;

/** Add a white quiet-zone border around a canvas — Tesseract reads text with
 *  margin far more reliably than text touching the crop edges. */
export function padCanvas(
  src: HTMLCanvasElement,
  pad?: number,
): HTMLCanvasElement {
  const p = pad ?? Math.max(14, Math.round(Math.min(src.width, src.height) * 0.12));
  const out = document.createElement("canvas");
  out.width = src.width + 2 * p;
  out.height = src.height + 2 * p;
  const ctx = out.getContext("2d");
  if (ctx) {
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, out.width, out.height);
    ctx.drawImage(src, p, p);
  }
  return out;
}

/** Return a copy of `src` rotated clockwise by `rot` (0/90/180/270). */
export function rotateCanvas(
  src: HTMLCanvasElement,
  rot: Rotation,
): HTMLCanvasElement {
  if (rot === 0) return src;
  const swap = rot === 90 || rot === 270;
  const out = document.createElement("canvas");
  out.width = swap ? src.height : src.width;
  out.height = swap ? src.width : src.height;
  const ctx = out.getContext("2d");
  if (ctx) {
    ctx.translate(out.width / 2, out.height / 2);
    ctx.rotate((rot * Math.PI) / 180);
    ctx.drawImage(src, -src.width / 2, -src.height / 2);
  }
  return out;
}

/**
 * Crop a normalized region out of an image, upscaled so the long edge reaches
 * `targetLongPx` (bounded by `maxScale` since upscaling a raster adds no real
 * detail).
 */
export function cropImageRegion(
  img: HTMLImageElement,
  region: NormRect,
  targetLongPx = OCR_TARGET_LONG_PX,
  maxScale = 4,
): HTMLCanvasElement {
  const natW = img.naturalWidth;
  const natH = img.naturalHeight;
  const cw = Math.max(1, region.w * natW);
  const ch = Math.max(1, region.h * natH);
  const scale = Math.min(maxScale, Math.max(1, targetLongPx / Math.max(cw, ch)));
  const outW = Math.max(1, Math.ceil(cw * scale));
  const outH = Math.max(1, Math.ceil(ch * scale));
  const canvas = document.createElement("canvas");
  canvas.width = outW;
  canvas.height = outH;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, outW, outH);
    ctx.drawImage(img, region.x * natW, region.y * natH, cw, ch, 0, 0, outW, outH);
  }
  return canvas;
}

/**
 * Render ONLY the marked region of a PDF page into a canvas, at a scale chosen
 * so the region's long edge reaches `targetLongPx` (bounded by `maxEdge`).
 * Because a PDF is vector, this yields crisp text at any region size regardless
 * of the on-screen zoom.
 */
export async function renderPdfRegionToCanvas(
  fileData: ArrayBuffer,
  pageNo: number,
  region: NormRect,
  targetLongPx = OCR_TARGET_LONG_PX,
  maxEdge = 4096,
): Promise<HTMLCanvasElement> {
  const pdf = await pdfjs.getDocument({ data: fileData.slice(0) }).promise;
  try {
    const page = await pdf.getPage(pageNo);
    const base = page.getViewport({ scale: 1 });
    const regW = Math.max(1, region.w * base.width);
    const regH = Math.max(1, region.h * base.height);
    let scale = Math.max(1, targetLongPx / Math.max(regW, regH));
    if (Math.max(regW, regH) * scale > maxEdge) {
      scale = maxEdge / Math.max(regW, regH);
    }
    const cw = Math.max(1, Math.ceil(regW * scale));
    const ch = Math.max(1, Math.ceil(regH * scale));
    // Offset the viewport so the region's top-left maps to the canvas origin;
    // the canvas is region-sized, so only the region is rendered (clipped).
    const viewport = page.getViewport({
      scale,
      offsetX: -region.x * base.width * scale,
      offsetY: -region.y * base.height * scale,
    });
    const canvas = document.createElement("canvas");
    canvas.width = cw;
    canvas.height = ch;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("2d context unavailable");
    ctx.fillStyle = "#ffffff";
    ctx.fillRect(0, 0, cw, ch);
    await page.render({ canvas, canvasContext: ctx, viewport }).promise;
    return canvas;
  } finally {
    await pdf.destroy();
  }
}
