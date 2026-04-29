import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { getUploads, deleteUpload } from "@/lib/api";
import type { UploadBatchSummary } from "@/lib/api";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
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
  // failed
  return (
    <Badge className="bg-destructive text-destructive-foreground hover:bg-destructive">
      {status}
    </Badge>
  );
}

export function UploadHistory() {
  const { t } = useTranslation();
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

  const columnHeaderClass = "uppercase text-xs tracking-wider text-muted-foreground";

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="h-10 w-full rounded animate-pulse bg-muted"
          />
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
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead className={columnHeaderClass}>{t("col_filename")}</TableHead>
          <TableHead className={columnHeaderClass}>{t("col_uploaded_at")}</TableHead>
          <TableHead className={columnHeaderClass}>{t("col_rows")}</TableHead>
          <TableHead className={columnHeaderClass}>{t("col_status")}</TableHead>
          <TableHead className={columnHeaderClass}>{t("col_errors")}</TableHead>
          <TableHead className={columnHeaderClass + " w-12"} />
        </TableRow>
      </TableHeader>
      <TableBody>
        {uploads.map((batch) => (
          <TableRow key={batch.id}>
            <TableCell className="text-sm font-medium">{batch.filename}</TableCell>
            <TableCell className="text-sm text-muted-foreground">
              {new Date(batch.uploaded_at).toLocaleString()}
            </TableCell>
            <TableCell className="text-sm">{batch.row_count}</TableCell>
            <TableCell>
              <StatusBadge status={batch.status} />
            </TableCell>
            <TableCell
              className={`text-sm ${batch.error_count === 0 ? "text-muted-foreground" : "text-foreground"}`}
            >
              {batch.error_count}
            </TableCell>
            <TableCell>
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
            </TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
