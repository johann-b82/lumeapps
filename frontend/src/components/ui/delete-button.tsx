import { useState, type ReactNode } from "react";
import { Trans, useTranslation } from "react-i18next";
import { Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { DeleteDialog } from "@/components/ui/delete-dialog";

/**
 * Re-export of lucide `Trash2` for the rare non-row raw-glyph case where
 * the composed `<DeleteButton>` is not appropriate (e.g. inline help text).
 * Prefer `<DeleteButton>` for any actionable delete control.
 */
export const TrashIcon = Trash2;

export interface DeleteButtonProps {
  /** Item identifier interpolated into the default fallback body. */
  itemLabel: string;
  /** Awaited on Confirm; dialog closes after settle (success or error). */
  onConfirm: () => void | Promise<void>;
  /** Override dialog title. Defaults to `t("ui.delete.title")`. */
  dialogTitle?: string;
  /**
   * Override dialog body. Defaults to a `<Trans>` over `ui.delete.bodyFallback`
   * with `<1>{{itemLabel}}</1>` interpolation for emphasis.
   */
  dialogBody?: ReactNode;
  cancelLabel?: string;
  confirmLabel?: string;
  /** Required — Phase 59 accessible-name audit relies on explicit labels. */
  "aria-label": string;
  disabled?: boolean;
}

export function DeleteButton({
  itemLabel,
  onConfirm,
  dialogTitle,
  dialogBody,
  cancelLabel,
  confirmLabel,
  "aria-label": ariaLabel,
  disabled,
}: DeleteButtonProps) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const { t } = useTranslation();

  const body =
    dialogBody ?? (
      <Trans
        i18nKey="ui.delete.bodyFallback"
        values={{ itemLabel }}
        components={{ 1: <strong className="text-foreground font-medium" /> }}
      />
    );

  const handleConfirm = async () => {
    setBusy(true);
    try {
      await onConfirm();
    } catch {
      // Caller is expected to surface its own error UI (toast, inline);
      // we swallow here so the dialog still closes cleanly and no unhandled
      // rejection escapes into the React event-handler boundary.
    } finally {
      setBusy(false);
      setOpen(false);
    }
  };

  return (
    <>
      <Button
        type="button"
        variant="destructive"
        size="icon"
        aria-label={ariaLabel}
        disabled={disabled}
        onClick={() => setOpen(true)}
      >
        <Trash2 aria-hidden="true" />
      </Button>
      <DeleteDialog
        open={open}
        onOpenChange={setOpen}
        title={dialogTitle ?? t("ui.delete.title")}
        body={body}
        cancelLabel={cancelLabel}
        confirmLabel={confirmLabel}
        onConfirm={handleConfirm}
        confirmDisabled={busy}
      />
    </>
  );
}
