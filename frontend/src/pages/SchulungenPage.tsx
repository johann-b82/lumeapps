import { useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  AlertTriangle,
  FileDown,
  GraduationCap,
  Loader2,
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
  ladeSchulungsprotokoll,
  setzeFrist,
  setzeVerantwortlicher,
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

type KatalogZeile = Schulung;

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
        placeholder="—"
        aria-label={t("schulungen.katalog.verantwortlicher")}
        className="h-7 w-44 rounded-md border bg-background px-2 text-xs disabled:opacity-50
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

/** Schulungen eines Bereichs. */
function BereichGruppe({ bereich, zeilen }: { bereich: string; zeilen: KatalogZeile[] }) {
  const { t } = useTranslation();
  return (
    <Klappbar titel={bereich} anzahl={zeilen.length}>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/30">
            <Th>{t("schulungen.katalog.name")}</Th>
            <Th>{t("schulungen.katalog.turnus")}</Th>
            <Th>{t("schulungen.katalog.verantwortlicher")}</Th>
            <Th rechts>{t("schulungen.katalog.frist")}</Th>
            <Th rechts>{t("schulungen.katalog.teilnahmen")}</Th>
            <Th rechts>{""}</Th>
          </tr>
        </thead>
        <tbody>
          {zeilen.map((s) => (
            <tr
              key={s.id}
              className="border-b border-border/50 transition-colors last:border-0 hover:bg-muted/40"
            >
              <td className="px-4 py-2">{s.name}</td>
              <td className="px-4 py-2 whitespace-nowrap">
                {s.turnus ? (
                  <span className="rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                    {s.turnus}
                  </span>
                ) : (
                  <span className="text-muted-foreground">—</span>
                )}
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
          ))}
        </tbody>
      </table>
    </Klappbar>
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
                  {a.vorgesetzter ?? <span className="text-muted-foreground">—</span>}
                  {a.weitere_vorgesetzte > 0 && (
                    <span className="ml-2 rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                      {t("schulungen.abteilungen.weitere", { count: a.weitere_vorgesetzte })}
                    </span>
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

  const { data: schulungen, isLoading } = useQuery({
    queryKey: hrKpiKeys.schulungen(),
    queryFn: fetchSchulungen,
  });

  const gefiltert = useMemo<KatalogZeile[] | undefined>(() => {
    if (!schulungen) return undefined;
    const q = suche.trim().toLowerCase();
    const zeilen = schulungen as KatalogZeile[];
    if (!q) return zeilen;
    return zeilen.filter(
      (s) =>
        s.name.toLowerCase().includes(q) ||
        s.bereich.toLowerCase().includes(q) ||
        (s.turnus ?? "").toLowerCase().includes(q),
    );
  }, [schulungen, suche]);

  /** Nach Bereich gruppiert; Reihenfolge folgt der Excel (betrieblich zuerst). */
  const gruppen = useMemo<[string, KatalogZeile[]][]>(() => {
    if (!gefiltert) return [];
    const map = new Map<string, KatalogZeile[]>();
    for (const s of gefiltert) {
      const liste = map.get(s.bereich);
      if (liste) liste.push(s);
      else map.set(s.bereich, [s]);
    }
    const rang = (b: string) =>
      b === "betrieblich" ? 0 : b === "Produktion" ? 1 : b === "Verwaltung" ? 2 : 3;
    return [...map.entries()].sort((a, b) => rang(a[0]) - rang(b[0]) || a[0].localeCompare(b[0]));
  }, [gefiltert]);

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

      {/* Handlungsliste zuerst: was ist überfällig oder wird bald fällig. */}
      <OffenePanel />

      {/* Anforderungsmatrix: Pflichtschulungen je Abteilung ankreuzen. */}
      <PflichtMatrixPanel schulungen={schulungen} />

      {/* Einzelzuweisung — für alles, was die Matrix abteilungsweit nicht trifft. */}
      <ZuweisenPanel schulungen={schulungen} />

      {/* Mitarbeiter mit Fälligkeiten; Zeile aufklappen = Einzelübersicht. */}
      <MitarbeiterPanel />

      {/* Abteilungen & Vorgesetzte — abgeleitet aus den Personio-Daten. */}
      <AbteilungenPanel />

      {/* Katalog — nach Bereich gruppiert, Abschnitte einklappbar. */}
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

        <div className="space-y-3">
          {gruppen.map(([bereich, zeilen]) => (
            <BereichGruppe key={bereich} bereich={bereich} zeilen={zeilen} />
          ))}
        </div>
      </section>
    </div>
  );
}
