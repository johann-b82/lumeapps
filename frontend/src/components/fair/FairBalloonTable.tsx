/**
 * Running table of {number, value} for every balloon, sorted by number. Rows
 * can be reordered by drag-and-drop — dropping renumbers the balloons 1..n in
 * the new order (server-side, reflected on the drawing). "Copy for Excel" puts
 * a TSV on the clipboard; CSV download uses semicolons + a BOM for German
 * Excel. Values are editable inline; a row can be deleted (server renumbers).
 */
import {
  DndContext,
  KeyboardSensor,
  PointerSensor,
  closestCenter,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import type { DragEndEvent } from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Copy, Download, GripVertical, Loader2, RefreshCw, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { fairApi } from "@/lib/fairApi";
import type { FairBalloon, FairProjectDetail } from "@/lib/fairApi";
import { fairKeys } from "@/lib/queryKeys";
import { buildCsv, buildTsv, sanitizeFilename } from "./geometry";

interface FairBalloonTableProps {
  projectId: string;
  projectName: string;
  balloons: readonly FairBalloon[];
  showPage: boolean;
  /** Re-run OCR on a balloon's stored region; returns the fresh text, "" if
   *  nothing was read, or null if OCR isn't available. */
  onReocr: (b: FairBalloon) => Promise<string | null>;
}

export function FairBalloonTable({
  projectId,
  projectName,
  balloons,
  showPage,
  onReocr,
}: FairBalloonTableProps) {
  const { t } = useTranslation();
  const queryClient = useQueryClient();
  const [reloadingId, setReloadingId] = useState<string | null>(null);
  // Newest (highest number) on top.
  const rows = [...balloons].sort((a, b) => b.number - a.number);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: fairKeys.project(projectId) });

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    // Rows are DESCENDING (newest on top); the reorder API numbers 1..n in the
    // given order, so the ascending id list is the reversed display order.
    const idsDesc = rows.map((r) => r.id);
    const oldIndex = idsDesc.indexOf(String(active.id));
    const newIndex = idsDesc.indexOf(String(over.id));
    if (oldIndex < 0 || newIndex < 0) return;
    const newDesc = arrayMove(idsDesc, oldIndex, newIndex);
    const orderedAsc = [...newDesc].reverse();

    // Optimistic: renumber in the query cache so the UI + drawing update now.
    queryClient.setQueryData<FairProjectDetail>(
      fairKeys.project(projectId),
      (old) => {
        if (!old) return old;
        const byId = new Map(old.balloons.map((b) => [b.id, b]));
        const renumbered = orderedAsc
          .map((id, i) => {
            const b = byId.get(id);
            return b ? { ...b, number: i + 1 } : null;
          })
          .filter((b): b is FairBalloon => b !== null);
        return { ...old, balloons: renumbered };
      },
    );

    fairApi
      .reorderBalloons(projectId, orderedAsc)
      .then(() => invalidate())
      .catch((e: Error) => {
        toast.error(e.message);
        void invalidate();
      });
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(
        buildTsv(rows, [t("fair.table.number"), t("fair.table.value")]),
      );
      toast.success(t("fair.table.copied"));
    } catch {
      toast.error(t("fair.table.copyFailed"));
    }
  };

  const handleCsv = () => {
    const csv = buildCsv(rows, [t("fair.table.number"), t("fair.table.value")]);
    const blob = new Blob(["﻿" + csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${sanitizeFilename(projectName)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleDelete = async (id: string) => {
    try {
      await fairApi.deleteBalloon(id);
      await invalidate();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  // Re-run OCR on this row's marked region and save the fresh value.
  const handleReocrRow = async (b: FairBalloon) => {
    setReloadingId(b.id);
    try {
      const text = await onReocr(b);
      if (text === null) {
        toast.error(t("fair.table.reocrUnavailable"));
      } else if (text.trim() === "") {
        toast(t("fair.table.reocrEmpty"));
      } else {
        await fairApi.patchBalloon(b.id, { value_text: text });
        await invalidate();
      }
    } catch (e) {
      toast.error((e as Error).message);
    } finally {
      setReloadingId(null);
    }
  };

  const handleValueSave = async (id: string, value: string) => {
    try {
      await fairApi.patchBalloon(id, { value_text: value });
      await invalidate();
    } catch (e) {
      toast.error((e as Error).message);
    }
  };

  const colCount = showPage ? 5 : 4;

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">
          {t("fair.table.title")} ({rows.length})
        </h3>
        <div className="flex gap-2">
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={() => void handleCopy()}
            disabled={rows.length === 0}
          >
            <Copy className="h-4 w-4" />
            <span className="ml-1">{t("fair.table.copy")}</span>
          </Button>
          <Button
            type="button"
            size="sm"
            variant="outline"
            onClick={handleCsv}
            disabled={rows.length === 0}
          >
            <Download className="h-4 w-4" />
            <span className="ml-1">CSV</span>
          </Button>
        </div>
      </div>

      <div className="max-h-[82vh] overflow-y-auto rounded-md border">
        <Table>
          <TableHeader className="sticky top-0 z-10 bg-background">
            <TableRow>
              <TableHead className="w-8" />
              <TableHead className="w-16">{t("fair.table.number")}</TableHead>
              {showPage && (
                <TableHead className="w-20">{t("fair.table.page")}</TableHead>
              )}
              <TableHead>{t("fair.table.value")}</TableHead>
              <TableHead className="w-20" />
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={colCount}
                  className="text-center text-sm text-muted-foreground"
                >
                  {t("fair.table.empty")}
                </TableCell>
              </TableRow>
            ) : (
              <DndContext
                sensors={sensors}
                collisionDetection={closestCenter}
                onDragEnd={handleDragEnd}
              >
                <SortableContext
                  items={rows.map((r) => r.id)}
                  strategy={verticalListSortingStrategy}
                >
                  {rows.map((b) => (
                    <SortableRow
                      key={b.id}
                      balloon={b}
                      showPage={showPage}
                      reorderLabel={t("fair.table.reorder")}
                      reloadLabel={t("fair.table.reloadRow")}
                      deleteLabel={t("fair.table.delete")}
                      reloading={reloadingId === b.id}
                      onValueSave={(v) => void handleValueSave(b.id, v)}
                      onReload={() => void handleReocrRow(b)}
                      onDelete={() => void handleDelete(b.id)}
                    />
                  ))}
                </SortableContext>
              </DndContext>
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}

function SortableRow({
  balloon,
  showPage,
  reorderLabel,
  reloadLabel,
  deleteLabel,
  reloading,
  onValueSave,
  onReload,
  onDelete,
}: {
  balloon: FairBalloon;
  showPage: boolean;
  reorderLabel: string;
  reloadLabel: string;
  deleteLabel: string;
  reloading: boolean;
  onValueSave: (v: string) => void;
  onReload: () => void;
  onDelete: () => void;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: balloon.id });

  return (
    <TableRow
      ref={setNodeRef}
      style={{
        transform: CSS.Transform.toString(transform),
        transition,
        opacity: isDragging ? 0.5 : 1,
      }}
    >
      <TableCell className="w-8">
        <button
          type="button"
          className="flex cursor-grab items-center text-muted-foreground touch-none active:cursor-grabbing"
          aria-label={reorderLabel}
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-4 w-4" />
        </button>
      </TableCell>
      <TableCell className="font-medium tabular-nums">{balloon.number}</TableCell>
      {showPage && (
        <TableCell className="tabular-nums">{balloon.page_no}</TableCell>
      )}
      <TableCell>
        <ValueCell value={balloon.value_text} onSave={onValueSave} />
      </TableCell>
      <TableCell>
        <div className="flex items-center gap-0.5">
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            onClick={onReload}
            disabled={reloading}
            title={reloadLabel}
          >
            {reloading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
          </Button>
          <Button
            type="button"
            size="icon-sm"
            variant="ghost"
            onClick={onDelete}
            title={deleteLabel}
          >
            <Trash2 className="h-4 w-4 text-destructive" />
          </Button>
        </div>
      </TableCell>
    </TableRow>
  );
}

/**
 * Inline value editor — commits on blur or Enter if changed. Uncontrolled +
 * keyed by the server value: while editing, `value` is unchanged so the input
 * keeps the user's text; once a save lands and the query refetches, the new
 * `value` changes the key and the input remounts with the fresh default.
 */
function ValueCell({
  value,
  onSave,
}: {
  value: string;
  onSave: (v: string) => void;
}) {
  return (
    <Input
      key={value}
      defaultValue={value}
      className="h-8"
      onBlur={(e) => {
        const v = e.currentTarget.value;
        if (v !== value) onSave(v);
      }}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
      }}
    />
  );
}
