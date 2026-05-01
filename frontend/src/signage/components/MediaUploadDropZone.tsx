import { useMemo, useState } from "react";
import { useDropzone } from "react-dropzone";
import type { FileRejection } from "react-dropzone";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";
import { uploadFiles } from "@directus/sdk";

import { directus } from "@/lib/directusClient";
import { apiClient } from "@/lib/apiClient";
import { signageApi } from "@/signage/lib/signageApi";
import { signageKeys } from "@/lib/queryKeys";
import { Button } from "@/components/ui/button";
import type {
  SignageMedia,
  SignageMediaKind,
} from "@/signage/lib/signageTypes";

/**
 * MediaUploadDropZone — admin-only dropzone for the Media tab.
 *
 * Routing rules (D-04 in 46-CONTEXT):
 *   - .pptx → multipart POST to /api/signage/media/pptx (backend converts).
 *   - All other accepted kinds → upload to Directus first via the SDK
 *     (`uploadFiles`), then signageApi.createMedia({ directus_file_id }) which
 *     inserts the row directly into the Directus `signage_media` collection
 *     (v1.23 C-4 — non-PPTX FastAPI handler removed).
 *
 * Pitfall 8 (46-RESEARCH): the Directus SDK's `uploadFiles` may return either
 * an array (one entry per file) or a single object — normalize both shapes
 * with `Array.isArray(res) ? res[0].id : res.id` before reading the id.
 *
 * No theme variants and no direct fetch — apiClient + directus SDK only.
 */

function inferKind(file: File): SignageMediaKind {
  const name = file.name.toLowerCase();
  const type = (file.type ?? "").toLowerCase();
  if (name.endsWith(".pptx")) return "pptx";
  if (type.startsWith("image/")) return "image";
  if (type.startsWith("video/")) return "video";
  if (type === "application/pdf" || name.endsWith(".pdf")) return "pdf";
  throw new Error(`unsupported file type: ${file.name}`);
}

interface DirectusUploadResult {
  id: string;
}

function normalizeDirectusUploadId(res: unknown): string {
  if (Array.isArray(res)) {
    const first = res[0] as DirectusUploadResult | undefined;
    if (!first?.id) throw new Error("directus upload returned no id");
    return first.id;
  }
  const single = res as DirectusUploadResult | null;
  if (!single?.id) throw new Error("directus upload returned no id");
  return single.id;
}

export function MediaUploadDropZone() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [rejectedExt, setRejectedExt] = useState<string | null>(null);

  const uploadMutation = useMutation<SignageMedia, Error, File>({
    mutationFn: async (file) => {
      const kind = inferKind(file);

      // PPTX path — multipart straight to backend so it can spool the bytes
      // into Directus and start conversion in a BackgroundTask.
      if (kind === "pptx") {
        const formData = new FormData();
        formData.append("file", file);
        formData.append("title", file.name);
        return await apiClient<SignageMedia>("/api/signage/media/pptx", {
          method: "POST",
          body: formData,
        });
      }

      // Non-PPTX path — Directus SDK upload first, then Directus row insert
      // via signageApi.createMedia (v1.23 C-4).
      const formData = new FormData();
      formData.append("file", file);
      formData.append("title", file.name);
      const uploadRes = await directus.request(uploadFiles(formData));
      const fileId = normalizeDirectusUploadId(uploadRes);

      return await signageApi.createMedia({
        kind: kind as "image" | "video" | "pdf",
        title: file.name,
        directus_file_id: fileId,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: signageKeys.media() });
      toast.success(t("signage.admin.media.upload_title"));
    },
    onError: (err) => {
      toast.error(
        t("signage.admin.error.generic", { detail: err.message }),
      );
    },
  });

  const accept = useMemo(
    () => ({
      "image/*": [],
      "video/*": [],
      "application/pdf": [".pdf"],
      "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        [".pptx"],
    }),
    [],
  );

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    accept,
    multiple: false,
    noClick: true,
    noKeyboard: true,
    disabled: uploadMutation.isPending,
    onDrop: (accepted: File[], rejections: FileRejection[]) => {
      setRejectedExt(null);
      if (rejections.length > 0) {
        const name = rejections[0].file.name;
        setRejectedExt(name.split(".").pop() ?? name);
        return;
      }
      if (accepted.length > 0) {
        uploadMutation.mutate(accepted[0]);
      }
    },
  });

  // v1.40: drop the bg-muted fill so the drop zone reads as a clean
  // dashed-bordered region inside the surrounding Card (same chrome
  // weight as a settings-form section).
  let containerClass =
    "rounded-md border-2 border-dashed min-h-[120px] flex flex-col items-center justify-center text-center p-6 transition-colors";
  if (uploadMutation.isPending) {
    containerClass += " border-border cursor-not-allowed opacity-60";
  } else if (isDragActive) {
    containerClass += " bg-primary/5 border-solid border-primary";
  } else {
    containerClass += " border-border";
  }

  return (
    <div>
      <div {...getRootProps({ className: containerClass })}>
        {/* CTRL-02 exception: native file picker — primitive <Input> does not wrap file-type inputs (browser-native styling retained). */}
        <input {...getInputProps()} />
        {uploadMutation.isPending ? (
          <div className="flex flex-col items-center gap-2">
            <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
            <span className="text-xs text-muted-foreground">
              {t("signage.admin.media.upload_title")}
            </span>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-2">
            <p className="text-sm font-semibold text-foreground">
              {t("signage.admin.media.upload_title")}
            </p>
            <p className="text-xs text-muted-foreground">
              {t("signage.admin.media.upload_or")}
            </p>
            <Button
              size="sm"
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                open();
              }}
            >
              {t("signage.admin.media.browse_button")}
            </Button>
            <p className="text-xs text-muted-foreground">
              {t("signage.admin.media.accepted_formats")}
            </p>
          </div>
        )}
      </div>
      {rejectedExt && (
        <p className="mt-2 text-sm text-destructive">
          {t("signage.admin.error.generic", {
            detail: `unsupported: .${rejectedExt}`,
          })}
        </p>
      )}
    </div>
  );
}
