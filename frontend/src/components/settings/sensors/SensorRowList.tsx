import type { SensorDraftRow } from "@/hooks/useSensorDraft";
import { SensorRowForm } from "./SensorRowForm";

export interface SensorRowListProps {
  rows: SensorDraftRow[];
  onUpdate: (localId: string, patch: Partial<SensorDraftRow>) => void;
  onRemove: (localId: string) => void;
}

/**
 * Phase 40-01 — renders the list of draft sensor rows as SensorRowForm cards.
 */
export function SensorRowList({ rows, onUpdate, onRemove }: SensorRowListProps) {
  return (
    <div className="space-y-4">
      {rows.map((row) => (
        <SensorRowForm
          key={row._localId}
          row={row}
          onChange={(patch) => onUpdate(row._localId, patch)}
          onRemove={() => onRemove(row._localId)}
        />
      ))}
    </div>
  );
}
