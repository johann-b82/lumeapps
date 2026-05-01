import { useDropzone } from "react-dropzone";
import type { FileRejection } from "react-dropzone";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useTranslation } from "react-i18next";
import { Loader2 } from "lucide-react";
import { Link as WouterLink } from "wouter";
import { useState } from "react";

import { uploadContactsFile } from "@/lib/api";
import type { ContactsUploadResponse } from "@/lib/api";
import { salesKeys } from "@/lib/queryKeys";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { AdminOnly } from "@/auth/AdminOnly";

/**
 * ContactsDropZone — admin-only dropzone for Kontakte (.txt) ingestion.
 *
 * Mirrors DropZone for orders, but POSTs to /api/upload-contacts and
 * surfaces the unmapped-token report on success. If any tokens were
 * unmapped the toast renders a "Manage aliases" deep-link to
 * /settings/hr#sales-aliases so the admin can curate the mapping.
 */
export function ContactsDropZone() {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [rejectedExt, setRejectedExt] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: uploadContactsFile,
    onSuccess: (data: ContactsUploadResponse) => {
      const unmappedCount = data.unmapped_tokens.length;
      const description = t("contacts_upload.summary", {
        inserted: data.rows_inserted,
        replaced: data.rows_replaced,
      });
      if (unmappedCount > 0) {
        toast.warning(t("contacts_upload.title"), {
          description,
          action: {
            label: t("contacts_upload.manage_aliases"),
            onClick: () => {
              window.location.href = "/settings/hr#sales-aliases";
            },
          },
        });
      } else {
        toast.success(t("contacts_upload.title"), { description });
      }
      queryClient.invalidateQueries({ queryKey: salesKeys.all });
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
                {t("contacts_upload.dropzone_prompt")}
              </p>
              <p className="text-xs text-muted-foreground">{t("dropzone_or")}</p>
              <AdminOnly>
                <Button type="button" variant="default" size="sm" onClick={open}>
                  {t("browse_button")}
                </Button>
              </AdminOnly>
              <p className="text-xs text-muted-foreground">
                {t("contacts_upload.accepted_formats")}
              </p>
              <WouterLink
                href="/settings/hr#sales-aliases"
                className="text-xs text-primary hover:underline"
              >
                {t("contacts_upload.manage_aliases")}
              </WouterLink>
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
