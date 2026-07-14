/**
 * Export the drawing WITH its bubbles/arrows as a PDF at FULL original quality.
 *
 * PDF source: the original page is embedded as a VECTOR form XObject and placed
 * UPRIGHT onto a new page whose size equals the editor's rotation-aware viewport
 * (i.e. the frame the balloons were captured in). This makes the export line up
 * EXACTLY with the editor even when the source page carries a `/Rotate` — while
 * preserving vector quality (no re-rasterisation / downscaling).
 * Image source: the original bytes are embedded at native resolution.
 *
 * The bubbles/arrows/numbers are drawn as crisp vectors on top; the user's view
 * rotation is applied to the whole page and the numbers are counter-rotated so
 * they stay upright.
 */
import { PDFDocument, StandardFonts, degrees, rgb } from "pdf-lib";
import type { PDFEmbeddedPage, PDFFont, PDFPage } from "pdf-lib";
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
 * Place an embedded source page (unrotated content, W0×H0) UPRIGHT onto the
 * target page, undoing the source `/Rotate` (clockwise). The target page is
 * sized to the rotation-aware dims, so the result matches pdf.js/the editor.
 */
function drawUpright(
  page: PDFPage,
  embedded: PDFEmbeddedPage,
  rot: number,
  W0: number,
  H0: number,
): void {
  switch (rot) {
    case 90:
      page.drawPage(embedded, { x: 0, y: W0, rotate: degrees(-90) });
      break;
    case 180:
      page.drawPage(embedded, { x: W0, y: H0, rotate: degrees(180) });
      break;
    case 270:
      page.drawPage(embedded, { x: H0, y: 0, rotate: degrees(90) });
      break;
    default:
      page.drawPage(embedded, { x: 0, y: 0 });
  }
}

/**
 * Draw one page's balloons in the (upright) page's content space. Geometry from
 * `balloonPixels` is canvas (y-down); pdf-lib is y-up, so y is flipped. The
 * number is centred on the bubble and counter-rotated by `rotation` so it stays
 * upright after the page is rotated.
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
  const out = await PDFDocument.create();
  const font = await out.embedFont(StandardFonts.HelveticaBold);

  if (opts.kind === "image") {
    // Embed the ORIGINAL image bytes at native resolution — no downscale/re-encode.
    const bytes = new Uint8Array(await (await fetch(opts.imageUrl)).arrayBuffer());
    const isPng = bytes[0] === 0x89 && bytes[1] === 0x50;
    const image = isPng ? await out.embedPng(bytes) : await out.embedJpg(bytes);
    const page = out.addPage([image.width, image.height]);
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
    const src = await PDFDocument.load(opts.pdfData, { ignoreEncryption: true });
    const srcPages = src.getPages();
    for (let i = 0; i < srcPages.length; i++) {
      const sp = srcPages[i];
      const rot = (((sp.getRotation().angle % 360) + 360) % 360);
      const embedded = await out.embedPage(sp);
      const W0 = embedded.width;
      const H0 = embedded.height;
      const swap = rot === 90 || rot === 270;
      const vw = swap ? H0 : W0;
      const vh = swap ? W0 : H0;
      const page = out.addPage([vw, vh]);
      drawUpright(page, embedded, rot, W0, H0);
      drawBalloons(
        page,
        font,
        opts.balloonsByPage.get(i + 1) ?? [],
        vw,
        vh,
        opts.sizeScale,
        opts.rotation,
      );
      if (opts.rotation) page.setRotation(degrees(opts.rotation));
    }
  }

  download(await out.save({ useObjectStreams: true }), opts.fileName);
}
