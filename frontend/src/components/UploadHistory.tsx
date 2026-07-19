import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { getUploads, deleteUpload } from "@/lib/api";
import type { UploadBatchSummary } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { DeleteButton } from "@/components/ui/delete-button";
import { AdminOnly } from "@/auth/AdminOnly";
import { DataTable, type DataTableColumn } from "@/components/DataTable";

type UploadRow = UploadBatchSummary & Record<string, unknown>;

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
  const [search, setSearch] = useState("");

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

  const q = search.trim().toLowerCase();
  const rows = (uploads ?? []).filter(
    (b) => !q
      || b.filename.toLowerCase().includes(q)
      || b.kind.toLowerCase().includes(q)
      || b.status.toLowerCase().includes(q),
  ) as UploadRow[];

  const columns: DataTableColumn<UploadRow>[] = [
    { key: "filename", header: t("col_filename"), className: "font-medium" },
    {
      key: "kind", header: t("col_kind"),
      cell: (b) => <Badge variant="outline" className="capitalize">{t(`kind_${b.kind}`)}</Badge>,
    },
    {
      key: "uploaded_at", header: t("col_uploaded_at"), className: "text-muted-foreground",
      cell: (b) => new Date(b.uploaded_at).toLocaleString(locale),
    },
    { key: "row_count", header: t("col_rows"), align: "right", className: "tabular-nums" },
    { key: "status", header: t("col_status"), cell: (b) => <StatusBadge status={b.status} /> },
    {
      key: "error_count", header: t("col_errors"), align: "right",
      className: "tabular-nums",
      cell: (b) => (
        <span className={b.error_count === 0 ? "text-muted-foreground" : "text-foreground"}>
          {b.error_count}
        </span>
      ),
    },
    {
      key: "actions", header: "", sortable: false, className: "w-12",
      cell: (b) => (
        <AdminOnly>
          <DeleteButton
            itemLabel={b.filename}
            onConfirm={() => deleteMutation.mutateAsync(b.id)}
            dialogTitle={t("delete_title")}
            cancelLabel={t("delete_cancel")}
            confirmLabel={t("delete_confirm")}
            dialogBody={t("delete_body", { filename: b.filename, count: b.row_count })}
            aria-label={t("delete_title")}
          />
        </AdminOnly>
      ),
    },
  ];

  return (
    <DataTable
      card={false}
      columns={columns}
      rows={rows}
      rowKey={(b) => b.id}
      isLoading={isLoading}
      initialSort={{ key: "uploaded_at", dir: "desc" }}
      pageSize={25}
      search={{ value: search, onChange: setSearch, placeholder: t("col_filename") }}
      emptyText={
        <span className="flex flex-col items-center gap-1">
          <span className="text-base font-semibold text-foreground">{t("empty_title")}</span>
          <span>{t("empty_body")}</span>
        </span>
      }
    />
  );
}
