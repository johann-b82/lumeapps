/**
 * Renders the drawing at its NATURAL size (once) — a PDF page via react-pdf or
 * an <img>. Zoom/pan is applied by the parent's CSS transform, so `<Page width>`
 * stays stable and the PDF canvas never re-rasterises on zoom. Reports the
 * natural page size and (for PDFs) the page count up to the editor.
 */
import { memo } from "react";
import { Document, Page } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";
import type { FairFileKind } from "@/lib/fairApi";

interface DrawingSurfaceProps {
  url: string;
  kind: FairFileKind;
  pageNo: number;
  naturalW: number | null;
  naturalH: number | null;
  /** Backing-store oversampling for the PDF canvas — raised with zoom so
   *  dimension text stays sharp instead of upscaling a 72-DPI raster. */
  renderDpr: number;
  onNatural: (size: { w: number; h: number }) => void;
  onNumPages: (n: number) => void;
}

function DrawingSurfaceImpl({
  url,
  kind,
  pageNo,
  naturalW,
  naturalH,
  renderDpr,
  onNatural,
  onNumPages,
}: DrawingSurfaceProps) {
  if (kind === "image") {
    return (
      <img
        src={url}
        alt="Zeichnung"
        draggable={false}
        style={{
          display: "block",
          width: naturalW ? `${naturalW}px` : "auto",
          height: naturalH ? `${naturalH}px` : "auto",
          userSelect: "none",
          pointerEvents: "none",
        }}
        onLoad={(e) => {
          const img = e.currentTarget;
          onNumPages(1);
          if (!naturalW) {
            onNatural({ w: img.naturalWidth, h: img.naturalHeight });
          }
        }}
      />
    );
  }

  return (
    <Document
      file={url}
      onLoadSuccess={({ numPages }) => onNumPages(numPages)}
      loading=""
      error="PDF konnte nicht geladen werden."
    >
      <Page
        pageNumber={pageNo}
        width={naturalW ?? undefined}
        devicePixelRatio={renderDpr}
        renderTextLayer={false}
        renderAnnotationLayer={false}
        onLoadSuccess={(p) => {
          const vp = p.getViewport({ scale: 1 });
          onNatural({ w: vp.width, h: vp.height });
        }}
      />
    </Document>
  );
}

export const DrawingSurface = memo(DrawingSurfaceImpl);
