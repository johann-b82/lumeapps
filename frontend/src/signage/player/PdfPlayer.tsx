import { useEffect, useState, useRef } from "react";
import { Document, Page } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

// SGN-DIFF-03: PDF crossfade between consecutive pages.
// Two-layer overlap with `transition-opacity duration-200`. Default 200ms per ROADMAP success criterion 3.
// Admin-configurable per-playlist piece is OUT OF SCOPE per CONTEXT (no admin UI changes); fixed default.
//
// Phase 47 note: the pdf.js worker pin lives in `frontend/src/player/lib/pdfWorker.ts`
// (Plan 47-01) and is imported by `main.tsx`. Do NOT configure the worker here.
export interface PdfPlayerProps {
  uri: string | null;
  autoFlipSeconds?: number;
  /** Crossfade duration in ms between consecutive pages (SGN-DIFF-03). */
  crossfadeMs?: number;
}

export function PdfPlayer({
  uri,
  autoFlipSeconds = 8,
  crossfadeMs = 200,
}: PdfPlayerProps) {
  const [numPages, setNumPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [nextPage, setNextPage] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState<number | undefined>(undefined);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) setContainerWidth(entry.contentRect.width);
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Auto-flip timer: every `autoFlipSeconds`, start a crossfade to the next page.
  // The timer reads `currentPage` from the effect closure, so we re-subscribe on
  // every page change — each tick schedules exactly one crossfade and unmounts.
  useEffect(() => {
    if (numPages <= 1) return;
    if (nextPage !== null) return; // crossfade in flight — wait for it to commit
    const intervalMs = Math.max(1000, autoFlipSeconds * 1000);
    const id = window.setTimeout(() => {
      const target = currentPage >= numPages ? 1 : currentPage + 1;
      setNextPage(target);
      window.setTimeout(() => {
        setCurrentPage(target);
        setNextPage(null);
      }, crossfadeMs);
    }, intervalMs);
    return () => window.clearTimeout(id);
  }, [numPages, autoFlipSeconds, crossfadeMs, currentPage, nextPage]);

  // Reset page when uri changes.
  useEffect(() => {
    setCurrentPage(1);
    setNextPage(null);
  }, [uri]);

  if (!uri) return null;
  return (
    <div
      ref={containerRef}
      className="relative w-full h-full flex items-center justify-center"
    >
      <Document file={uri} onLoadSuccess={({ numPages: n }) => setNumPages(n)}>
        {/* Layer A: current page — fades out as nextPage mounts on top. */}
        <div
          className="absolute inset-0 flex items-center justify-center transition-opacity duration-200"
          style={{ opacity: nextPage === null ? 1 : 0 }}
        >
          <Page
            pageNumber={currentPage}
            width={containerWidth}
            renderTextLayer={false}
            renderAnnotationLayer={false}
          />
        </div>
        {/* Layer B: next page, only mounted during the crossfade window. */}
        {nextPage !== null && (
          <div
            className="absolute inset-0 flex items-center justify-center transition-opacity duration-200"
            style={{ opacity: 1 }}
          >
            <Page
              pageNumber={nextPage}
              width={containerWidth}
              renderTextLayer={false}
              renderAnnotationLayer={false}
            />
          </div>
        )}
      </Document>
    </div>
  );
}
