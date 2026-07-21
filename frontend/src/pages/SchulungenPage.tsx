import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { AlertTriangle, GraduationCap, Loader2, Upload } from "lucide-react";
import {
  fetchSchulungen,
  schulungImportCommit,
  schulungImportPreview,
  type SchulungImportVorschau,
} from "@/lib/schulungApi";
import { hrKpiKeys } from "@/lib/queryKeys";

/** Kennzahl-Kachel der Vorschau. */
function Kennzahl({ label, wert }: { label: string; wert: string | number }) {
  return (
    <div className="rounded-lg border bg-card px-3 py-2">
      <div className="text-lg font-semibold">{wert}</div>
      <div className="text-xs text-muted-foreground">{label}</div>
    </div>
  );
}

function Vorschau({
  v,
  onCommit,
  committing,
  committed,
}: {
  v: SchulungImportVorschau;
  onCommit: () => void;
  committing: boolean;
  committed: boolean;
}) {
  const { t } = useTranslation();
  return (
    <div className="mt-4 space-y-4 rounded-lg border bg-muted/30 p-4">
      <div className="text-sm font-medium">{v.dateiname}</div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <Kennzahl label={t("schulungen.import.schulungen")} wert={v.schulungen_gesamt} />
        <Kennzahl label={t("schulungen.import.neu")} wert={v.schulungen_neu} />
        <Kennzahl label={t("schulungen.import.teilnahmen")} wert={v.teilnahmen_gesamt} />
        <Kennzahl
          label={t("schulungen.import.zugeordnet")}
          wert={`${v.teilnahmen_zugeordnet}/${v.teilnahmen_gesamt}`}
        />
      </div>

      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
        {Object.entries(v.bereiche).map(([bereich, anzahl]) => (
          <span key={bereich} className="rounded-full border px-2 py-0.5">
            {bereich}: {anzahl}
          </span>
        ))}
      </div>

      {v.nicht_zugeordnet.length > 0 && (
        <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3">
          <div className="flex items-center gap-2 text-sm font-medium">
            <AlertTriangle className="h-4 w-4" aria-hidden="true" />
            {t("schulungen.import.nichtZugeordnet", { count: v.nicht_zugeordnet.length })}
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            {t("schulungen.import.nichtZugeordnetHinweis")}
          </p>
          <ul className="mt-2 space-y-0.5 text-xs">
            {v.nicht_zugeordnet.map((n) => (
              <li key={n.personalnummer}>
                <span className="font-mono">{n.personalnummer}</span>{" "}
                {n.mitarbeiter_name ?? "—"} ({n.anzahl_teilnahmen})
              </li>
            ))}
          </ul>
        </div>
      )}

      {v.warnungen.length > 0 && (
        <ul className="space-y-0.5 text-xs text-destructive">
          {v.warnungen.map((w) => (
            <li key={w}>{w}</li>
          ))}
        </ul>
      )}

      {!committed && (
        <button
          type="button"
          onClick={onCommit}
          disabled={committing}
          className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-1.5 text-sm
                     text-primary-foreground disabled:opacity-60
                     focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {committing && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
          {t("schulungen.import.uebernehmen")}
        </button>
      )}
    </div>
  );
}

export function SchulungenPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const dateiRef = useRef<HTMLInputElement>(null);
  const [datei, setDatei] = useState<File | null>(null);
  const [vorschau, setVorschau] = useState<SchulungImportVorschau | null>(null);
  const [committed, setCommitted] = useState(false);

  const { data: schulungen, isLoading } = useQuery({
    queryKey: hrKpiKeys.schulungen(),
    queryFn: fetchSchulungen,
  });

  const preview = useMutation({
    mutationFn: (f: File) => schulungImportPreview(f),
    onSuccess: (v) => {
      setVorschau(v);
      setCommitted(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const commit = useMutation({
    mutationFn: (f: File) => schulungImportCommit(f),
    onSuccess: (v) => {
      setVorschau(v);
      setCommitted(true);
      toast.success(t("schulungen.import.erfolg", { count: v.teilnahmen_gesamt }));
      qc.invalidateQueries({ queryKey: hrKpiKeys.schulungen() });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  function waehle(f: File | null) {
    setDatei(f);
    setVorschau(null);
    setCommitted(false);
    if (f) preview.mutate(f);
  }

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8">
      <h1 className="mb-6 flex items-center gap-2 text-lg font-semibold">
        <GraduationCap className="h-5 w-5" aria-hidden="true" />
        {t("schulungen.title")}
      </h1>

      {/* Import */}
      <section className="mb-8">
        <h2 className="mb-2 text-sm font-medium">{t("schulungen.import.title")}</h2>
        <p className="mb-3 text-xs text-muted-foreground">
          {t("schulungen.import.hinweis")}
        </p>

        <input
          ref={dateiRef}
          type="file"
          accept=".xlsx,.xlsm"
          className="hidden"
          onChange={(e) => waehle(e.target.files?.[0] ?? null)}
        />
        <button
          type="button"
          onClick={() => dateiRef.current?.click()}
          className="inline-flex items-center gap-2 rounded-md border px-3 py-1.5 text-sm
                     hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Upload className="h-4 w-4" aria-hidden="true" />
          {datei ? datei.name : t("schulungen.import.dateiWaehlen")}
        </button>

        {preview.isPending && (
          <div className="mt-3 flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
            {t("schulungen.import.analysiere")}
          </div>
        )}

        {vorschau && datei && (
          <Vorschau
            v={vorschau}
            committing={commit.isPending}
            committed={committed}
            onCommit={() => commit.mutate(datei)}
          />
        )}
      </section>

      {/* Katalog */}
      <section>
        <h2 className="mb-3 text-sm font-medium">
          {t("schulungen.katalog.title")}
          {schulungen && schulungen.length > 0 && (
            <span className="ml-2 text-xs font-normal text-muted-foreground">
              {schulungen.length}
            </span>
          )}
        </h2>

        {isLoading && (
          <div className="flex h-32 items-center justify-center">
            <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden="true" />
          </div>
        )}

        {schulungen && schulungen.length === 0 && (
          <p className="text-sm text-muted-foreground">{t("schulungen.katalog.leer")}</p>
        )}

        {schulungen && schulungen.length > 0 && (
          <div className="overflow-x-auto rounded-lg border">
            <table className="w-full text-sm">
              <thead className="border-b bg-muted/40 text-left">
                <tr>
                  <th className="px-3 py-2">{t("schulungen.katalog.bereich")}</th>
                  <th className="px-3 py-2">{t("schulungen.katalog.name")}</th>
                  <th className="px-3 py-2">{t("schulungen.katalog.turnus")}</th>
                  <th className="px-3 py-2 text-right">
                    {t("schulungen.katalog.teilnahmen")}
                  </th>
                </tr>
              </thead>
              <tbody>
                {schulungen.map((s) => (
                  <tr key={s.id} className="border-b last:border-0">
                    <td className="px-3 py-1.5 whitespace-nowrap text-muted-foreground">
                      {s.bereich}
                    </td>
                    <td className="px-3 py-1.5">{s.name}</td>
                    <td className="px-3 py-1.5 whitespace-nowrap text-muted-foreground">
                      {s.turnus ?? "—"}
                    </td>
                    <td className="px-3 py-1.5 text-right tabular-nums">{s.teilnahmen}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
