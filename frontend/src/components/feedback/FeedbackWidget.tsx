import { useCallback, useState } from "react";
import { useTranslation } from "react-i18next";
import { MessageSquarePlus, Loader2 } from "lucide-react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { useAuth } from "@/auth/useAuth";
import { submitFeedback } from "@/lib/api";

/** Convert a data-URL (from html-to-image) into a Blob for multipart upload. */
function dataUrlToBlob(dataUrl: string): Blob {
  const [head, b64] = dataUrl.split(",");
  const mime = /:(.*?);/.exec(head)?.[1] ?? "image/jpeg";
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Blob([bytes], { type: mime });
}

/**
 * Global feedback widget — a floating button present on every authenticated
 * page (mounted once in AppShell). Clicking captures a screenshot of the
 * current page (client-side DOM render via html-to-image) and opens a dialog
 * with the preview + a free-text field. Submitting POSTs to /api/feedback.
 *
 * The widget's own DOM is tagged `data-feedback-ui` so html-to-image filters
 * it out of the capture.
 */
export function FeedbackWidget() {
  const { t } = useTranslation();
  const { user } = useAuth();

  const [open, setOpen] = useState(false);
  const [capturing, setCapturing] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [description, setDescription] = useState("");
  const [screenshot, setScreenshot] = useState<string | null>(null);
  const [captureFailed, setCaptureFailed] = useState(false);

  const handleOpen = useCallback(async () => {
    setCapturing(true);
    setCaptureFailed(false);
    setScreenshot(null);
    try {
      // Dynamic import so a missing/unbuilt html-to-image never breaks the
      // app at load time — capture just falls back to text-only if it fails.
      const { toJpeg } = await import("html-to-image");
      const bg =
        getComputedStyle(document.body).backgroundColor || "#ffffff";
      const dataUrl = await toJpeg(document.body, {
        quality: 0.85,
        pixelRatio: 1,
        cacheBust: true,
        backgroundColor: bg,
        // Skip the widget's own DOM (button + this dialog trigger).
        filter: (node) =>
          !(
            node instanceof HTMLElement && node.dataset.feedbackUi === "true"
          ),
      });
      setScreenshot(dataUrl);
    } catch {
      // Screenshot is best-effort — allow a text-only report.
      setCaptureFailed(true);
    } finally {
      setCapturing(false);
      setOpen(true);
    }
  }, []);

  const reset = useCallback(() => {
    setOpen(false);
    setDescription("");
    setScreenshot(null);
    setCaptureFailed(false);
  }, []);

  const handleSubmit = useCallback(async () => {
    const text = description.trim();
    if (!text) return;
    setSubmitting(true);
    try {
      await submitFeedback({
        description: text,
        pageUrl: window.location.pathname + window.location.search,
        userAgent: navigator.userAgent,
        viewport: `${window.innerWidth}x${window.innerHeight}`,
        reporterEmail: user?.email,
        screenshot: screenshot ? dataUrlToBlob(screenshot) : null,
      });
      toast.success(t("feedback.toast.success"));
      reset();
    } catch (err) {
      toast.error((err as Error).message || t("feedback.toast.error"));
    } finally {
      setSubmitting(false);
    }
  }, [description, screenshot, user?.email, reset, t]);

  return (
    <div data-feedback-ui="true">
      <Button
        type="button"
        onClick={handleOpen}
        disabled={capturing}
        aria-label={t("feedback.button.aria")}
        className="fixed bottom-5 right-5 z-40 gap-2 shadow-lg"
      >
        {capturing ? (
          <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
        ) : (
          <MessageSquarePlus className="h-4 w-4" aria-hidden />
        )}
        <span className="hidden sm:inline">{t("feedback.button.label")}</span>
      </Button>

      <Dialog open={open} onOpenChange={(o) => (o ? setOpen(true) : reset())}>
        <DialogContent className="sm:max-w-lg" data-feedback-ui="true">
          <DialogHeader>
            <DialogTitle>{t("feedback.dialog.title")}</DialogTitle>
            <DialogDescription>
              {t("feedback.dialog.description")}
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-3">
            <Textarea
              autoFocus
              rows={4}
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder={t("feedback.dialog.placeholder")}
            />

            {screenshot && (
              <div className="overflow-hidden rounded-md border border-border">
                <img
                  src={screenshot}
                  alt={t("feedback.dialog.screenshotAlt")}
                  className="max-h-48 w-full object-contain bg-muted"
                />
              </div>
            )}
            {captureFailed && (
              <p className="text-xs text-muted-foreground">
                {t("feedback.dialog.screenshotFailed")}
              </p>
            )}
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={reset} disabled={submitting}>
              {t("feedback.dialog.cancel")}
            </Button>
            <Button
              onClick={handleSubmit}
              disabled={submitting || description.trim() === ""}
            >
              {submitting && (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
              )}
              {t("feedback.dialog.submit")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
