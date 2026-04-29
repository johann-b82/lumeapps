import { useTranslation } from "react-i18next";
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from "@dnd-kit/core";
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  verticalListSortingStrategy,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical, X } from "lucide-react";

import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { SignageMedia } from "@/signage/lib/signageTypes";

const DIRECTUS_URL =
  (import.meta.env.VITE_DIRECTUS_URL as string | undefined) ??
  "http://localhost:8055";

export type PlaylistItemTransition = "fade" | "cut";

export interface PlaylistItemFormState {
  /** Stable client-only key for @dnd-kit reconciliation. */
  key: string;
  media_id: string;
  duration_s: number;
  transition: PlaylistItemTransition;
}

export interface PlaylistItemListProps {
  items: PlaylistItemFormState[];
  /** Lookup table for thumbnails + titles. Missing keys render a placeholder. */
  mediaLookup: Map<string, SignageMedia>;
  onChange: (next: PlaylistItemFormState[]) => void;
  onRemove: (key: string) => void;
}

function thumbnailUrl(media: SignageMedia | undefined): string | null {
  if (!media) return null;
  if (
    (media.kind === "image" || media.kind === "video") &&
    media.uri
  ) {
    return `${DIRECTUS_URL}/assets/${media.uri}`;
  }
  return null;
}

interface SortableRowProps {
  item: PlaylistItemFormState;
  media: SignageMedia | undefined;
  onChangeOne: (next: PlaylistItemFormState) => void;
  onRemove: () => void;
}

function SortablePlaylistItemRow({
  item,
  media,
  onChangeOne,
  onRemove,
}: SortableRowProps) {
  const { t } = useTranslation();
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: item.key });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.6 : 1,
  };

  const thumb = thumbnailUrl(media);
  const title = media?.title ?? t("signage.admin.editor.empty_title");

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="flex items-center gap-3 p-3 border border-border rounded-md bg-card"
    >
      <Button
        type="button"
        variant="ghost"
        size="icon-sm"
        {...attributes}
        {...listeners}
        aria-label={`Drag to reorder ${title}`}
        aria-roledescription="drag handle"
        className="cursor-grab touch-none"
      >
        <GripVertical className="w-5 h-5" />
      </Button>

      <div className="w-10 h-10 rounded-md bg-muted overflow-hidden flex items-center justify-center shrink-0">
        {thumb ? (
          <img src={thumb} alt="" className="w-full h-full object-cover" />
        ) : (
          <span className="text-xs text-muted-foreground">{media?.kind ?? "?"}</span>
        )}
      </div>

      <span className="text-sm truncate flex-1" title={title}>
        {title}
      </span>

      <Input
        type="number"
        min={1}
        max={3600}
        value={item.duration_s}
        onChange={(e) => {
          const next = Math.max(1, Number(e.target.value) || 1);
          onChangeOne({ ...item, duration_s: next });
        }}
        className="w-20"
        aria-label={t("signage.admin.editor.duration_label")}
      />

      <Select
        value={item.transition}
        onValueChange={(v: string) =>
          onChangeOne({
            ...item,
            transition: v as PlaylistItemTransition,
          })
        }
      >
        <SelectTrigger
          aria-label={t("signage.admin.editor.transition_label")}
          className="w-28"
        >
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value="fade">
            {t("signage.admin.editor.transition_fade")}
          </SelectItem>
          <SelectItem value="cut">
            {t("signage.admin.editor.transition_cut")}
          </SelectItem>
        </SelectContent>
      </Select>

      <Button
        type="button"
        variant="ghost"
        size="icon"
        onClick={onRemove}
        aria-label={`Remove ${title}`}
      >
        <X className="w-4 h-4" />
      </Button>
    </div>
  );
}

/**
 * Phase 46 Plan 46-05 — drag-and-drop playlist item list.
 *
 * Sensors: PointerSensor (mouse/touch) + KeyboardSensor with
 * sortableKeyboardCoordinates (Pitfall 4 — keyboard a11y for D-12).
 *
 * Drag handle: a dedicated <GripVertical> button receives `{...listeners}`
 * (Pitfall 5 — full-row listeners would conflict with row-internal inputs).
 */
export function PlaylistItemList({
  items,
  mediaLookup,
  onChange,
  onRemove,
}: PlaylistItemListProps) {
  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    }),
  );

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = items.findIndex((i) => i.key === active.id);
    const newIndex = items.findIndex((i) => i.key === over.id);
    if (oldIndex === -1 || newIndex === -1) return;
    onChange(arrayMove(items, oldIndex, newIndex));
  }

  function handleChangeOne(next: PlaylistItemFormState) {
    onChange(items.map((i) => (i.key === next.key ? next : i)));
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <SortableContext
        items={items.map((i) => i.key)}
        strategy={verticalListSortingStrategy}
      >
        <div className="space-y-2">
          {items.map((item) => (
            <SortablePlaylistItemRow
              key={item.key}
              item={item}
              media={mediaLookup.get(item.media_id)}
              onChangeOne={handleChangeOne}
              onRemove={() => onRemove(item.key)}
            />
          ))}
        </div>
      </SortableContext>
    </DndContext>
  );
}
