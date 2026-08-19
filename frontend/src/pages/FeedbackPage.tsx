import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Trash2, Check, RotateCcw, ExternalLink } from "lucide-react";
import { toast } from "sonner";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { DeleteDialog } from "@/components/ui/delete-dialog";
import {
  getFeedbackList,
  updateFeedbackStatus,
  deleteFeedback,
  type FeedbackItem,
} from "@/lib/api";

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("de-DE", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function FeedbackPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [deleteTarget, setDeleteTarget] = useState<FeedbackItem | null>(null);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["feedback"],
    queryFn: getFeedbackList,
  });

  const statusMutation = useMutation({
    mutationFn: ({ id, status }: { id: string; status: FeedbackItem["status"] }) =>
      updateFeedbackStatus(id, status),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["feedback"] }),
    onError: (err) => toast.error((err as Error).message),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteFeedback(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["feedback"] });
      setDeleteTarget(null);
    },
    onError: (err) => toast.error((err as Error).message),
  });

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-16">
      <Card>
        <CardHeader>
          <CardTitle>{t("feedback.admin.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <div className="flex justify-center py-10">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          )}
          {isError && (
            <div className="py-8 text-center text-destructive">
              {t("feedback.admin.loadError")}
            </div>
          )}
          {data && data.length === 0 && (
            <div className="py-10 text-center text-muted-foreground">
              {t("feedback.admin.empty")}
            </div>
          )}
          {data && data.length > 0 && (
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>{t("feedback.admin.col.date")}</TableHead>
                    <TableHead>{t("feedback.admin.col.reporter")}</TableHead>
                    <TableHead>{t("feedback.admin.col.page")}</TableHead>
                    <TableHead>{t("feedback.admin.col.description")}</TableHead>
                    <TableHead>{t("feedback.admin.col.screenshot")}</TableHead>
                    <TableHead>{t("feedback.admin.col.status")}</TableHead>
                    <TableHead className="text-right">
                      {t("feedback.admin.col.actions")}
                    </TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {data.map((f) => (
                    <TableRow key={f.id}>
                      <TableCell className="whitespace-nowrap text-xs text-muted-foreground">
                        {formatDate(f.created_at)}
                      </TableCell>
                      <TableCell className="text-xs">
                        {f.reporter_email ?? t("feedback.admin.anonymous")}
                      </TableCell>
                      <TableCell className="max-w-40 truncate text-xs font-mono">
                        {f.page_url}
                      </TableCell>
                      <TableCell className="max-w-sm whitespace-pre-wrap text-sm">
                        {f.description}
                      </TableCell>
                      <TableCell>
                        {f.has_screenshot ? (
                          <a
                            href={`/api/feedback/${f.id}/screenshot`}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="inline-flex items-center gap-1 text-xs text-primary hover:underline"
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                            {t("feedback.admin.action.view")}
                          </a>
                        ) : (
                          <span className="text-xs text-muted-foreground">—</span>
                        )}
                      </TableCell>
                      <TableCell>
                        <Badge
                          variant={f.status === "new" ? "default" : "secondary"}
                        >
                          {t(`feedback.admin.status.${f.status}`)}
                        </Badge>
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center justify-end gap-1">
                          {f.status === "new" ? (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() =>
                                statusMutation.mutate({
                                  id: f.id,
                                  status: "resolved",
                                })
                              }
                              title={t("feedback.admin.action.resolve")}
                            >
                              <Check className="h-4 w-4" />
                            </Button>
                          ) : (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() =>
                                statusMutation.mutate({ id: f.id, status: "new" })
                              }
                              title={t("feedback.admin.action.reopen")}
                            >
                              <RotateCcw className="h-4 w-4" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            className="text-destructive"
                            onClick={() => setDeleteTarget(f)}
                            title={t("feedback.admin.action.delete")}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </div>
          )}
        </CardContent>
      </Card>

      <DeleteDialog
        open={deleteTarget !== null}
        onOpenChange={(o) => !o && setDeleteTarget(null)}
        title={t("feedback.admin.delete.title")}
        body={t("feedback.admin.delete.body")}
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
        confirmDisabled={deleteMutation.isPending}
      />
    </div>
  );
}
