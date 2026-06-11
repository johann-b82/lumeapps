import { useDropzone } from "react-dropzone";
import type { FileRejection } from "react-dropzone";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { Loader2 } from "lucide-react";
import { useState } from "react";

import { uploadAngeboteFile } from "@/lib/api";
import type { AngeboteUploadResponse, ValidationErrorDetail } from "@/lib/api";
import { salesKeys } from "@/lib/queryKeys";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AdminOnly } from "@/auth/AdminOnly";

interface Props {
  onUploadSuccess?: () => void;
  onUploadError?: (errs: ValidationErrorDetail[]) => void;
}

/**
 * AngeboteDropZone — admin-only dropzone for AswKpf_ANG.txt offer dumps.
 * POSTs to /api/upload-angebote and invalidates sales activity queries so
 * the Angebote €/rep/week chart refetches with the new data.
 */
export function AngeboteDropZone({
  onUploadSuccess,
  onUploadError,
}: Props = {}) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [rejectedExt, setRejectedExt] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: uploadAngeboteFile,
    onSuccess: (data: AngeboteUploadResponse) => {
      toast.success(t("angebote_upload.title"), {
        description: t("angebote_upload.summary", {
          inserted: data.rows_inserted,
          updated: data.rows_updated,
        }),
      });
      queryClient.invalidateQueries({ queryKey: ["uploads"] });
      queryClient.invalidateQueries({ queryKey: salesKeys.all });
      if (data.errors && data.errors.length > 0) {
        onUploadError?.(data.errors);
      } else {
        onUploadSuccess?.();
      }
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop: (accepted: File[], rejections: FileRejection[]) => {
      setRejectedExt(null);
      if (rejections.length > 0) {
        const name = rejections[0].file.name;
        setRejectedExt(name.split(".").pop() ?? name);
        return;
      }
      if (accepted.length > 0) mutation.mutate(accepted[0]);
    },
    accept: { "text/plain": [".txt"] },
    maxFiles: 1,
    disabled: mutation.isPending,
    noClick: true,
    noKeyboard: true,
  });

  let containerClass =
    "flex flex-col items-center justify-center gap-3 min-h-[160px] rounded-md border-2 border-dashed transition-colors p-6";
  if (mutation.isPending) {
    containerClass += " bg-muted border-border cursor-not-allowed";
  } else if (isDragActive) {
    containerClass += " bg-primary/5 border-solid border-primary";
  } else {
    containerClass += " bg-muted border-border";
  }

  return (
    <Card>
      <CardContent className="p-0">
        <div {...getRootProps({ className: containerClass })}>
          <input {...getInputProps()} />
          {mutation.isPending ? (
            <div className="flex flex-col items-center gap-2">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
              <span className="text-sm text-muted-foreground">
                {t("processing")}
              </span>
            </div>
          ) : (
            <>
              <p
                className={`text-sm font-medium ${isDragActive ? "text-primary" : "text-muted-foreground"}`}
              >
                {t("angebote_upload.dropzone_prompt")}
              </p>
              <p className="text-xs text-muted-foreground">{t("dropzone_or")}</p>
              <AdminOnly>
                <Button type="button" variant="default" size="sm" onClick={open}>
                  {t("browse_button")}
                </Button>
              </AdminOnly>
              <p className="text-xs text-muted-foreground">
                {t("angebote_upload.accepted_formats")}
              </p>
            </>
          )}
        </div>
        {rejectedExt && (
          <p className="px-4 py-2 text-sm text-destructive">
            {t("invalid_file_type", { ext: rejectedExt })}
          </p>
        )}
      </CardContent>
    </Card>
  );
}
