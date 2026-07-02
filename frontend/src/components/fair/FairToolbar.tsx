/** FAIR editor toolbar: tool mode, zoom, page navigation, PDF export. */
import { useTranslation } from "react-i18next";
import {
  ChevronLeft,
  ChevronRight,
  CircleDot,
  Crosshair,
  Download,
  Hand,
  Loader2,
  Maximize,
  Minus,
  Plus,
  RotateCw,
} from "lucide-react";
import { Button } from "@/components/ui/button";

export type FairTool = "pan" | "add";

interface FairToolbarProps {
  tool: FairTool;
  onToolChange: (t: FairTool) => void;
  onZoomIn: () => void;
  onZoomOut: () => void;
  onFit: () => void;
  onRotate: () => void;
  onBubbleSmaller: () => void;
  onBubbleLarger: () => void;
  page: number;
  pageCount: number;
  onPage: (p: number) => void;
  onExport: () => void;
  exporting: boolean;
  ocrReady: boolean;
}

export function FairToolbar({
  tool,
  onToolChange,
  onZoomIn,
  onZoomOut,
  onFit,
  onRotate,
  onBubbleSmaller,
  onBubbleLarger,
  page,
  pageCount,
  onPage,
  onExport,
  exporting,
  ocrReady,
}: FairToolbarProps) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-md border bg-card p-2">
      <div className="flex items-center gap-1">
        <Button
          type="button"
          size="sm"
          variant={tool === "pan" ? "default" : "outline"}
          onClick={() => onToolChange("pan")}
          title={t("fair.tool.pan")}
        >
          <Hand className="h-4 w-4" />
        </Button>
        <Button
          type="button"
          size="sm"
          variant={tool === "add" ? "default" : "outline"}
          onClick={() => onToolChange("add")}
          title={t("fair.tool.add")}
        >
          <Crosshair className="h-4 w-4" />
          <span className="ml-1 hidden sm:inline">{t("fair.tool.add")}</span>
        </Button>
      </div>

      <div className="mx-1 h-6 w-px bg-border" />

      <div className="flex items-center gap-1">
        <Button type="button" size="sm" variant="outline" onClick={onZoomOut} title={t("fair.zoom.out")}>
          <Minus className="h-4 w-4" />
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onZoomIn} title={t("fair.zoom.in")}>
          <Plus className="h-4 w-4" />
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onFit} title={t("fair.zoom.fit")}>
          <Maximize className="h-4 w-4" />
        </Button>
        <Button type="button" size="sm" variant="outline" onClick={onRotate} title={t("fair.rotate")}>
          <RotateCw className="h-4 w-4" />
        </Button>
      </div>

      <div className="mx-1 h-6 w-px bg-border" />

      {/* Global bubble size (all balloons + numbers). */}
      <div className="flex items-center gap-1">
        <CircleDot className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onBubbleSmaller}
          title={t("fair.bubble.smaller")}
        >
          <Minus className="h-4 w-4" />
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          onClick={onBubbleLarger}
          title={t("fair.bubble.larger")}
        >
          <Plus className="h-4 w-4" />
        </Button>
      </div>

      {pageCount > 1 && (
        <>
          <div className="mx-1 h-6 w-px bg-border" />
          <div className="flex items-center gap-1">
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => onPage(page - 1)}
              disabled={page <= 1}
            >
              <ChevronLeft className="h-4 w-4" />
            </Button>
            <span className="min-w-[3.5rem] text-center text-sm tabular-nums">
              {page} / {pageCount}
            </span>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={() => onPage(page + 1)}
              disabled={page >= pageCount}
            >
              <ChevronRight className="h-4 w-4" />
            </Button>
          </div>
        </>
      )}

      <div className="ml-auto flex items-center gap-2">
        {!ocrReady && (
          <span className="text-xs text-muted-foreground">{t("fair.ocr.loading")}</span>
        )}
        <Button type="button" size="sm" onClick={onExport} disabled={exporting}>
          {exporting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Download className="h-4 w-4" />
          )}
          <span className="ml-1">{t("fair.export.pdf")}</span>
        </Button>
      </div>
    </div>
  );
}
