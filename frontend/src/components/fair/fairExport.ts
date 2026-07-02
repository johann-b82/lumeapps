/**
 * Export the drawing WITH its bubbles/arrows as a PDF at FULL original quality.
 *
 * The source PDF pages are copied verbatim (vector, original resolution) and the
 * source image is embedded at its native pixels — the drawing is never
 * re-rasterised or downscaled. The bubbles/arrows/numbers are drawn as crisp
 * VECTORS on top. The whole page is rotated to match the current view; the
 * numbers are counter-rotated so they stay upright.
 *
 * NOTE: file size/performance follows the ORIGINAL file — a heavy source PDF
 * yields a heavy export. This is intentional: drawing quality must not be
 * reduced. (Object streams give lossless structural compression only.)
 */
import { PDFDocument, StandardFonts, degrees, rgb } from "pdf-lib";
import type { PDFFont, PDFPage } from "pdf-lib";
import { balloonPixels } from "./geometry";
import type { Rotation } from "./geometry";
import type { FairBalloon } from "@/lib/fairApi";

const RED = rgb(0.862, 0.149, 0.149); // #dc2626
const WHITE = rgb(1, 1, 1);
const REGION_OPACITY = 0.45;

function download(bytes: Uint8Array, fileName: string): void {
  const ab = bytes.buffer.slice(
    bytes.byteOffset,
    bytes.byteOffset + bytes.byteLength,
  ) as ArrayBuffer;
  const blob = new Blob([ab], { type: "application/pdf" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = fileName;
  a.click();
  URL.revokeObjectURL(url);
}

/**
 * Draw one page's balloons in the page's content space. Geometry comes from
 * `balloonPixels` in canvas (y-down) coords; pdf-lib is y-up, so y is flipped.
 * `drawSvgPath` anchored at (0, pageH) performs the same flip for path shapes.
 * The number is centred on the bubble and counter-rotated by `rotation` so it
 * stays upright after the page is rotated.
 */
function drawBalloons(
  page: PDFPage,
  font: PDFFont,
  balloons: readonly FairBalloon[],
  pageW: number,
  pageH: number,
  sizeScale: number,
  rotation: Rotation,
): void {
  const flipY = (y: number) => pageH - y;
  for (const b of balloons) {
    const g = balloonPixels(b, pageW, pageH, sizeScale);
    const sw = Math.max(1, g.r * 0.14);

    const rx = g.region.x;
    const ry = g.region.y;
    const rw = g.region.w;
    const rh = g.region.h;
    page.drawSvgPath(
      `M ${rx} ${ry} L ${rx + rw} ${ry} L ${rx + rw} ${ry + rh} L ${rx} ${ry + rh} Z`,
      { x: 0, y: pageH, borderColor: RED, borderWidth: sw, borderOpacity: REGION_OPACITY },
    );

    const p = g.arrowPoints.split(" ").map((pt) => pt.split(",").map(Number));
    page.drawSvgPath(
      `M ${p[0][0]} ${p[0][1]} L ${p[1][0]} ${p[1][1]} L ${p[2][0]} ${p[2][1]} Z`,
      { x: 0, y: pageH, color: RED },
    );

    page.drawCircle({
      x: g.tail.x,
      y: flipY(g.tail.y),
      size: g.r,
      color: WHITE,
      borderColor: RED,
      borderWidth: sw,
    });

    const str = String(b.number);
    const tw = font.widthOfTextAtSize(str, g.fontSize);
    const bo = g.fontSize * 0.35;
    const cx = g.tail.x;
    const cy = flipY(g.tail.y);
    const phi = (rotation * Math.PI) / 180;
    const cos = Math.cos(phi);
    const sin = Math.sin(phi);
    page.drawText(str, {
      x: cx - (tw / 2) * cos + bo * sin,
      y: cy - (tw / 2) * sin - bo * cos,
      size: g.fontSize,
      font,
      color: RED,
      rotate: degrees(rotation),
    });
  }
}

export interface ExportImageOpts {
  kind: "image";
  fileName: string;
  imageUrl: string;
  rotation: Rotation;
  sizeScale: number;
  balloons: readonly FairBalloon[];
}

export interface ExportPdfOpts {
  kind: "pdf";
  fileName: string;
  pdfData: ArrayBuffer;
  rotation: Rotation;
  sizeScale: number;
  balloonsByPage: Map<number, FairBalloon[]>;
}

export async function exportFairPdf(
  opts: ExportImageOpts | ExportPdfOpts,
): Promise<void> {
  let doc: PDFDocument;

  if (opts.kind === "image") {
    // Embed the ORIGINAL image bytes at native resolution — no downscale/re-encode.
    const bytes = new Uint8Array(await (await fetch(opts.imageUrl)).arrayBuffer());
    doc = await PDFDocument.create();
    const font = await doc.embedFont(StandardFonts.HelveticaBold);
    const isPng = bytes[0] === 0x89 && bytes[1] === 0x50;
    const image = isPng ? await doc.embedPng(bytes) : await doc.embedJpg(bytes);
    const page = doc.addPage([image.width, image.height]);
    page.drawImage(image, { x: 0, y: 0, width: image.width, height: image.height });
    drawBalloons(
      page,
      font,
      opts.balloons,
      image.width,
      image.height,
      opts.sizeScale,
      opts.rotation,
    );
    if (opts.rotation) page.setRotation(degrees(opts.rotation));
  } else {
    // Copy the ORIGINAL PDF pages verbatim (vector, full quality); overlay only.
    doc = await PDFDocument.load(opts.pdfData, { ignoreEncryption: true });
    const font = await doc.embedFont(StandardFonts.HelveticaBold);
    doc.getPages().forEach((page, i) => {
      const { width, height } = page.getSize();
      drawBalloons(
        page,
        font,
        opts.balloonsByPage.get(i + 1) ?? [],
        width,
        height,
        opts.sizeScale,
        opts.rotation,
      );
      if (opts.rotation) {
        const current = page.getRotation().angle;
        page.setRotation(degrees((current + opts.rotation) % 360));
      }
    });
  }

  download(await doc.save({ useObjectStreams: true }), opts.fileName);
}
