import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { ChevronDown, ChevronRight, Search } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { runSnmpWalk, type SnmpWalkEntry } from "@/lib/api";
import type { SensorDraftRow } from "@/hooks/useSensorDraft";

/**
 * Phase 40-02 — SNMP-Walk OID-Finder (SEN-ADM-06).
 *
 * Collapsible card with host/port/community/base-OID inputs, Walk button,
 * scrollable results table, and click-to-assign into target sensor row's
 * temperature_oid or humidity_oid via `updateRow`.
 *
 * Community is NEVER auto-filled from stored ciphertext (write-only rule —
 * the backend can't decrypt it for the admin, and echoing ciphertext would
 * leak no useful plaintext). Host/port are seeded from the first existing
 * sensor row to save typing.
 *
 * Timeout: Promise.race(30_000) mirrors backend asyncio.wait_for(timeout=30).
 */

const WALK_TIMEOUT_MS = 30_000;
const TIMEOUT_SENTINEL = "timeout";

function walkWithTimeout(
  body: Parameters<typeof runSnmpWalk>[0],
): Promise<SnmpWalkEntry[]> {
  return Promise.race<SnmpWalkEntry[]>([
    runSnmpWalk(body),
    new Promise<SnmpWalkEntry[]>((_, reject) =>
      setTimeout(() => reject(new Error(TIMEOUT_SENTINEL)), WALK_TIMEOUT_MS),
    ),
  ]);
}

type WalkField = "temperature_oid" | "humidity_oid";

export interface SnmpWalkCardProps {
  rows: SensorDraftRow[];
  onUpdateRow: (_localId: string, patch: Partial<SensorDraftRow>) => void;
}

export function SnmpWalkCard({ rows, onUpdateRow }: SnmpWalkCardProps) {
  const { t } = useTranslation();
  const [expanded, setExpanded] = useState(false);

  // Seed host/port from the first live (non-deleted) sensor row.
  const seed = useMemo(() => {
    const first = rows.find((r) => !r._markedForDelete);
    return {
      host: first?.host ?? "",
      port: first?.port ?? 161,
    };
  }, [rows]);

  const [host, setHost] = useState<string>(seed.host);
  const [port, setPort] = useState<number>(seed.port);
  const [community, setCommunity] = useState<string>("");
  const [baseOid, setBaseOid] = useState<string>(".1.3.6.1");
  const [isRunning, setIsRunning] = useState(false);
  const [results, setResults] = useState<SnmpWalkEntry[] | null>(null);

  // Click-to-assign picker state: which result is being assigned.
  const [picker, setPicker] = useState<{
    oid: string;
    localId: string;
    field: WalkField;
  } | null>(null);

  const liveRows = useMemo(() => rows.filter((r) => !r._markedForDelete), [rows]);

  const canRun =
    host.trim().length > 0 && community.length > 0 && baseOid.trim().length > 0;

  const handleRun = async () => {
    if (!canRun) return;
    setIsRunning(true);
    try {
      const data = await walkWithTimeout({
        host: host.trim(),
        port,
        community,
        base_oid: baseOid.trim(),
      });
      setResults(data);
      toast.success(t("sensors.admin.walk.results_count", { count: data.length }));
    } catch (err) {
      const isTimeout =
        err instanceof Error && err.message === TIMEOUT_SENTINEL;
      if (isTimeout) {
        toast.error(t("sensors.admin.walk.timeout"));
      } else {
        const detail = err instanceof Error ? err.message : "Unknown error";
        toast.error(t("sensors.admin.walk.failure", { detail }));
      }
      setResults(null);
    } finally {
      setIsRunning(false);
    }
  };

  const handleAssignConfirm = () => {
    if (!picker) return;
    onUpdateRow(picker.localId, { [picker.field]: picker.oid } as Partial<SensorDraftRow>);
    setPicker(null);
  };

  return (
    <Card>
      <CardHeader>
        <Button
          type="button"
          variant="ghost"
          size="default"
          className="w-full h-auto justify-start text-left px-0"
          onClick={() => setExpanded((v) => !v)}
          aria-expanded={expanded}
        >
          {expanded ? (
            <ChevronDown className="h-4 w-4" aria-hidden="true" />
          ) : (
            <ChevronRight className="h-4 w-4" aria-hidden="true" />
          )}
          <CardTitle className="text-xl font-semibold">
            {t("sensors.admin.walk.title")}
          </CardTitle>
        </Button>
      </CardHeader>
      {expanded && (
        <CardContent className="space-y-4">
          {/* Inputs row */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="flex flex-col gap-2">
              <Label htmlFor="walk-host" className="text-sm font-medium">
                {t("sensors.admin.walk.host")}
              </Label>
              <Input
                id="walk-host"
                value={host}
                onChange={(e) => setHost(e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="walk-port" className="text-sm font-medium">
                {t("sensors.admin.walk.port")}
              </Label>
              <Input
                id="walk-port"
                type="number"
                min={1}
                max={65535}
                value={port}
                onChange={(e) => setPort(Number(e.target.value))}
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="walk-community" className="text-sm font-medium">
                {t("sensors.admin.walk.community")}
              </Label>
              <Input
                id="walk-community"
                type="password"
                value={community}
                onChange={(e) => setCommunity(e.target.value)}
                autoComplete="new-password"
              />
            </div>
            <div className="flex flex-col gap-2">
              <Label htmlFor="walk-base-oid" className="text-sm font-medium">
                {t("sensors.admin.walk.base_oid")}
              </Label>
              <Input
                id="walk-base-oid"
                value={baseOid}
                onChange={(e) => setBaseOid(e.target.value)}
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
            <Button type="button" onClick={handleRun} disabled={!canRun || isRunning}>
              <Search className="h-4 w-4 mr-1" aria-hidden="true" />
              {isRunning
                ? t("sensors.admin.walk.running")
                : t("sensors.admin.walk.run")}
            </Button>
            {results && (
              <span className="text-sm text-muted-foreground">
                {t("sensors.admin.walk.results_count", { count: results.length })}
              </span>
            )}
          </div>

          {/* Results panel */}
          {results !== null && results.length === 0 && (
            <p className="text-sm text-muted-foreground">
              {t("sensors.admin.walk.empty")}
            </p>
          )}

          {results !== null && results.length > 0 && (
            <div className="max-h-96 overflow-y-auto rounded-md border border-border">
              <table className="w-full text-sm">
                <thead className="bg-muted/30 sticky top-0">
                  <tr>
                    <th className="text-left font-medium px-3 py-2">OID</th>
                    <th className="text-left font-medium px-3 py-2">Type</th>
                    <th className="text-left font-medium px-3 py-2">Value</th>
                    <th className="text-right font-medium px-3 py-2">
                      {t("sensors.admin.walk.assign_confirm")}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {results.map((entry) => (
                    <tr
                      key={entry.oid}
                      className="border-t border-border hover:bg-accent/10 transition-colors"
                    >
                      <td className="px-3 py-2 font-mono text-xs break-all">
                        {entry.oid}
                      </td>
                      <td className="px-3 py-2 text-xs text-muted-foreground">
                        {entry.type}
                      </td>
                      <td className="px-3 py-2 text-xs break-all">{entry.value}</td>
                      <td className="px-3 py-2 text-right">
                        <Button
                          type="button"
                          variant="ghost"
                          className="h-8 px-2 text-xs"
                          onClick={() =>
                            setPicker({
                              oid: entry.oid,
                              localId: liveRows[0]?._localId ?? "",
                              field: "temperature_oid",
                            })
                          }
                          disabled={liveRows.length === 0}
                        >
                          {t("sensors.admin.walk.assign_confirm")}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Assign picker */}
          {picker && (
            <div className="rounded-md border border-border bg-card p-4 space-y-3">
              <p className="text-sm font-medium break-all">
                <span className="text-muted-foreground">OID:</span>{" "}
                <span className="font-mono text-xs">{picker.oid}</span>
              </p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="flex flex-col gap-2">
                  <Label className="text-sm font-medium">
                    {t("sensors.admin.walk.assign_target")}
                  </Label>
                  <Select
                    value={picker.localId}
                    onValueChange={(v: string) =>
                      setPicker({ ...picker, localId: v })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {liveRows.map((r) => (
                        <SelectItem key={r._localId} value={r._localId}>
                          {r.name || "(unnamed)"}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="flex flex-col gap-2">
                  <Label className="text-sm font-medium">Field</Label>
                  <Select
                    value={picker.field}
                    onValueChange={(v: string) =>
                      setPicker({
                        ...picker,
                        field: v as WalkField,
                      })
                    }
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="temperature_oid">
                        {t("sensors.admin.walk.assign_to_temp")}
                      </SelectItem>
                      <SelectItem value="humidity_oid">
                        {t("sensors.admin.walk.assign_to_humidity")}
                      </SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>
              <div className="flex items-center justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setPicker(null)}
                >
                  {t("sensors.admin.remove_confirm.cancel")}
                </Button>
                <Button type="button" onClick={handleAssignConfirm}>
                  {t("sensors.admin.walk.assign_confirm")}
                </Button>
              </div>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  );
}
