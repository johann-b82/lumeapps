import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
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
import { Download, GripVertical } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { SegmentedControl } from "@/components/ui/segmented-control";
import { DataTable, type DataTableColumn } from "@/components/DataTable";
import {
  exportBereich,
  prioApi,
  type BereichsZeile,
  type GesamtZeile,
  type ImportQuelle,
} from "@/lib/produktionPrioApi";

type Tab = "gesamt" | "bereiche" | "import";

const QK = {
  status: ["prio", "status"],
  gesamt: ["prio", "gesamt"],
  bereiche: ["prio", "bereiche"],
} as const;

function datum(s: string | null): string {
  return s ? new Date(s).toLocaleDateString() : "—";
}

function zahl(s: string | null, stellen = 0): string {
  return s == null ? "—" : Number(s).toLocaleString(undefined, { maximumFractionDigits: stellen });
}

/**
 * Produktions-Priorisierung (/production/prio): Gesamtliste mit manueller
 * Sortierung, Tätigkeitslisten je Bereich und die Importe der Apollo-Exporte
 * bzw. Kunden-Priolisten.
 */
export function ProductionPrioPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<Tab>("gesamt");

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-semibold">{t("prio.heading")}</h1>
        <SegmentedControl<Tab>
          segments={[
            { value: "gesamt", label: t("prio.tab.gesamt") },
            { value: "bereiche", label: t("prio.tab.bereiche") },
            { value: "import", label: t("prio.tab.import") },
          ]}
          value={tab}
          onChange={setTab}
        />
      </div>
      {tab === "gesamt" && <GesamtTab />}
      {tab === "bereiche" && <BereicheTab />}
      {tab === "import" && <ImportTab />}
    </div>
  );
}

// ── Gesamtliste ─────────────────────────────────────────────────────────────

const SEITE = 200;

function GesamtTab() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: QK.gesamt, queryFn: prioApi.gesamt });

  // Lokale, noch nicht gespeicherte Reihenfolge; null = Serverstand.
  const [entwurf, setEntwurf] = useState<string[] | null>(null);
  const [suche, setSuche] = useState("");
  const [sichtbar, setSichtbar] = useState(SEITE);

  const serverReihenfolge = useMemo(() => (data ?? []).map((z) => z.schluessel), [data]);
  const reihenfolge = entwurf ?? serverReihenfolge;
  const dirty = entwurf != null;

  const zeilen = useMemo(() => new Map((data ?? []).map((z) => [z.schluessel, z])), [data]);

  const q = suche.trim().toLowerCase();
  const gefiltert = useMemo(
    () =>
      reihenfolge.filter((k) => {
        if (!q) return true;
        const z = zeilen.get(k);
        return [z?.vorgang_nr, z?.artikelnr, z?.bezeichnung, z?.kunde, z?.liste]
          .some((v) => (v ?? "").toLowerCase().includes(q));
      }),
    [reihenfolge, zeilen, q],
  );
  const anzeige = gefiltert.slice(0, sichtbar);
  const platz = useMemo(() => new Map(reihenfolge.map((k, i) => [k, i + 1])), [reihenfolge]);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: QK.gesamt });
    qc.invalidateQueries({ queryKey: QK.bereiche });
    qc.invalidateQueries({ queryKey: ["prio", "bereich"] });
  };
  const speichern = useMutation({
    mutationFn: () => prioApi.saveManuell(reihenfolge),
    onSuccess: () => { toast.success(t("prio.gesamt.saved")); setEntwurf(null); invalidate(); },
    onError: (e: unknown) => toast.error(String(e)),
  });
  const zuruecksetzen = useMutation({
    mutationFn: prioApi.resetManuell,
    onSuccess: () => { setEntwurf(null); invalidate(); },
    onError: (e: unknown) => toast.error(String(e)),
  });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function verschiebe(von: number, nach: number) {
    if (von === nach || von < 0 || nach < 0) return;
    setEntwurf(arrayMove(reihenfolge, von, Math.min(nach, reihenfolge.length - 1)));
  }

  function handleDragEnd({ active, over }: DragEndEvent) {
    if (!over || active.id === over.id) return;
    verschiebe(reihenfolge.indexOf(String(active.id)), reihenfolge.indexOf(String(over.id)));
  }

  if (!isLoading && (data ?? []).length === 0) {
    return <Card className="p-6 text-sm text-muted-foreground">{t("prio.gesamt.empty")}</Card>;
  }

  return (
    <Card className="p-4 space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          className="max-w-xs"
          placeholder={t("prio.gesamt.search")}
          value={suche}
          onChange={(e) => { setSuche(e.target.value); setSichtbar(SEITE); }}
        />
        <span className="text-xs text-muted-foreground flex-1">{t("prio.gesamt.hint")}</span>
        {dirty && <span className="text-xs text-amber-600">{t("prio.gesamt.dirty")}</span>}
        <Button size="sm" disabled={!dirty || speichern.isPending} onClick={() => speichern.mutate()}>
          {t("prio.gesamt.save")}
        </Button>
        <Button
          size="sm"
          variant="outline"
          disabled={zuruecksetzen.isPending}
          onClick={() => { if (confirm(t("prio.gesamt.confirmReset"))) zuruecksetzen.mutate(); }}
        >
          {t("prio.gesamt.reset")}
        </Button>
      </div>

      <div className="overflow-x-auto border rounded-md">
        <table className="w-full text-sm min-w-[960px]">
          <thead className="bg-muted/50 text-left">
            <tr>
              <th className="px-2 py-2 w-8" />
              <th className="px-2 py-2 w-20">{t("prio.col.rang")}</th>
              <th className="px-2 py-2">{t("prio.col.ba")}</th>
              <th className="px-2 py-2">{t("prio.col.artikel")}</th>
              <th className="px-2 py-2">{t("prio.col.bezeichnung")}</th>
              <th className="px-2 py-2 text-right">{t("prio.col.menge")}</th>
              <th className="px-2 py-2">{t("prio.col.kunde")}</th>
              <th className="px-2 py-2">{t("prio.col.termin")}</th>
              <th className="px-2 py-2">{t("prio.col.liste")}</th>
              <th className="px-2 py-2">{t("prio.col.hinweis")}</th>
            </tr>
          </thead>
          <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
            <SortableContext items={anzeige} strategy={verticalListSortingStrategy}>
              <tbody>
                {anzeige.map((k) => {
                  const z = zeilen.get(k);
                  return z ? (
                    <GesamtRow
                      key={k}
                      z={z}
                      platz={platz.get(k) ?? 0}
                      max={reihenfolge.length}
                      onPlatz={(n) => verschiebe(reihenfolge.indexOf(k), n - 1)}
                    />
                  ) : null;
                })}
              </tbody>
            </SortableContext>
          </DndContext>
        </table>
      </div>
      {gefiltert.length > sichtbar && (
        <Button variant="outline" size="sm" onClick={() => setSichtbar((s) => s + SEITE)}>
          {t("prio.gesamt.more", { n: Math.min(SEITE, gefiltert.length - sichtbar) })}
        </Button>
      )}
    </Card>
  );
}

function GesamtRow({ z, platz, max, onPlatz }: {
  z: GesamtZeile;
  platz: number;
  max: number;
  onPlatz: (n: number) => void;
}) {
  const { t } = useTranslation();
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: z.schluessel });
  // Nur während der Eingabe gesetzt; sonst zeigt das Feld den aktuellen Platz.
  const [eingabe, setEingabe] = useState<string | null>(null);

  const uebernehmen = () => {
    const n = Number(eingabe);
    if (Number.isInteger(n) && n >= 1 && n <= max && n !== platz) onPlatz(n);
    setEingabe(null);
  };

  return (
    <tr
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.6 : 1 }}
      className={`border-t hover:bg-muted/30 ${z.gesperrt ? "bg-red-50 dark:bg-red-950/20" : ""}`}
    >
      <td className="px-2 py-1">
        <button type="button" className="cursor-grab text-muted-foreground" aria-label="drag" {...attributes} {...listeners}>
          <GripVertical className="w-4 h-4" />
        </button>
      </td>
      <td className="px-2 py-1">
        <input
          className="w-16 border rounded px-1 py-0.5 text-right bg-background"
          value={eingabe ?? String(platz)}
          onChange={(e) => setEingabe(e.target.value)}
          onBlur={uebernehmen}
          onKeyDown={(e) => { if (e.key === "Enter") (e.target as HTMLInputElement).blur(); }}
        />
      </td>
      <td className="px-2 py-1 font-mono text-xs whitespace-nowrap">
        {z.vorgang_nr} / {z.pos}{z.upos ? `.${z.upos}` : ""}
      </td>
      <td className="px-2 py-1 font-mono text-xs">{z.artikelnr ?? "—"}</td>
      <td className="px-2 py-1">{z.bezeichnung ?? "—"}</td>
      <td className="px-2 py-1 text-right whitespace-nowrap">{zahl(z.menge, 2)} {z.einheit ?? ""}</td>
      <td className="px-2 py-1">{z.kunde ?? "—"}</td>
      <td className="px-2 py-1 whitespace-nowrap">{datum(z.termin)}</td>
      <td className="px-2 py-1 whitespace-nowrap">
        {z.liste ? `${z.liste}${z.listen_rang != null ? ` · ${z.listen_rang}` : ""}` : "—"}
      </td>
      <td className="px-2 py-1 text-xs space-x-1">
        {z.gesperrt && <span className="text-red-600">{t("prio.flag.gesperrt")}</span>}
        {z.manuell && <span className="text-blue-600">{t("prio.flag.manuell")}</span>}
        {z.ohne_plan && <span className="text-amber-600">{t("prio.flag.ohnePlan")}</span>}
        {z.kommentar && <span className="text-muted-foreground">{z.kommentar}</span>}
      </td>
    </tr>
  );
}

// ── Bereiche ────────────────────────────────────────────────────────────────

type BereichsRow = BereichsZeile & Record<string, unknown>;

function BereicheTab() {
  const { t } = useTranslation();
  const { data: bereiche } = useQuery({ queryKey: QK.bereiche, queryFn: prioApi.bereiche });
  const [auswahl, setAuswahl] = useState<string | null>(null);
  const [suche, setSuche] = useState("");
  const aktiv = auswahl ?? bereiche?.find((b) => b.taetigkeiten > 0)?.key ?? null;

  const { data: zeilen, isLoading } = useQuery({
    queryKey: ["prio", "bereich", aktiv],
    queryFn: () => prioApi.bereich(aktiv as string),
    enabled: aktiv != null,
  });

  const q = suche.trim().toLowerCase();
  const rows = (zeilen ?? []).filter((z) =>
    !q || [z.vorgang_nr, z.endartikel, z.artikelnr, z.artikel_bez, z.taetigkeit, z.ressource, z.kunde]
      .some((v) => (v ?? "").toLowerCase().includes(q)),
  ) as BereichsRow[];

  const columns: DataTableColumn<BereichsRow>[] = [
    { key: "prio", header: t("prio.col.rang"), align: "right" },
    { key: "ba", header: t("prio.col.ba"), className: "font-mono text-xs whitespace-nowrap",
      cell: (z) => `${z.vorgang_nr} / ${z.pos}${z.upos ? `.${z.upos}` : ""}` },
    { key: "termin", header: t("prio.col.termin"), className: "whitespace-nowrap", cell: (z) => datum(z.termin) },
    { key: "endartikel", header: t("prio.col.endartikel"),
      cell: (z) => <span title={z.endartikel_bez ?? ""} className="font-mono text-xs">{z.endartikel}</span> },
    { key: "ebene", header: t("prio.col.ebene"), align: "right" },
    { key: "artikelnr", header: t("prio.col.artikel"),
      cell: (z) => (
        <div>
          <div className="font-mono text-xs">{z.artikelnr}</div>
          <div className="text-xs text-muted-foreground">{z.artikel_bez ?? ""}</div>
        </div>
      ) },
    { key: "taetigkeit", header: t("prio.col.taetigkeit"), className: "whitespace-pre-line text-xs" },
    { key: "ressource", header: t("prio.col.ressource"), className: "font-mono text-xs" },
    { key: "menge", header: t("prio.col.menge"), align: "right", cell: (z) => zahl(z.menge, 2) },
    { key: "minuten", header: t("prio.col.minuten"), align: "right", cell: (z) => zahl(z.minuten, 1) },
    { key: "hinweis", header: t("prio.col.hinweis"), className: "text-xs",
      cell: (z) => (
        <>
          {z.gesperrt && <span className="text-red-600 mr-1">{t("prio.flag.gesperrt")}</span>}
          {z.kommentar && <span className="text-muted-foreground">{z.kommentar}</span>}
        </>
      ) },
  ];

  const summeMin = rows.reduce((s, z) => s + Number(z.minuten), 0);

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        {(bereiche ?? []).map((b) => (
          <button
            key={b.key}
            type="button"
            onClick={() => setAuswahl(b.key)}
            className={`rounded-full border px-3 py-1 text-sm transition-colors ${
              b.key === aktiv ? "bg-primary text-primary-foreground border-primary" : "hover:bg-muted"
            }`}
          >
            {b.label} <span className="opacity-70">({b.taetigkeiten})</span>
          </button>
        ))}
      </div>
      {aktiv && (
        <DataTable<BereichsRow>
          title={bereiche?.find((b) => b.key === aktiv)?.label}
          columns={columns}
          rows={rows}
          rowKey={(z) => `${z.vorgang_nr}|${z.pos}|${z.upos}|${z.pfad}`}
          isLoading={isLoading}
          emptyText={t("prio.bereiche.empty")}
          search={{ value: suche, onChange: setSuche, placeholder: t("prio.bereiche.search") }}
          pageSize={100}
          minWidth={1100}
          rowClassName={(z) => (z.gesperrt ? "bg-red-50 dark:bg-red-950/20" : "")}
          actions={
            <div className="flex items-center gap-3">
              <span className="text-xs text-muted-foreground">
                {t("prio.bereiche.summary", { n: rows.length, h: (summeMin / 60).toLocaleString(undefined, { maximumFractionDigits: 1 }) })}
              </span>
              <Button size="sm" variant="outline"
                onClick={() => exportBereich(aktiv).catch((e) => toast.error(String(e)))}>
                <Download className="w-4 h-4 mr-1" />
                {t("prio.bereiche.export")}
              </Button>
            </div>
          }
        />
      )}
    </div>
  );
}

// ── Import ──────────────────────────────────────────────────────────────────

const QUELLEN: ImportQuelle[] = ["auftraege", "ressourcenplan", "artikelstamm"];

function ImportTab() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data: status } = useQuery({ queryKey: QK.status, queryFn: prioApi.status });
  const [hinweise, setHinweise] = useState<string[]>([]);

  const fertig = (r: { zeilen: number; warnungen: string[]; warnungen_anzahl: number }) => {
    toast.success(t("prio.import.done", { zeilen: r.zeilen, warnungen: r.warnungen_anzahl }));
    setHinweise(r.warnungen);
    qc.invalidateQueries({ queryKey: ["prio"] });
  };
  const fehler = (e: unknown) => toast.error(String(e));

  const quelle = useMutation({
    mutationFn: ({ q, file }: { q: ImportQuelle; file: File }) => prioApi.importQuelle(q, file),
    onSuccess: fertig,
    onError: fehler,
  });
  const liste = useMutation({ mutationFn: prioApi.importListe, onSuccess: fertig, onError: fehler });
  const loeschen = useMutation({
    mutationFn: prioApi.deleteListe,
    onSuccess: () => qc.invalidateQueries({ queryKey: ["prio"] }),
    onError: fehler,
  });
  const laeuft = quelle.isPending || liste.isPending;

  return (
    <div className="space-y-4">
      <Card className="p-4 space-y-3">
        <p className="text-xs text-muted-foreground">{t("prio.import.replaceHint")}</p>
        {QUELLEN.map((q) => {
          const s = status?.importe.find((i) => i.quelle === q);
          return (
            <div key={q} className="flex flex-wrap items-center gap-3 border-t pt-3 first:border-t-0 first:pt-0">
              <div className="flex-1 min-w-[240px]">
                <div className="font-medium text-sm">{t(`prio.import.${q}`)}</div>
                <div className="text-xs text-muted-foreground">
                  {s
                    ? t("prio.import.last", { datei: s.dateiname ?? "", zeilen: s.zeilen, datum: new Date(s.importiert_am).toLocaleString() })
                    : t("prio.import.never")}
                </div>
              </div>
              <input
                type="file"
                accept=".txt,.csv"
                disabled={laeuft}
                className="text-sm"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) quelle.mutate({ q, file });
                  e.target.value = "";
                }}
              />
            </div>
          );
        })}
        <div className="flex flex-wrap items-center gap-3 border-t pt-3">
          <div className="flex-1 min-w-[240px] font-medium text-sm">{t("prio.import.liste")}</div>
          <input
            type="file"
            accept=".xlsx,.xlsm"
            disabled={laeuft}
            className="text-sm"
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) liste.mutate(file);
              e.target.value = "";
            }}
          />
        </div>
        {laeuft && <p className="text-xs text-muted-foreground">{t("prio.import.running")}</p>}
        {hinweise.length > 0 && (
          <ul className="text-xs text-amber-700 list-disc pl-5 max-h-40 overflow-auto">
            {hinweise.map((h, i) => <li key={i}>{h}</li>)}
          </ul>
        )}
      </Card>

      <Card className="p-4">
        <h2 className="font-medium text-sm mb-2">{t("prio.listen.heading")}</h2>
        {(status?.listen ?? []).length === 0 ? (
          <p className="text-sm text-muted-foreground">{t("prio.listen.empty")}</p>
        ) : (
          <table className="w-full text-sm">
            <thead className="bg-muted/50 text-left">
              <tr>
                <th className="px-2 py-1">{t("prio.listen.col.name")}</th>
                <th className="px-2 py-1">{t("prio.listen.col.stand")}</th>
                <th className="px-2 py-1 text-right">{t("prio.listen.col.eintraege")}</th>
                <th className="px-2 py-1 text-right">{t("prio.listen.col.mitRang")}</th>
                <th className="px-2 py-1">{t("prio.listen.col.datei")}</th>
                <th className="px-2 py-1" />
              </tr>
            </thead>
            <tbody>
              {status!.listen.map((l) => (
                <tr key={l.id} className="border-t">
                  <td className="px-2 py-1">{l.name}</td>
                  <td className="px-2 py-1">{datum(l.stand)}</td>
                  <td className="px-2 py-1 text-right">{l.eintraege}</td>
                  <td className="px-2 py-1 text-right">{l.mit_rang}</td>
                  <td className="px-2 py-1 text-xs text-muted-foreground">{l.dateiname}</td>
                  <td className="px-2 py-1 text-right">
                    <button className="text-red-600"
                      onClick={() => { if (confirm(t("prio.listen.confirmDelete"))) loeschen.mutate(l.id); }}>
                      {t("common.delete")}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}
