/**
 * Floating value field shown after a region is marked. Pre-filled with the OCR
 * guess (auto-selected for instant retype) and editable. Two buttons re-check
 * the same region as a measurement (digits only) or as text. There is NO
 * confirm step: the next click on the drawing (to place the bubble) confirms
 * the value. Escape cancels.
 */
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Loader2, Ruler, Type } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

interface OcrCorrectionInputProps {
  screenX: number;
  screenY: number;
  value: string;
  busy: boolean;
  rechecking: boolean;
  onChange: (v: string) => void;
  onRecheck: (mode: "measure" | "text") => void;
  onCancel: () => void;
}

export function OcrCorrectionInput({
  screenX,
  screenY,
  value,
  busy,
  rechecking,
  onChange,
  onRecheck,
  onCancel,
}: OcrCorrectionInputProps) {
  const { t } = useTranslation();
  const ref = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (!busy && ref.current) {
      ref.current.focus();
      ref.current.select();
    }
  }, [busy]);

  const disabled = busy || rechecking;

  return (
    <div
      className="absolute z-20 flex flex-col gap-1 rounded-md border bg-popover p-1.5 shadow-lg"
      style={{ left: screenX, top: screenY, transform: "translate(-50%, 8px)" }}
      onPointerDown={(e) => e.stopPropagation()}
    >
      <div className="flex items-center gap-1">
        <Input
          ref={ref}
          value={value}
          disabled={busy}
          placeholder={busy ? t("fair.ocr.reading") : t("fair.ocr.value")}
          className="h-8 w-44"
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              e.currentTarget.blur();
            } else if (e.key === "Escape") {
              e.preventDefault();
              onCancel();
            }
          }}
        />
        {(busy || rechecking) && (
          <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
        )}
      </div>
      <div className="flex items-center gap-1">
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 flex-1"
          disabled={disabled}
          onClick={() => onRecheck("measure")}
          title={t("fair.ocr.recheckMeasure")}
        >
          <Ruler className="h-3.5 w-3.5" />
          <span className="ml-1">{t("fair.ocr.measure")}</span>
        </Button>
        <Button
          type="button"
          size="sm"
          variant="outline"
          className="h-7 flex-1"
          disabled={disabled}
          onClick={() => onRecheck("text")}
          title={t("fair.ocr.recheckText")}
        >
          <Type className="h-3.5 w-3.5" />
          <span className="ml-1">{t("fair.ocr.text")}</span>
        </Button>
      </div>
    </div>
  );
}
