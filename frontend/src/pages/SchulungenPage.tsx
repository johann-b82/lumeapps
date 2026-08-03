import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle,
  ChevronDown,
  FileDown,
  GraduationCap,
  Loader2,
  Paperclip,
  Upload,
  UserPlus,
  Users,
  X,
} from "lucide-react";
import {
  entferneZuweisung,
  fetchAbteilungen,
  fetchMitarbeiter,
  fetchMitarbeiterSchulungen,
  fetchOffeneSchulungen,
  fetchPflichtMatrix,
  fetchSchulungen,
  fetchZuweisbare,
  entferneUnterlage,
  fetchUnterlagen,
  ladeSchulungsprotokoll,
  ladeUnterlage,
  ladeUnterlageHoch,
  setzeBeschreibung,
  setzeFrist,
  setzeTurnus,
  setzeVerantwortlicher,
  type Unterlage,
  schulungImportCommit,
  schulungImportPreview,
  setzePflicht,
  weiseSchulungZu,
  type PflichtEbene,
  type PflichtMatrix,
  type Schulung,
  type SchulungImportVorschau,
  type SchulungStatus,
} from "@/lib/schulungApi";
import { hrKpiKeys } from "@/lib/queryKeys";
import { abteilungAusgeblendet, vollwort } from "@/lib/abkuerzungen";
import { Klappbar, Th } from "@/components/hr/Klappbar";

/** Eine über Bereiche zusammengefasste Schulung (ein Eintrag je Name). */
type DedupSchulung = Schulung & { bereiche: string[] };

const BEREICH_RANG = (b: string) =>
  b === "betrieblich" ? 0 : b === "Produktion" ? 1 : b === "Verwaltung" ? 2 : 3;

/** Fasst gleichnamige Schulungen (über Bereiche) zu einem Eintrag zusammen.
 *  Turnus/Frist/Verantwortlicher/Beschreibung sind je Name geteilt; die ID des
 *  ersten Vorkommens dient als kanonischer Bezug (Bearbeiten/Zuweisen wirkt je
 *  Name). Teilnahmen werden summiert, Bereiche gesammelt. */
function dedupliziere(schulungen: Schulung[]): DedupSchulung[] {
  const map = new Map<string, DedupSchulung>();
  for (const s of schulungen) {
    const key = s.name.trim().toLowerCase();
    const vorhanden = map.get(key);
    if (vorhanden) {
      vorhanden.teilnahmen += s.teilnahmen;
      if (!vorhanden.bereiche.includes(s.bereich)) vorhanden.bereiche.push(s.bereich);
    } else {
      map.set(key, { ...s, bereiche: [s.bereich] });
    }
  }
  return [...map.values()].sort(
    (a, b) =>
      BEREICH_RANG(a.bereiche[0]) - BEREICH_RANG(b.bereiche[0]) ||
      a.name.localeCompare(b.name),
  );
}

/** Lädt den Schulungsnachweis (Formblatt 68) einer Schulung als PDF. */
function ProtokollKnopf({ schulung }: { schulung: Schulung }) {
  const { t } = useTranslation();
  const laden = useMutation({
    mutationFn: () => ladeSchulungsprotokoll(schulung.id, schulung.name),
    onError: (e: Error) => toast.error(e.message),
  });
  return (
    <button
      type="button"
      onClick={() => laden.mutate()}
      disabled={laden.isPending}
      aria-label={t("schulungen.katalog.protokoll")}
      title={t("schulungen.katalog.protokoll")}
      className="rounded-md p-1 text-muted-foreground transition-colors hover:bg-muted
                 hover:text-foreground disabled:opacity-50 focus-visible:outline-none
                 focus-visible:ring-2 focus-visible:ring-ring"
    >
      {laden.isPending ? (
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      ) : (
        <FileDown className="h-4 w-4" aria-hidden="true" />
      )}
    </button>
  );
}

/** Editierbares Frist-Feld (Tage nach Eintritt/Zuweisung) je Schulung.
 *
 *  Speichert beim Verlassen des Feldes bzw. mit Enter; leer = Frist gelöscht.
 */
function FristFeld({ schulung }: { schulung: Schulung }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [wert, setWert] = useState(
    schulung.frist_tage === null ? "" : String(schulung.frist_tage),
  );

  const speichern = useMutation({
    mutationFn: (tage: number | null) => setzeFrist(schulung.id, tage),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: hrKpiKeys.schulungen() });
      qc.invalidateQueries({ queryKey: hrKpiKeys.schulungOffen() });
    },
    onError: (e: Error) => {
      toast.error(e.message);
      setWert(schulung.frist_tage === null ? "" : String(schulung.frist_tage));
    },
  });

  const abschicken = () => {
    const roh = wert.trim();
    const neu = roh === "" ? null : Math.round(Number(roh));
    if (roh !== "" && (!Number.isFinite(neu) || (neu as number) < 0 || (neu as number) > 3650)) {
      toast.error(t("schulungen.katalog.fristUngueltig"));
      setWert(schulung.frist_tage === null ? "" : String(schulung.frist_tage));
      return;
    }
    if (neu !== schulung.frist_tage) speichern.mutate(neu);
  };

  return (
    <input
      type="text"
      inputMode="numeric"
      value={wert}
      disabled={speichern.isPending}
      onChange={(e) => setWert(e.target.value)}
      onBlur={abschicken}
      onKeyDown={(e) => {
        if (e.key === "Enter") e.currentTarget.blur();
        if (e.key === "Escape")
          setWert(schulung.frist_tage === null ? "" : String(schulung.frist_tage));
      }}
      placeholder="—"
      aria-label={t("schulungen.katalog.frist")}
      className="h-7 w-16 rounded-md border bg-background px-2 text-right text-xs tabular-nums
                 disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2
                 focus-visible:ring-ring"
    />
  );
}

/** Editierbarer Verantwortlicher/Trainer je Schulung — aus Personio wählbar.
 *
 *  Durchsuchbares Dropdown (Freitext für Externe erlaubt). Speichert beim
 *  Verlassen/Enter; leer = Zuordnung gelöscht. Füllt später das Trainer-Feld
 *  im Schulungsnachweis vor.
 */
function VerantwortlicherFeld({ schulung }: { schulung: Schulung }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [wert, setWert] = useState(schulung.verantwortlicher ?? "");

  const { data: personen } = useQuery({
    queryKey: hrKpiKeys.schulungZuweisbar(),
    queryFn: fetchZuweisbare,
  });

  const speichern = useMutation({
    mutationFn: (name: string | null) => setzeVerantwortlicher(schulung.id, name),
    onSuccess: () => qc.invalidateQueries({ queryKey: hrKpiKeys.schulungen() }),
    onError: (e: Error) => {
      toast.error(e.message);
      setWert(schulung.verantwortlicher ?? "");
    },
  });

  const abschicken = () => {
    const neu = wert.trim() || null;
    if (neu !== (schulung.verantwortlicher ?? null)) speichern.mutate(neu);
  };

  const listId = `verantw-${schulung.id}`;
  return (
    <>
      <input
        type="text"
        list={listId}
        value={wert}
        disabled={speichern.isPending}
        onChange={(e) => setWert(e.target.value)}
        onBlur={abschicken}
        onKeyDown={(e) => {
          if (e.key === "Enter") e.currentTarget.blur();
          if (e.key === "Escape") setWert(schulung.verantwortlicher ?? "");
        }}
        placeholder={t("schulungen.katalog.verantwortlicherPlaceholder")}
        title={t("schulungen.katalog.verantwortlicherHinweis")}
        aria-label={t("schulungen.katalog.verantwortlicher")}
        className="h-7 w-52 rounded-md border bg-background px-2 text-xs disabled:opacity-50
                   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
      <datalist id={listId}>
        {(personen ?? []).map((p) => (
          <option key={p.employee_id} value={p.name} />
        ))}
      </datalist>
    </>
  );
}

const TURNUS_PRESETS = [6, 12, 24, 36, 60] as const;

/** Turnus (Wiederholung) einer Schulung setzen — treibt die Fälligkeit. */
function TurnusFeld({ schulung }: { schulung: Schulung }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const speichern = useMutation({
    mutationFn: (monate: number | null) => setzeTurnus(schulung.id, monate),
    onSuccess: () => qc.invalidateQueries({ queryKey: hrKpiKeys.schulungen() }),
    onError: (e: Error) => toast.error(e.message),
  });

  const monate = schulung.turnus_monate;
  const istPreset = monate != null && (TURNUS_PRESETS as readonly number[]).includes(monate);

  return (
    <select
      value={monate == null ? "" : String(monate)}
      disabled={speichern.isPending}
      onChange={(e) => speichern.mutate(e.target.value === "" ? null : Number(e.target.value))}
      aria-label={t("schulungen.katalog.turnus")}
      className="h-7 rounded-md border bg-background px-2 text-xs disabled:opacity-50
                 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <option value="">
        {monate == null ? (schulung.turnus ?? t("schulungen.turnus.beiBedarf")) : t("schulungen.turnus.beiBedarf")}
      </option>
      <option value="6">{t("schulungen.turnus.m6")}</option>
      <option value="12">{t("schulungen.turnus.m12")}</option>
      <option value="24">{t("schulungen.turnus.m24")}</option>
      <option value="36">{t("schulungen.turnus.m36")}</option>
      <option value="60">{t("schulungen.turnus.m60")}</option>
      {monate != null && !istPreset && (
        <option value={String(monate)}>{schulung.turnus ?? `${monate} Mon.`}</option>
      )}
    </select>
  );
}

/** Beschreibung einer Schulung — Freitext, je Name geteilt. */
function BeschreibungFeld({ schulung }: { schulung: Schulung }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [wert, setWert] = useState(schulung.beschreibung ?? "");
  const speichern = useMutation({
    mutationFn: (text: string | null) => setzeBeschreibung(schulung.id, text),
    onSuccess: () => qc.invalidateQueries({ queryKey: hrKpiKeys.schulungen() }),
    onError: (e: Error) => {
      toast.error(e.message);
      setWert(schulung.beschreibung ?? "");
    },
  });
  return (
    <div>
      <label className="text-xs font-medium">{t("schulungen.detail.beschreibung")}</label>
      <textarea
        value={wert}
        onChange={(e) => setWert(e.target.value)}
        onBlur={() => {
          const neu = wert.trim() || null;
          if (neu !== (schulung.beschreibung ?? null)) speichern.mutate(neu);
        }}
        rows={3}
        placeholder={t("schulungen.detail.beschreibungPlaceholder")}
        className="mt-1 w-full rounded-md border bg-background px-2 py-1 text-sm
                   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
    </div>
  );
}

/** Unterlagen einer Schulung — hochladen, herunterladen, entfernen (je Name geteilt). */
function UnterlagenPanel({ schulung }: { schulung: Schulung }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const dateiRef = useRef<HTMLInputElement>(null);
  const { data } = useQuery({
    queryKey: hrKpiKeys.schulungUnterlagen(schulung.id),
    queryFn: () => fetchUnterlagen(schulung.id),
  });
  const auffrischen = () => {
    qc.invalidateQueries({ queryKey: hrKpiKeys.schulungUnterlagen(schulung.id) });
    qc.invalidateQueries({ queryKey: hrKpiKeys.schulungen() });
  };
  const hochladen = useMutation({
    mutationFn: (f: File) => ladeUnterlageHoch(schulung.id, f),
    onSuccess: () => {
      toast.success(t("schulungen.detail.hochgeladen"));
      auffrischen();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const entfernen = useMutation({
    mutationFn: entferneUnterlage,
    onSuccess: () => {
      toast.success(t("schulungen.detail.entfernt"));
      auffrischen();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const laden = useMutation({
    mutationFn: (u: Unterlage) => ladeUnterlage(u.id, u.dateiname),
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div>
      <div className="flex items-center justify-between">
        <label className="text-xs font-medium">{t("schulungen.detail.unterlagen")}</label>
        <input
          ref={dateiRef}
          type="file"
          className="hidden"
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) hochladen.mutate(f);
            e.target.value = "";
          }}
        />
        <button
          type="button"
          onClick={() => dateiRef.current?.click()}
          disabled={hochladen.isPending}
          className="inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs
                     hover:bg-muted disabled:opacity-60 focus-visible:outline-none
                     focus-visible:ring-2 focus-visible:ring-ring"
        >
          {hochladen.isPending ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />
          ) : (
            <Upload className="h-3.5 w-3.5" aria-hidden="true" />
          )}
          {t("schulungen.detail.hochladen")}
        </button>
      </div>
      {!data || data.length === 0 ? (
        <p className="mt-1 text-xs text-muted-foreground">
          {t("schulungen.detail.keineUnterlagen")}
        </p>
      ) : (
        <ul className="mt-1.5 space-y-1">
          {data.map((u) => (
            <li key={u.id} className="flex items-center gap-2 text-sm">
              <button
                type="button"
                onClick={() => laden.mutate(u)}
                className="inline-flex items-center gap-1.5 text-primary hover:underline
                           focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <Paperclip className="h-3.5 w-3.5" aria-hidden="true" />
                {u.dateiname}
              </button>
              <button
                type="button"
                onClick={() => entfernen.mutate(u.id)}
                disabled={entfernen.isPending}
                aria-label={t("schulungen.detail.entfernen")}
                title={t("schulungen.detail.entfernen")}
                className="rounded p-0.5 text-muted-foreground transition-colors
                           hover:bg-destructive/10 hover:text-destructive disabled:opacity-50"
              >
                <X className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Aufklappbares Detail einer Schulung: Beschreibung + Unterlagen. */
function SchulungDetail({ schulung }: { schulung: Schulung }) {
  return (
    <div className="space-y-3 bg-muted/10 px-6 py-3">
      <BeschreibungFeld schulung={schulung} />
      <UnterlagenPanel schulung={schulung} />
    </div>
  );
}

/** Eine Katalogzeile (je Name, über Bereiche zusammengefasst) mit aufklappbarem Detail. */
function KatalogZeileRow({ s }: { s: DedupSchulung }) {
  const { t } = useTranslation();
  const [offen, setOffen] = useState(false);
  return (
    <>
      <tr className="border-b border-border/50 transition-colors hover:bg-muted/40">
        <td className="px-4 py-2">
          <button
            type="button"
            onClick={() => setOffen((v) => !v)}
            aria-expanded={offen}
            aria-label={t("schulungen.detail.aufklappen")}
            className="mr-1.5 inline-flex align-middle text-muted-foreground hover:text-foreground
                       focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <ChevronDown
              className={`h-4 w-4 transition-transform ${offen ? "" : "-rotate-90"}`}
              aria-hidden="true"
            />
          </button>
          {s.name}
          {s.anzahl_unterlagen > 0 && (
            <span className="ml-2 inline-flex items-center gap-1 align-middle text-xs text-muted-foreground">
              <Paperclip className="h-3 w-3" aria-hidden="true" />
              {s.anzahl_unterlagen}
            </span>
          )}
        </td>
        <td className="px-4 py-2 text-xs text-muted-foreground">{s.bereiche.join(", ")}</td>
        <td className="px-4 py-2 whitespace-nowrap">
          <TurnusFeld schulung={s} />
        </td>
        <td className="px-4 py-2">
          <VerantwortlicherFeld schulung={s} />
        </td>
        <td className="px-4 py-2 text-right">
          <FristFeld schulung={s} />
        </td>
        <td className="px-4 py-2 text-right tabular-nums">{s.teilnahmen}</td>
        <td className="px-4 py-2 text-right">
          <ProtokollKnopf schulung={s} />
        </td>
      </tr>
      {offen && (
        <tr className="border-b border-border/50">
          <td colSpan={7} className="p-0">
            <SchulungDetail schulung={s} />
          </td>
        </tr>
      )}
    </>
  );
}

/** Der Schulungskatalog als eine Tabelle — jede Schulung nur einmal. */
function KatalogTabelle({ zeilen }: { zeilen: DedupSchulung[] }) {
  const { t } = useTranslation();
  return (
    <div className="overflow-x-auto rounded-xl border bg-card shadow-sm">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/30">
            <Th>{t("schulungen.katalog.name")}</Th>
            <Th>{t("schulungen.katalog.bereich")}</Th>
            <Th>{t("schulungen.katalog.turnus")}</Th>
            <Th>{t("schulungen.katalog.verantwortlicher")}</Th>
            <Th rechts>{t("schulungen.katalog.frist")}</Th>
            <Th rechts>{t("schulungen.katalog.teilnahmen")}</Th>
            <Th rechts>{""}</Th>
          </tr>
        </thead>
        <tbody>
          {zeilen.map((s) => (
            <KatalogZeileRow key={s.id} s={s} />
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Offene Schulungen: überfällig oder in den nächsten 3 Monaten fällig. */
type OffenFilter = "alle" | "ueberfaellig" | "bald";

function OffenePanel() {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<OffenFilter>("alle");
  const { data, isLoading } = useQuery({
    queryKey: hrKpiKeys.schulungOffen(),
    queryFn: fetchOffeneSchulungen,
  });

  const ueberfaellig = (data ?? []).filter((o) => o.status === "ueberfaellig").length;
  const bald = (data ?? []).length - ueberfaellig;

  const gezeigt = useMemo(
    () => (filter === "alle" ? (data ?? []) : (data ?? []).filter((o) => o.status === filter)),
    [data, filter],
  );

  /** Filter-Schaltflächen: Beschriftung samt Anzahl, aktiver Zustand farbig. */
  const schalter: { wert: OffenFilter; label: string; anzahl: number; aktivStil: string }[] = [
    {
      wert: "alle",
      label: t("schulungen.offen.filter.alle"),
      anzahl: (data ?? []).length,
      aktivStil: "bg-primary text-primary-foreground",
    },
    {
      wert: "ueberfaellig",
      label: t("schulungen.offen.filter.ueberfaellig"),
      anzahl: ueberfaellig,
      aktivStil: "bg-destructive text-white",
    },
    {
      wert: "bald",
      label: t("schulungen.offen.filter.bald"),
      anzahl: bald,
      aktivStil: "bg-amber-500 text-white",
    },
  ];

  if (isLoading) {
    return (
      <div className="mb-6 flex h-24 items-center justify-center">
        <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden="true" />
      </div>
    );
  }
  if (!data || data.length === 0) return null;

  return (
    <section className="mb-6">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-medium">
          <AlertTriangle className="h-4 w-4 text-amber-500" aria-hidden="true" />
          {t("schulungen.offen.title")}
        </h2>
        <div className="flex gap-1 rounded-lg border p-0.5" role="group">
          {schalter.map((s) => (
            <button
              key={s.wert}
              type="button"
              onClick={() => setFilter(s.wert)}
              aria-pressed={filter === s.wert}
              className={`flex items-center gap-1.5 rounded-md px-3 py-1 text-xs transition-colors ${
                filter === s.wert ? s.aktivStil : "text-muted-foreground hover:bg-muted"
              }`}
            >
              {s.label}
              <span
                className={`rounded-full px-1.5 tabular-nums ${
                  filter === s.wert ? "bg-white/20" : "bg-muted"
                }`}
              >
                {s.anzahl}
              </span>
            </button>
          ))}
        </div>
      </div>

      {gezeigt.length === 0 && (
        <p className="rounded-xl border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">
          {t("schulungen.offen.leer")}
        </p>
      )}

      {gezeigt.length > 0 && (
      <div className="max-h-[26rem] overflow-auto rounded-xl border bg-card shadow-sm">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10">
            <tr className="border-b bg-muted/60 backdrop-blur">
              <Th>{t("schulungen.mitarbeiter.name")}</Th>
              <Th>{t("schulungen.abteilungen.abteilung")}</Th>
              <Th>{t("schulungen.katalog.name")}</Th>
              <Th>{t("schulungen.mitarbeiter.faelligAm")}</Th>
              <Th rechts>{t("schulungen.offen.frist")}</Th>
            </tr>
          </thead>
          <tbody>
            {gezeigt.map((o) => (
              <tr
                key={`${o.schluessel}-${o.schulung}`}
                className="border-b border-border/50 transition-colors last:border-0 hover:bg-muted/40"
              >
                <td className="px-4 py-1.5 whitespace-nowrap">
                  {o.personalnummer && (
                    <span className="font-mono text-xs text-muted-foreground">
                      {o.personalnummer}
                    </span>
                  )}{" "}
                  {o.mitarbeiter_name}
                </td>
                <td className="px-4 py-1.5 whitespace-nowrap text-muted-foreground">
                  {o.abteilung_kuerzel ?? o.abteilung ?? "—"}
                </td>
                <td className="px-4 py-1.5">
                  <span className="text-muted-foreground">{o.bereich}</span> · {o.schulung}
                </td>
                <td className="px-4 py-1.5 whitespace-nowrap tabular-nums">
                  {datum(o.faellig_am)}
                </td>
                <td className="px-4 py-1.5 text-right whitespace-nowrap">
                  {o.tage < 0 ? (
                    <span className="rounded-md bg-destructive/15 px-2 py-0.5 text-xs text-destructive">
                      {t("schulungen.offen.seit", { count: Math.abs(o.tage) })}
                    </span>
                  ) : (
                    <span className="rounded-md bg-amber-500/15 px-2 py-0.5 text-xs text-amber-600 dark:text-amber-400">
                      {t("schulungen.offen.in", { count: o.tage })}
                    </span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      )}
    </section>
  );
}

/** Anforderungsmatrix: welche Schulung ist für welche Abteilung Pflicht. */
function PflichtMatrixPanel({ schulungen }: { schulungen: Schulung[] | undefined }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [ebene, setEbene] = useState<PflichtEbene>("kuerzel");

  const { data, isLoading } = useQuery({
    queryKey: hrKpiKeys.schulungPflicht(ebene),
    queryFn: () => fetchPflichtMatrix(ebene),
  });

  const setzen = useMutation({
    mutationFn: setzePflicht,
    // Optimistisch: das Häkchen soll sofort reagieren, nicht erst nach dem Server.
    onMutate: async (eingabe) => {
      const key = hrKpiKeys.schulungPflicht(eingabe.ebene);
      await qc.cancelQueries({ queryKey: key });
      const vorher = qc.getQueryData<PflichtMatrix>(key);
      if (vorher) {
        const marke = `${eingabe.schulung_id}:${eingabe.abteilung}`;
        qc.setQueryData<PflichtMatrix>(key, {
          ...vorher,
          regeln: eingabe.pflicht
            ? [...vorher.regeln, marke]
            : vorher.regeln.filter((r) => r !== marke),
        });
      }
      return { key, vorher };
    },
    onError: (e: Error, _v, ctx) => {
      if (ctx?.vorher) qc.setQueryData(ctx.key, ctx.vorher);
      toast.error(e.message);
    },
  });

  const gesetzt = useMemo(() => new Set(data?.regeln ?? []), [data]);

  const gruppen = useMemo<[string, Schulung[]][]>(() => {
    if (!schulungen) return [];
    const map = new Map<string, Schulung[]>();
    for (const s of schulungen) {
      const l = map.get(s.bereich);
      if (l) l.push(s);
      else map.set(s.bereich, [s]);
    }
    const rang = (b: string) =>
      b === "betrieblich" ? 0 : b === "Produktion" ? 1 : b === "Verwaltung" ? 2 : 3;
    return [...map.entries()].sort((a, b) => rang(a[0]) - rang(b[0]));
  }, [schulungen]);

  const abteilungen = (data?.abteilungen ?? []).filter(
    (a) => !abteilungAusgeblendet(a),
  );

  return (
    <section className="mb-6">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-medium">{t("schulungen.pflicht.title")}</h2>
        <div className="flex gap-1 rounded-lg border p-0.5">
          {(["kuerzel", "personio"] as PflichtEbene[]).map((e) => (
            <button
              key={e}
              type="button"
              onClick={() => setEbene(e)}
              className={`rounded-md px-3 py-1 text-xs transition-colors ${
                ebene === e
                  ? "bg-primary text-primary-foreground"
                  : "text-muted-foreground hover:bg-muted"
              }`}
            >
              {t(`schulungen.pflicht.ebene.${e}`)}
            </button>
          ))}
        </div>
      </div>

      <p className="mb-3 text-xs text-muted-foreground">
        {t(`schulungen.pflicht.hinweis.${ebene}`)}
      </p>

      {isLoading && (
        <div className="flex h-32 items-center justify-center">
          <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden="true" />
        </div>
      )}

      {data && abteilungen.length > 0 && (
        <div className="overflow-x-auto rounded-xl border bg-card shadow-sm">
          <table className="text-sm">
            <thead>
              <tr className="border-b bg-muted/30">
                <th className="sticky left-0 z-10 min-w-[280px] bg-muted/30 px-4 py-2 text-left text-xs font-medium tracking-wide text-muted-foreground uppercase">
                  {t("schulungen.katalog.name")}
                </th>
                {abteilungen.map((a) => (
                  <th
                    key={a}
                    className="px-2 py-2 text-xs font-medium whitespace-nowrap text-muted-foreground"
                    title={vollwort(a)}
                  >
                    {a}
                  </th>
                ))}
              </tr>
            </thead>
            {gruppen.map(([bereich, zeilen]) => (
              <tbody key={bereich}>
                <tr className="border-b bg-muted/50">
                  <td
                    colSpan={abteilungen.length + 1}
                    className="sticky left-0 px-4 py-1.5 text-xs font-medium"
                  >
                    {bereich}
                  </td>
                </tr>
                {zeilen.map((s) => (
                  <tr
                    key={s.id}
                    className="border-b border-border/50 transition-colors last:border-0 hover:bg-muted/30"
                  >
                    <td className="sticky left-0 z-10 max-w-[380px] truncate bg-card px-4 py-1.5">
                      {s.name}
                    </td>
                    {abteilungen.map((a) => {
                      const an = gesetzt.has(`${s.id}:${a}`);
                      return (
                        <td key={a} className="px-2 py-1.5 text-center">
                          <input
                            type="checkbox"
                            checked={an}
                            aria-label={`${s.name} – ${a}`}
                            onChange={() =>
                              setzen.mutate({
                                schulung_id: s.id,
                                ebene,
                                abteilung: a,
                                pflicht: !an,
                              })
                            }
                            className="h-4 w-4 cursor-pointer accent-primary"
                          />
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            ))}
          </table>
        </div>
      )}
    </section>
  );
}

/** Farbige Status-Plakette für eine Fälligkeit. */
function StatusBadge({ status }: { status: SchulungStatus }) {
  const { t } = useTranslation();
  const stil: Record<SchulungStatus, string> = {
    ueberfaellig: "bg-destructive/15 text-destructive",
    bald: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
    ok: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
    ohne_frist: "bg-muted text-muted-foreground",
  };
  return (
    <span className={`rounded-md px-2 py-0.5 text-xs whitespace-nowrap ${stil[status]}`}>
      {t(`schulungen.status.${status}`)}
    </span>
  );
}

function datum(wert: string | null): string {
  if (!wert) return "—";
  const d = new Date(wert);
  return Number.isNaN(d.getTime()) ? wert : d.toLocaleDateString();
}

/** Einzelübersicht: alle Schulungen eines Mitarbeiters. */
function MitarbeiterDetail({ schluessel }: { schluessel: string }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: hrKpiKeys.schulungMitarbeiterDetail(schluessel),
    queryFn: () => fetchMitarbeiterSchulungen(schluessel),
  });

  const entfernen = useMutation({
    mutationFn: entferneZuweisung,
    onSuccess: () => {
      toast.success(t("schulungen.zuweisen.entfernt"));
      qc.invalidateQueries({ queryKey: hrKpiKeys.schulungMitarbeiterDetail(schluessel) });
      qc.invalidateQueries({ queryKey: hrKpiKeys.schulungMitarbeiter() });
      qc.invalidateQueries({ queryKey: hrKpiKeys.schulungen() });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 px-4 py-3 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
      </div>
    );
  }
  if (!data) return null;

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b bg-muted/20">
          <Th>{t("schulungen.katalog.name")}</Th>
          <Th>{t("schulungen.mitarbeiter.aktuell")}</Th>
          <Th>{t("schulungen.mitarbeiter.faelligAm")}</Th>
          <Th rechts>{t("schulungen.mitarbeiter.status")}</Th>
          <Th rechts>{""}</Th>
        </tr>
      </thead>
      <tbody>
        {data.map((s) => (
          <tr
            key={s.schulung_id}
            className="border-b border-border/40 transition-colors last:border-0 hover:bg-muted/30"
          >
            <td className="px-4 py-1.5">
              <span className="text-muted-foreground">{s.bereich}</span> · {s.name}
            </td>
            <td className="px-4 py-1.5 whitespace-nowrap tabular-nums">
              {datum(s.aktuell_datum)}
            </td>
            <td className="px-4 py-1.5 whitespace-nowrap tabular-nums">
              {datum(s.naechste_faellig_am)}
            </td>
            <td className="px-4 py-1.5 text-right">
              <StatusBadge status={s.status} />
            </td>
            <td className="px-4 py-1.5 text-right">
              {/* Nur ohne Nachweis: mit Datum ist die Zeile ein Beleg, kein Plan. */}
              {s.initial_datum === null && s.aktuell_datum === null && (
                <button
                  type="button"
                  onClick={() => entfernen.mutate(s.teilnahme_id)}
                  disabled={entfernen.isPending}
                  aria-label={t("schulungen.zuweisen.entfernen")}
                  title={t("schulungen.zuweisen.entfernen")}
                  className="rounded-md p-1 text-muted-foreground transition-colors
                             hover:bg-destructive/10 hover:text-destructive disabled:opacity-50
                             focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  <X className="h-3.5 w-3.5" aria-hidden="true" />
                </button>
              )}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

/** Einzelzuweisung: eine bestimmte Schulung an eine bestimmte Person.
 *
 *  Ergänzt die Anforderungsmatrix, die nur abteilungsweit wirkt — für alles,
 *  was nur eine einzelne Person betrifft (Sonderqualifikation, Vertretung).
 */
function ZuweisenPanel({ schulungen }: { schulungen: Schulung[] | undefined }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [mitarbeiter, setMitarbeiter] = useState("");
  const [schulung, setSchulung] = useState("");

  const { data: personen } = useQuery({
    queryKey: hrKpiKeys.schulungZuweisbar(),
    queryFn: fetchZuweisbare,
  });

  const zuweisen = useMutation({
    mutationFn: weiseSchulungZu,
    onSuccess: (z) => {
      toast.success(t("schulungen.zuweisen.erfolg", { name: z.name, schulung: z.schulung }));
      setSchulung("");
      qc.invalidateQueries({ queryKey: hrKpiKeys.schulungMitarbeiter() });
      qc.invalidateQueries({ queryKey: hrKpiKeys.schulungen() });
      qc.invalidateQueries({ queryKey: hrKpiKeys.schulungOffen() });
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const bereit = mitarbeiter !== "" && schulung !== "";
  const auswahlStil =
    "h-9 min-w-0 flex-1 rounded-md border bg-background px-2 text-sm " +
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

  return (
    <section className="mb-6">
      <Klappbar
        titel={t("schulungen.zuweisen.title")}
        icon={<UserPlus className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}
        offenStart={false}
      >
        <div className="space-y-3 px-4 py-3">
          <p className="text-xs text-muted-foreground">{t("schulungen.zuweisen.hinweis")}</p>
          <div className="flex flex-wrap items-center gap-2">
            <select
              value={mitarbeiter}
              onChange={(e) => setMitarbeiter(e.target.value)}
              aria-label={t("schulungen.mitarbeiter.name")}
              className={auswahlStil}
            >
              <option value="">{t("schulungen.zuweisen.mitarbeiterWaehlen")}</option>
              {(personen ?? []).map((p) => (
                <option key={p.employee_id} value={String(p.employee_id)}>
                  {p.name}
                  {p.abteilung ? ` · ${p.abteilung}` : ""}
                </option>
              ))}
            </select>

            <select
              value={schulung}
              onChange={(e) => setSchulung(e.target.value)}
              aria-label={t("schulungen.katalog.name")}
              className={auswahlStil}
            >
              <option value="">{t("schulungen.zuweisen.schulungWaehlen")}</option>
              {(schulungen ?? []).map((s) => (
                <option key={s.id} value={String(s.id)}>
                  {s.bereich} · {s.name}
                </option>
              ))}
            </select>

            <button
              type="button"
              disabled={!bereit || zuweisen.isPending}
              onClick={() =>
                zuweisen.mutate({
                  employee_id: Number(mitarbeiter),
                  schulung_id: Number(schulung),
                })
              }
              className="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-4 text-sm
                         text-primary-foreground disabled:opacity-50
                         focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              {zuweisen.isPending && (
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
              )}
              {t("schulungen.zuweisen.aktion")}
            </button>
          </div>
        </div>
      </Klappbar>
    </section>
  );
}

/** Mitarbeiterübersicht; Zeile aufklappen zeigt die Einzelübersicht. */
function MitarbeiterPanel() {
  const { t } = useTranslation();
  const [offenFuer, setOffenFuer] = useState<string | null>(null);
  const { data } = useQuery({
    queryKey: hrKpiKeys.schulungMitarbeiter(),
    queryFn: fetchMitarbeiter,
  });
  if (!data || data.length === 0) return null;

  const ueberfaellig = data.filter((m) => m.ueberfaellig > 0).length;

  return (
    <section className="mb-6">
      <Klappbar
        titel={t("schulungen.mitarbeiter.title")}
        anzahl={data.length}
        icon={<Users className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}
        offenStart={false}
      >
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/30">
              <Th>{t("schulungen.mitarbeiter.name")}</Th>
              <Th>{t("schulungen.abteilungen.abteilung")}</Th>
              <Th rechts>{t("schulungen.mitarbeiter.anzahl")}</Th>
              <Th rechts>{t("schulungen.status.ueberfaellig")}</Th>
              <Th rechts>{t("schulungen.status.bald")}</Th>
            </tr>
          </thead>
          <tbody>
            {data.map((m) => {
              const offen = offenFuer === m.schluessel;
              return [
                <tr
                  key={m.schluessel}
                  onClick={() => setOffenFuer(offen ? null : m.schluessel)}
                  className="cursor-pointer border-b border-border/50 transition-colors hover:bg-muted/40"
                >
                  <td className="px-4 py-2">
                    <span className="font-mono text-xs text-muted-foreground">
                      {m.personalnummer ?? "—"}
                    </span>{" "}
                    {m.name}
                  </td>
                  <td className="px-4 py-2 text-muted-foreground">{m.abteilung ?? "—"}</td>
                  <td className="px-4 py-2 text-right tabular-nums">{m.schulungen}</td>
                  <td className="px-4 py-2 text-right tabular-nums">
                    {m.ueberfaellig > 0 ? (
                      <span className="rounded-md bg-destructive/15 px-2 py-0.5 text-destructive">
                        {m.ueberfaellig}
                      </span>
                    ) : (
                      <span className="text-muted-foreground">0</span>
                    )}
                  </td>
                  <td className="px-4 py-2 text-right tabular-nums text-muted-foreground">
                    {m.bald_faellig}
                  </td>
                </tr>,
                offen ? (
                  <tr key={`${m.schluessel}-detail`} className="border-b bg-muted/10">
                    <td colSpan={5} className="p-0">
                      <MitarbeiterDetail schluessel={m.schluessel} />
                    </td>
                  </tr>
                ) : null,
              ];
            })}
          </tbody>
        </table>
      </Klappbar>
      <p className="mt-1.5 text-xs text-muted-foreground">
        {t("schulungen.mitarbeiter.hinweis", { count: ueberfaellig })}
      </p>
    </section>
  );
}

/** Abteilungen mit ihrem Hauptverantwortlichen (aus Personio abgeleitet). */
function AbteilungenPanel() {
  const { t } = useTranslation();
  const { data } = useQuery({
    queryKey: hrKpiKeys.schulungAbteilungen(),
    queryFn: fetchAbteilungen,
  });
  if (!data || data.length === 0) return null;

  return (
    <section className="mb-6">
      <Klappbar
        titel={t("schulungen.abteilungen.title")}
        anzahl={data.length}
        icon={<Users className="h-4 w-4 text-muted-foreground" aria-hidden="true" />}
        offenStart={false}
      >
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b bg-muted/30">
              <Th>{t("schulungen.abteilungen.abteilung")}</Th>
              <Th>{t("schulungen.abteilungen.vorgesetzter")}</Th>
              <Th rechts>{t("schulungen.abteilungen.mitarbeiter")}</Th>
            </tr>
          </thead>
          <tbody>
            {data.map((a) => (
              <tr
                key={a.abteilung}
                className="border-b border-border/50 transition-colors last:border-0 hover:bg-muted/40"
              >
                <td className="px-4 py-2">{a.abteilung}</td>
                <td className="px-4 py-2">
                  {a.vorgesetzte.length > 0 ? (
                    a.vorgesetzte.join(", ")
                  ) : (
                    <span className="text-muted-foreground">—</span>
                  )}
                </td>
                <td className="px-4 py-2 text-right tabular-nums">{a.mitarbeiter}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Klappbar>
      <p className="mt-1.5 text-xs text-muted-foreground">
        {t("schulungen.abteilungen.hinweis")}
      </p>
    </section>
  );
}

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

  const [suche, setSuche] = useState("");
  const [tab, setTab] = useState<"bearbeiten" | "zuweisen" | "stand">("bearbeiten");

  const { data: schulungen, isLoading } = useQuery({
    queryKey: hrKpiKeys.schulungen(),
    queryFn: fetchSchulungen,
  });

  /** Jede Schulung nur einmal (über Bereiche zusammengefasst). */
  const entdoppelt = useMemo<DedupSchulung[] | undefined>(
    () => (schulungen ? dedupliziere(schulungen) : undefined),
    [schulungen],
  );

  const gefiltert = useMemo<DedupSchulung[] | undefined>(() => {
    if (!entdoppelt) return undefined;
    const q = suche.trim().toLowerCase();
    if (!q) return entdoppelt;
    return entdoppelt.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.bereiche.some((b) => b.toLowerCase().includes(q)) ||
        (s.turnus ?? "").toLowerCase().includes(q),
    );
  }, [entdoppelt, suche]);

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

  const tabs: { key: typeof tab; label: string }[] = [
    { key: "bearbeiten", label: t("schulungen.tabs.bearbeiten") },
    { key: "zuweisen", label: t("schulungen.tabs.zuweisen") },
    { key: "stand", label: t("schulungen.tabs.stand") },
  ];

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-8">
      <h1 className="mb-4 flex items-center gap-2 text-lg font-semibold">
        <GraduationCap className="h-5 w-5" aria-hidden="true" />
        {t("schulungen.title")}
      </h1>

      <div className="mb-6 flex gap-1 border-b" role="tablist">
        {tabs.map(({ key, label }) => (
          <button
            key={key}
            type="button"
            role="tab"
            aria-selected={tab === key}
            onClick={() => setTab(key)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium transition-colors
                        focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${
                          tab === key
                            ? "border-primary text-foreground"
                            : "border-transparent text-muted-foreground hover:text-foreground"
                        }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "bearbeiten" && (
        <>
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

          <section>
            <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
              <h2 className="text-sm font-medium">{t("schulungen.katalog.title")}</h2>
              <input
                type="search"
                value={suche}
                onChange={(e) => setSuche(e.target.value)}
                placeholder={t("schulungen.katalog.suche")}
                className="h-8 w-72 rounded-md border bg-background px-3 text-sm
                           focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              />
            </div>

            {isLoading && (
              <div className="flex h-32 items-center justify-center">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" aria-hidden="true" />
              </div>
            )}

            {gefiltert && gefiltert.length === 0 && (
              <p className="rounded-xl border border-dashed px-4 py-8 text-center text-sm text-muted-foreground">
                {suche ? t("schulungen.katalog.keinTreffer") : t("schulungen.katalog.leer")}
              </p>
            )}

            {gefiltert && gefiltert.length > 0 && <KatalogTabelle zeilen={gefiltert} />}
          </section>
        </>
      )}

      {tab === "zuweisen" && (
        <>
          <PflichtMatrixPanel schulungen={entdoppelt} />
          <ZuweisenPanel schulungen={entdoppelt} />
        </>
      )}

      {tab === "stand" && (
        <>
          <OffenePanel />
          <MitarbeiterPanel />
          <AbteilungenPanel />
        </>
      )}
    </div>
  );
}
