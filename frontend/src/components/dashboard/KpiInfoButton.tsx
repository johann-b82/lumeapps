import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Info } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { MarkdownRenderer } from "@/components/docs/MarkdownRenderer";
import { getKpiInfo, type KpiInfoKey } from "@/lib/kpiInfo";

interface KpiInfoButtonProps {
  /** Which KPI's calculation notes to show (see `lib/kpiInfo.ts`). */
  infoKey: KpiInfoKey;
  /** Display label of the KPI — used in the dialog title + aria-label. */
  label: string;
  className?: string;
}

/**
 * Small "i" button that sits next to a KPI label and opens a dialog with
 * the calculation notes (formula, data source, filters, edge cases) for that
 * KPI. Content is static and lives in `lib/kpiInfo.ts`; the long-form
 * reference is `docs/kpi-rechenwege.md`.
 */
export function KpiInfoButton({ infoKey, label, className }: KpiInfoButtonProps) {
  const { t, i18n } = useTranslation();
  const [open, setOpen] = useState(false);
  const info = getKpiInfo(infoKey, i18n.language);

  return (
    <>
      <Button
        type="button"
        variant="ghost"
        size="icon-xs"
        onClick={(e) => {
          e.stopPropagation();
          setOpen(true);
        }}
        aria-label={t("kpiInfo.button.aria", { kpi: label })}
        title={t("kpiInfo.button.title")}
        data-testid={`kpi-info-${infoKey}`}
        className={
          "text-muted-foreground hover:text-foreground " + (className ?? "")
        }
      >
        <Info aria-hidden />
      </Button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="sm:max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>
              {t("kpiInfo.dialog.title")}: {label}
            </DialogTitle>
            <DialogDescription>{t("kpiInfo.dialog.description")}</DialogDescription>
          </DialogHeader>
          <div className="text-sm [&_.prose]:text-sm [&_.prose_p]:my-2 [&_.prose_ul]:my-2 [&_.prose_ol]:my-2 [&_.prose_li]:my-0.5">
            <MarkdownRenderer content={info} />
          </div>
        </DialogContent>
      </Dialog>
    </>
  );
}
