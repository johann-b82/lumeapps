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
  /** Optional. Fired after the last page has been shown for `autoFlipSeconds`.
   *  When provided, PdfPlayer stops flipping rather than wrapping back to page 1
   *  — the parent decides what comes next (e.g. advance to the next playlist
   *  item). Without it, the player loops back to page 1. */
  onCycleEnd?: () => void;
}

export function PdfPlayer({
  uri,
  autoFlipSeconds = 8,
  crossfadeMs = 200,
  onCycleEnd,
}: PdfPlayerProps) {
  const [numPages, setNumPages] = useState(0);
  const [currentPage, setCurrentPage] = useState(1);
  const [nextPage, setNextPage] = useState<number | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerSize, setContainerSize] = useState<{ w: number; h: number } | null>(null);
  // Native page dimensions (CSS pixels at scale=1). Set on the FIRST page load
  // success — we assume a uniform page geometry across the deck, which holds
  // for the vast majority of PDFs and avoids reflow flicker per page.
  const [pageNatural, setPageNatural] = useState<{ w: number; h: number } | null>(null);
  // Latest onCycleEnd in a ref so the flip effect doesn't re-subscribe (which
  // would reset the timer) when the callback identity changes between renders.
  const onCycleEndRef = useRef(onCycleEnd);
  useEffect(() => {
    onCycleEndRef.current = onCycleEnd;
  }, [onCycleEnd]);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerSize({
          w: entry.contentRect.width,
          h: entry.contentRect.height,
        });
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Fit-to-contain via width OR height prop (not both, not scale): react-pdf
  // computes the right scale from whichever dimension binds. This is more
  // robust than supplying scale ourselves — earlier attempts using
  // `scale={min(w/pw, h/ph)}` still let the canvas overflow on the Pi.
  // - container is wider than the page (relative): height is binding
  // - container is narrower than the page: width is binding
  // - before pageNatural is known, fall back to container width
  const fitProps: { width?: number; height?: number } = (() => {
    if (!containerSize) return {};
    if (!pageNatural) return { width: containerSize.w };
    const containerAspect = containerSize.w / containerSize.h;
    const pageAspect = pageNatural.w / pageNatural.h;
    return pageAspect >= containerAspect
      ? { width: containerSize.w }
      : { height: containerSize.h };
  })();

  // Auto-flip timer: every `autoFlipSeconds`, start a crossfade to the next page.
  // The timer reads `currentPage` from the effect closure, so we re-subscribe on
  // every page change — each tick schedules exactly one crossfade and unmounts.
  useEffect(() => {
    if (numPages === 0) return;
    if (nextPage !== null) return; // crossfade in flight — wait for it to commit
    const intervalMs = Math.max(1000, autoFlipSeconds * 1000);
    const id = window.setTimeout(() => {
      const isLastPage = currentPage >= numPages;
      if (isLastPage) {
        // End of cycle: hand off to parent if it asked, else wrap.
        if (onCycleEndRef.current) {
          onCycleEndRef.current();
          return;
        }
        if (numPages <= 1) return; // single-page PDF with no parent: just hold
      }
      const target = isLastPage ? 1 : currentPage + 1;
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
          className="absolute inset-0 overflow-hidden flex items-center justify-center transition-opacity duration-200"
          style={{ opacity: nextPage === null ? 1 : 0 }}
        >
          <Page
            pageNumber={currentPage}
            {...fitProps}
            renderTextLayer={false}
            renderAnnotationLayer={false}
            onLoadSuccess={(p) => {
              if (!pageNatural) {
                // Use the public pdfjs API to get native page size instead of
                // relying on react-pdf's added `originalWidth/Height` props,
                // which have moved across react-pdf versions.
                const vp = p.getViewport({ scale: 1 });
                setPageNatural({ w: vp.width, h: vp.height });
              }
            }}
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
              {...fitProps}
              renderTextLayer={false}
              renderAnnotationLayer={false}
            />
          </div>
        )}
      </Document>
    </div>
  );
}
