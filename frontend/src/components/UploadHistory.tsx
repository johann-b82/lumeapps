import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { getUploads, deleteUpload } from "@/lib/api";
import type { UploadBatchSummary } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { DeleteButton } from "@/components/ui/delete-button";
import { AdminOnly } from "@/auth/AdminOnly";

function StatusBadge({ status }: { status: UploadBatchSummary["status"] }) {
  if (status === "success") {
    return (
      <Badge className="bg-[var(--color-success)] text-white hover:bg-[var(--color-success)]">
        {status}
      </Badge>
    );
  }
  if (status === "partial") {
    return (
      <Badge className="bg-[var(--color-warning)] text-foreground hover:bg-[var(--color-warning)]">
        {status}
      </Badge>
    );
  }
  return (
    <Badge className="bg-destructive text-destructive-foreground hover:bg-destructive">
      {status}
    </Badge>
  );
}

export function UploadHistory() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language === "de" ? "de-DE" : "en-US";
  const queryClient = useQueryClient();

  const { data: uploads, isLoading } = useQuery({
    queryKey: ["uploads"],
    queryFn: getUploads,
  });

  const deleteMutation = useMutation({
    mutationFn: deleteUpload,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["uploads"] });
    },
  });

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-10 w-full rounded animate-pulse bg-muted" />
        ))}
      </div>
    );
  }

  if (!uploads || uploads.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 gap-2">
        <p className="text-base font-semibold text-foreground">
          {t("empty_title")}
        </p>
        <p className="text-sm text-muted-foreground">{t("empty_body")}</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-md border border-border">
      <table className="w-full min-w-[640px] text-sm">
        <thead>
          <tr className="border-b border-border bg-muted/50">
            <th className="px-3 py-2 font-medium text-left">{t("col_filename")}</th>
            <th className="px-3 py-2 font-medium text-left">{t("col_kind")}</th>
            <th className="px-3 py-2 font-medium text-left">{t("col_uploaded_at")}</th>
            <th className="px-3 py-2 font-medium text-right">{t("col_rows")}</th>
            <th className="px-3 py-2 font-medium text-left">{t("col_status")}</th>
            <th className="px-3 py-2 font-medium text-right">{t("col_errors")}</th>
            <th className="px-3 py-2 font-medium w-12" />
          </tr>
        </thead>
        <tbody>
          {uploads.map((batch) => (
            <tr key={batch.id} className="border-b border-border last:border-0 hover:bg-muted/30">
              <td className="px-3 py-2 font-medium">{batch.filename}</td>
              <td className="px-3 py-2">
                <Badge variant="outline" className="capitalize">
                  {t(`kind_${batch.kind}`)}
                </Badge>
              </td>
              <td className="px-3 py-2 text-muted-foreground">
                {new Date(batch.uploaded_at).toLocaleString(locale)}
              </td>
              <td className="px-3 py-2 text-right tabular-nums">{batch.row_count}</td>
              <td className="px-3 py-2">
                <StatusBadge status={batch.status} />
              </td>
              <td
                className={`px-3 py-2 text-right tabular-nums ${
                  batch.error_count === 0 ? "text-muted-foreground" : "text-foreground"
                }`}
              >
                {batch.error_count}
              </td>
              <td className="px-3 py-2">
                <AdminOnly>
                  <DeleteButton
                    itemLabel={batch.filename}
                    onConfirm={() => deleteMutation.mutateAsync(batch.id)}
                    dialogTitle={t("delete_title")}
                    cancelLabel={t("delete_cancel")}
                    confirmLabel={t("delete_confirm")}
                    dialogBody={t("delete_body", {
                      filename: batch.filename,
                      count: batch.row_count,
                    })}
                    aria-label={t("delete_title")}
                  />
                </AdminOnly>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
