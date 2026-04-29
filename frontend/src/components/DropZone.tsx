import { useDropzone } from "react-dropzone";
import type { FileRejection } from "react-dropzone";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { Loader2 } from "lucide-react";
import { uploadFile } from "@/lib/api";
import type { UploadResponse } from "@/lib/api";
import { kpiKeys } from "@/lib/queryKeys";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AdminOnly } from "@/auth/AdminOnly";
import { useState } from "react";

interface DropZoneProps {
  onUploadSuccess: (data: UploadResponse) => void;
  onUploadError: (data: UploadResponse) => void;
}

export function DropZone({ onUploadSuccess, onUploadError }: DropZoneProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [rejectedExt, setRejectedExt] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: uploadFile,
    onSuccess: (data) => {
      const filename = data.filename;
      if (data.status === "partial") {
        toast.success(t("upload_success_title"), {
          description: t("upload_partial_body", {
            filename,
            count: data.row_count,
            errors: data.error_count,
          }),
        });
      } else {
        toast.success(t("upload_success_title"), {
          description: t("upload_success_body", {
            filename,
            count: data.row_count,
          }),
        });
      }
      queryClient.invalidateQueries({ queryKey: ["uploads"] });
      queryClient.invalidateQueries({ queryKey: kpiKeys.all });

      if (data.status === "success") {
        onUploadSuccess(data);
      } else {
        // "partial" and "failed" both route to onUploadError so ErrorList stays visible
        onUploadError(data);
      }
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop: (acceptedFiles: File[], fileRejections: FileRejection[]) => {
      setRejectedExt(null);
      if (fileRejections.length > 0) {
        const name = fileRejections[0].file.name;
        setRejectedExt(name.split(".").pop() ?? name);
        return;
      }
      if (acceptedFiles.length > 0) {
        mutation.mutate(acceptedFiles[0]);
      }
    },
    accept: {
      "text/csv": [".csv"],
      "text/plain": [".txt"],
    },
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
          {/* CTRL-02 exception: native file picker — primitive <Input> does not wrap file-type inputs (browser-native styling retained). */}
          <input {...getInputProps()} />

          {mutation.isPending ? (
            <div className="flex flex-col items-center gap-2">
              <Loader2 className="h-6 w-6 animate-spin text-primary" />
              <span className="text-sm text-muted-foreground">{t("processing")}</span>
            </div>
          ) : (
            <>
              <p
                className={`text-sm font-medium ${isDragActive ? "text-primary" : "text-muted-foreground"}`}
              >
                {t("dropzone_prompt")}
              </p>
              <p className="text-xs text-muted-foreground">{t("dropzone_or")}</p>
              <AdminOnly>
                <Button
                  type="button"
                  variant="default"
                  size="sm"
                  onClick={open}
                >
                  {t("browse_button")}
                </Button>
              </AdminOnly>
              <p className="text-xs text-muted-foreground">{t("accepted_formats")}</p>
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
