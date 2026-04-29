import { useDropzone, type FileRejection } from "react-dropzone";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Loader2, Upload } from "lucide-react";
import { uploadLogo, type Settings } from "@/lib/api";

interface LogoUploadProps {
  /** Current logo URL from the settings cache — null when no logo set. */
  logoUrl: string | null;
}

const MAX_BYTES = 1_048_576;  // 1 MB exactly — matches backend BRAND-01

/**
 * Dropzone + current-logo thumbnail combo.
 *
 * - If `logoUrl` is non-null, renders the thumbnail (120x120, object-contain)
 *   on the left and labels the dropzone "Replace logo".
 * - If null, renders only the dropzone with "Upload logo" labeling.
 *
 * On valid drop, immediately POSTs via uploadLogo() (D-14). On success,
 * writes the response to the ['settings'] cache so ThemeProvider +
 * NavBar pick up the new logo_url without a refetch. On failure,
 * fires toast.error with the server's detail message.
 *
 * Client-side rejections (>1MB, wrong MIME) fire localized toasts
 * before any network call (D-16). No inline error state on the dropzone
 * itself — errors are toast-only (D-16).
 */
export function LogoUpload({ logoUrl }: LogoUploadProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: uploadLogo,
    onSuccess: (response: Settings) => {
      // Update the cache directly so NavBar + ThemeProvider re-render
      // with the new logo_url + logo_updated_at — avoids a round-trip.
      queryClient.setQueryData<Settings>(["settings"], response);
      toast.success(t("settings.toasts.logo_updated"));
    },
    onError: (err: Error) => {
      toast.error(
        t("settings.toasts.logo_error", { detail: err.message }),
      );
    },
  });

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    accept: {
      "image/png": [".png"],
      "image/svg+xml": [".svg"],
    },
    maxSize: MAX_BYTES,
    maxFiles: 1,
    multiple: false,
    disabled: mutation.isPending,
    onDrop: (acceptedFiles: File[], fileRejections: FileRejection[]) => {
      if (fileRejections.length > 0) {
        const rejection = fileRejections[0];
        const code = rejection.errors[0]?.code;
        if (code === "file-too-large") {
          toast.error(t("settings.toasts.logo_too_large"));
        } else if (code === "file-invalid-type") {
          toast.error(t("settings.toasts.logo_wrong_type"));
        } else {
          // Catch-all for other react-dropzone rejection codes
          toast.error(t("settings.toasts.logo_wrong_type"));
        }
        return;
      }
      if (acceptedFiles.length > 0) {
        mutation.mutate(acceptedFiles[0]);
      }
    },
  });

  const dropzoneLabel = logoUrl
    ? t("settings.identity.logo.dropzone_replace")
    : t("settings.identity.logo.dropzone_empty");

  return (
    <div className="grid grid-cols-1 sm:grid-cols-4 items-stretch gap-4">
      {logoUrl && (
        <div className="sm:col-span-1 flex items-stretch">
          <img
            src={logoUrl}
            alt="Current logo"
            className="w-full aspect-square object-contain rounded-md border border-border bg-background"
          />
        </div>
      )}
      <div
        {...getRootProps({
          className: [
            (logoUrl ? "sm:col-span-3" : "sm:col-span-4") + " min-h-[120px] rounded-md border-2 border-dashed flex items-center justify-center p-6 transition-colors cursor-pointer",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary",
            isDragActive
              ? "bg-primary/5 border-primary"
              : "bg-muted/30 border-border hover:bg-muted/50",
            mutation.isPending ? "cursor-not-allowed opacity-60" : "",
          ].join(" "),
          "aria-label": t("settings.actions.logo_dropzone_aria"),
          role: "button",
          tabIndex: 0,
        })}
      >
        {/* CTRL-02 exception: native file picker — primitive <Input> does not wrap file-type inputs (browser-native styling retained). */}
        <input {...getInputProps()} />
        {mutation.isPending ? (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            <span>Uploading…</span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2 text-center">
            <Upload className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm text-foreground">{dropzoneLabel}</p>
            <p className="text-xs text-muted-foreground">
              {t("settings.identity.logo.help")}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
