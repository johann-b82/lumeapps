/**
 * Upload a drawing (PDF/PNG/JPG) → POST /api/fair/projects → navigate to the
 * new project's editor. Mirrors the repo's other DropZone components.
 */
import { useState } from "react";
import { useDropzone } from "react-dropzone";
import type { FileRejection } from "react-dropzone";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useLocation } from "wouter";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Loader2, Upload } from "lucide-react";
import { Button } from "@/components/ui/button";
import { fairApi } from "@/lib/fairApi";
import { fairKeys } from "@/lib/queryKeys";

export function FairUpload() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [, navigate] = useLocation();
  const [rejected, setRejected] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (file: File) => fairApi.createProject(file),
    onSuccess: (project) => {
      queryClient.invalidateQueries({ queryKey: fairKeys.projects() });
      navigate(`/fair/${project.id}`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const { getRootProps, getInputProps, isDragActive, open } = useDropzone({
    onDrop: (accepted: File[], rejections: FileRejection[]) => {
      setRejected(null);
      if (rejections.length > 0) {
        const name = rejections[0].file.name;
        setRejected(name.split(".").pop() ?? name);
        return;
      }
      if (accepted.length > 0) mutation.mutate(accepted[0]);
    },
    accept: {
      "application/pdf": [".pdf"],
      "image/png": [".png"],
      "image/jpeg": [".jpg", ".jpeg"],
    },
    maxFiles: 1,
    disabled: mutation.isPending,
    noClick: true,
    noKeyboard: true,
  });

  return (
    <div
      {...getRootProps()}
      className={`flex flex-col items-center justify-center gap-3 rounded-md border-2 border-dashed p-8 transition-colors ${
        isDragActive
          ? "border-primary bg-primary/5"
          : "border-border bg-muted/40"
      }`}
    >
      <input {...getInputProps()} />
      {mutation.isPending ? (
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      ) : (
        <Upload className="h-8 w-8 text-muted-foreground" />
      )}
      <p className="text-sm text-muted-foreground">{t("fair.upload.prompt")}</p>
      <Button type="button" onClick={open} disabled={mutation.isPending}>
        {t("fair.upload.button")}
      </Button>
      {rejected && (
        <p className="text-xs text-destructive">
          {t("fair.upload.rejected", { ext: rejected })}
        </p>
      )}
    </div>
  );
}
