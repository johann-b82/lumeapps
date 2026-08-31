import { useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { FileText, Sparkles, Loader2, Trash2, Download, Building2, RefreshCw, Blocks } from "lucide-react";

import {
  ZEUGNIS_ABSCHNITTE,
  ZEUGNIS_DIMENSIONEN,
  baukastenAbschnitt,
  baukastenZeugnis,
  createVorlage,
  createZeugnis,
  deleteVorlage,
  deleteZeugnis,
  downloadDocx,
  downloadPdf,
  fetchAussteller,
  fetchPersonen,
  fetchVorlagen,
  fetchZeugnis,
  fetchZeugnisse,
  generateAbschnitt,
  generateZeugnis,
  saveAussteller,
  updateZeugnis,
} from "@/lib/zeugnisApi";
import type { Aussteller, Person, Vorlage, ZeugnisArt, ZeugnisDetail } from "@/lib/zeugnisApi";

const feld =
  "h-8 rounded-md border border-input bg-background px-2 text-sm " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
const primary =
  "inline-flex h-8 items-center gap-2 rounded-md bg-primary px-3 text-xs " +
  "text-primary-foreground disabled:opacity-50 focus-visible:outline-none " +
  "focus-visible:ring-2 focus-visible:ring-ring";
const ghost =
  "inline-flex h-8 items-center gap-2 rounded-md border border-input px-3 text-xs " +
  "hover:bg-muted disabled:opacity-50 focus-visible:outline-none " +
  "focus-visible:ring-2 focus-visible:ring-ring";

const ARTEN: ZeugnisArt[] = [
  "qualifiziert",
  "einfach",
  "zwischenzeugnis",
  "ausbildungszeugnis",
  "praktikumszeugnis",
];
const zKeys = {
  liste: () => ["hr", "zeugnisse"] as const,
  personen: () => ["hr", "zeugnisse", "personen"] as const,
  detail: (id: number) => ["hr", "zeugnisse", id] as const,
  aussteller: () => ["hr", "zeugnisse", "aussteller"] as const,
};

export function ZeugnissePage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [auswahl, setAuswahl] = useState<number | null>(null);

  const { data: liste } = useQuery({ queryKey: zKeys.liste(), queryFn: fetchZeugnisse });
  const { data: personen } = useQuery({ queryKey: zKeys.personen(), queryFn: fetchPersonen });

  const [neuePerson, setNeuePerson] = useState("");
  const [neueArt, setNeueArt] = useState<ZeugnisArt>("qualifiziert");
  const anlegen = useMutation({
    mutationFn: () => createZeugnis(Number(neuePerson), neueArt),
    onSuccess: (z) => {
      qc.invalidateQueries({ queryKey: zKeys.liste() });
      setNeuePerson("");
      setAuswahl(z.id);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="max-w-7xl mx-auto px-6 pt-4 pb-10">
      <div className="mb-4 flex items-center gap-2">
        <FileText className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
        <h1 className="text-lg font-semibold">{t("zeugnisse.title")}</h1>
      </div>
      <p className="mb-4 text-xs text-muted-foreground">{t("zeugnisse.hinweis")}</p>

      <AusstellerCard />

      <div className="grid gap-6 lg:grid-cols-[320px_1fr]">
        {/* Liste + Anlegen */}
        <div className="space-y-3">
          <div className="rounded-lg border p-3">
            <div className="mb-2 text-xs font-medium">{t("zeugnisse.neu")}</div>
            <select
              value={neuePerson}
              onChange={(e) => setNeuePerson(e.target.value)}
              className={`${feld} w-full`}
            >
              <option value="">{t("zeugnisse.personWaehlen")}</option>
              {(personen ?? []).map((p: Person) => (
                <option key={p.employee_id} value={p.employee_id}>
                  {p.name}
                  {p.status === "inactive" ? " · ausgeschieden" : ""}
                  {p.status === "extern" ? " · extern" : ""}
                </option>
              ))}
            </select>
            <div className="mt-2 flex items-center gap-2">
              <select
                value={neueArt}
                onChange={(e) => setNeueArt(e.target.value as ZeugnisArt)}
                className={`${feld} flex-1`}
              >
                {ARTEN.map((a) => (
                  <option key={a} value={a}>
                    {t(`zeugnisse.art.${a}`)}
                  </option>
                ))}
              </select>
              <button
                type="button"
                className={primary}
                disabled={!neuePerson || anlegen.isPending}
                onClick={() => anlegen.mutate()}
              >
                {anlegen.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                {t("zeugnisse.anlegen")}
              </button>
            </div>
          </div>

          <div className="rounded-lg border">
            {!liste || liste.length === 0 ? (
              <p className="p-3 text-sm text-muted-foreground">{t("zeugnisse.leer")}</p>
            ) : (
              <ul className="divide-y">
                {liste.map((z) => (
                  <li key={z.id}>
                    <button
                      type="button"
                      onClick={() => setAuswahl(z.id)}
                      className={`flex w-full items-center justify-between px-3 py-2 text-left text-sm
                                  hover:bg-muted ${auswahl === z.id ? "bg-muted" : ""}`}
                    >
                      <span className="truncate">
                        {z.name}
                        <span className="ml-1 text-xs text-muted-foreground">
                          · {t(`zeugnisse.art.${z.art}`)}
                        </span>
                      </span>
                      <span className="ml-2 shrink-0 text-xs text-muted-foreground">
                        {z.schlussnote != null ? z.schlussnote.toFixed(1) : "—"}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </div>

        {/* Editor */}
        <div>
          {auswahl == null ? (
            <div className="rounded-lg border p-6 text-sm text-muted-foreground">
              {t("zeugnisse.keinsGewaehlt")}
            </div>
          ) : (
            <ZeugnisEditor id={auswahl} onDeleted={() => setAuswahl(null)} />
          )}
        </div>
      </div>
    </div>
  );
}

/** Ausstellerprofil (Firma, Standort, Unterzeichner) — einmal pflegen. */
function AusstellerCard() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const [offen, setOffen] = useState(false);
  const { data } = useQuery({ queryKey: zKeys.aussteller(), queryFn: fetchAussteller });
  const { data: personen } = useQuery({ queryKey: zKeys.personen(), queryFn: fetchPersonen });
  const [form, setForm] = useState<Aussteller>({
    firma: "",
    standort: "",
    unterzeichner1_name: "",
    unterzeichner1_titel: "",
    unterzeichner2_name: "",
    unterzeichner2_titel: "",
  });
  useEffect(() => {
    if (data) setForm({ ...data });
  }, [data]);

  const speichern = useMutation({
    mutationFn: () => saveAussteller(form),
    onSuccess: () => {
      toast.success(t("zeugnisse.gespeichert"));
      qc.invalidateQueries({ queryKey: zKeys.aussteller() });
      setOffen(false);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const fehlt = !data || !data.firma;
  return (
    <div className={`mb-4 rounded-lg border p-3 ${fehlt ? "border-amber-500/60" : ""}`}>
      <button
        type="button"
        onClick={() => setOffen((o) => !o)}
        className="flex w-full items-center gap-2 text-sm font-medium"
      >
        <Building2 className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        {t("zeugnisse.aussteller")}
        <span className="ml-2 text-xs text-muted-foreground">
          {fehlt ? t("zeugnisse.ausstellerFehlt") : data?.firma}
        </span>
      </button>
      {offen && (
        <div className="mt-3 grid gap-2 sm:grid-cols-2">
          <input
            className={feld}
            placeholder={t("zeugnisse.firma")}
            value={form.firma}
            onChange={(e) => setForm({ ...form, firma: e.target.value })}
          />
          <input
            className={feld}
            placeholder={t("zeugnisse.standort")}
            value={form.standort ?? ""}
            onChange={(e) => setForm({ ...form, standort: e.target.value })}
          />
          <input
            className={feld}
            placeholder={t("zeugnisse.unterzeichner1Name")}
            value={form.unterzeichner1_name ?? ""}
            onChange={(e) => setForm({ ...form, unterzeichner1_name: e.target.value })}
          />
          <input
            className={feld}
            placeholder={t("zeugnisse.unterzeichner1Titel")}
            value={form.unterzeichner1_titel ?? ""}
            onChange={(e) => setForm({ ...form, unterzeichner1_titel: e.target.value })}
          />
          <div className="sm:col-span-2">
            <label className="text-xs text-muted-foreground">
              {t("zeugnisse.hrManager")}
            </label>
            <select
              className={`${feld} mt-1 w-full`}
              value={
                (personen ?? []).find((p) => p.name === form.unterzeichner2_name)
                  ?.employee_id ?? ""
              }
              onChange={(e) => {
                const p = (personen ?? []).find(
                  (x) => String(x.employee_id) === e.target.value,
                );
                setForm({
                  ...form,
                  unterzeichner2_name: p ? p.name : "",
                  unterzeichner2_titel: p ? p.position ?? "" : "",
                });
              }}
            >
              <option value="">{t("zeugnisse.personWaehlen")}</option>
              {(personen ?? []).map((p: Person) => (
                <option key={p.employee_id} value={p.employee_id}>
                  {p.name}
                  {p.position ? ` – ${p.position}` : ""}
                </option>
              ))}
            </select>
            {form.unterzeichner2_name && (
              <p className="mt-1 text-[0.7rem] text-muted-foreground">
                {form.unterzeichner2_name}
                {form.unterzeichner2_titel ? ` – ${form.unterzeichner2_titel}` : ""}
              </p>
            )}
          </div>
          <div className="sm:col-span-2">
            <button
              type="button"
              className={primary}
              disabled={!form.firma.trim() || speichern.isPending}
              onClick={() => speichern.mutate()}
            >
              {speichern.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {t("zeugnisse.speichern")}
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

/** Bewertungs-Vorlagen: gespeicherte Noten-Profile anwenden / aktuelles sichern. */
function VorlagenLeiste({
  noten,
  onApply,
}: {
  noten: Record<string, number>;
  onApply: (noten: Record<string, number>) => void;
}) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const vKey = ["hr", "zeugnisse", "vorlagen"] as const;
  const { data: vorlagen } = useQuery({ queryKey: vKey, queryFn: fetchVorlagen });
  const speichern = useMutation({
    mutationFn: (name: string) => createVorlage(name, noten),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: vKey });
      toast.success(t("zeugnisse.vorlageGespeichert"));
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const loeschen = useMutation({
    mutationFn: (vid: number) => deleteVorlage(vid),
    onSuccess: () => qc.invalidateQueries({ queryKey: vKey }),
    onError: (e: Error) => toast.error(e.message),
  });
  return (
    <div className="flex flex-wrap items-center gap-1">
      {(vorlagen ?? []).map((v: Vorlage) => (
        <span key={v.id} className="inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-xs">
          <button type="button" className="hover:underline" title={t("zeugnisse.vorlageAnwenden")} onClick={() => onApply(v.noten)}>
            {v.name}
          </button>
          <button
            type="button"
            className="text-muted-foreground hover:text-destructive"
            title={t("zeugnisse.vorlageEntfernen")}
            onClick={() => {
              if (confirm(t("zeugnisse.vorlageLoeschenBestaetigen", { name: v.name }))) loeschen.mutate(v.id);
            }}
          >
            ×
          </button>
        </span>
      ))}
      <button
        type="button"
        className={`${ghost} h-7`}
        disabled={Object.keys(noten).length === 0 || speichern.isPending}
        onClick={() => {
          const name = window.prompt(t("zeugnisse.vorlageName"));
          if (name && name.trim()) speichern.mutate(name.trim());
        }}
      >
        {t("zeugnisse.vorlageSpeichern")}
      </button>
    </div>
  );
}

function ZeugnisEditor({ id, onDeleted }: { id: number; onDeleted: () => void }) {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data: z } = useQuery({ queryKey: zKeys.detail(id), queryFn: () => fetchZeugnis(id) });

  const [form, setForm] = useState<ZeugnisDetail | null>(null);
  useEffect(() => {
    if (z) setForm(z);
  }, [z]);

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: zKeys.liste() });
    qc.invalidateQueries({ queryKey: zKeys.detail(id) });
  };

  const speichern = useMutation({
    mutationFn: (patch: Partial<ZeugnisDetail>) => updateZeugnis(id, patch),
    onSuccess: (d) => {
      setForm(d);
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const generieren = useMutation({
    mutationFn: async () => {
      // Erst die Eingaben (Noten + Freitexte) sichern, dann generieren.
      if (!form) return null;
      await updateZeugnis(id, {
        geschlecht: form.geschlecht,
        taetigkeit: form.taetigkeit,
        abteilung: form.abteilung,
        eintritt: form.eintritt,
        austritt: form.austritt,
        art: form.art,
        fuehrungskraft: form.fuehrungskraft,
        taetigkeit_stichpunkte: form.taetigkeit_stichpunkte,
        besondere_kompetenzen: form.besondere_kompetenzen,
        besondere_erfolge: form.besondere_erfolge,
        bewertungen: form.bewertungen,
      });
      return generateZeugnis(id);
    },
    onSuccess: (d) => {
      if (d) {
        setForm(d);
        invalidate();
        toast.success(t("zeugnisse.generiert"));
      }
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const neuAbschnitt = useMutation({
    mutationFn: (key: string) => generateAbschnitt(id, key),
    onSuccess: (d) => {
      setForm(d);
      invalidate();
      toast.success(t("zeugnisse.abschnittNeu"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const baukasten = useMutation({
    mutationFn: async () => {
      // Erst die Eingaben (Noten + Freitexte) sichern, dann aus Bausteinen bauen.
      if (!form) return null;
      await updateZeugnis(id, {
        geschlecht: form.geschlecht,
        taetigkeit: form.taetigkeit,
        abteilung: form.abteilung,
        eintritt: form.eintritt,
        austritt: form.austritt,
        art: form.art,
        anlass: form.anlass,
        fuehrungskraft: form.fuehrungskraft,
        taetigkeit_stichpunkte: form.taetigkeit_stichpunkte,
        besondere_kompetenzen: form.besondere_kompetenzen,
        besondere_erfolge: form.besondere_erfolge,
        bewertungen: form.bewertungen,
      });
      return baukastenZeugnis(id);
    },
    onSuccess: (d) => {
      if (d) {
        setForm(d);
        invalidate();
        toast.success(t("zeugnisse.bausteineErzeugt"));
      }
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const baustein = useMutation({
    mutationFn: (key: string) => baukastenAbschnitt(id, key),
    onSuccess: (d) => {
      setForm(d);
      invalidate();
      toast.success(t("zeugnisse.abschnittBaustein"));
    },
    onError: (e: Error) => toast.error(e.message),
  });

  const entfernen = useMutation({
    mutationFn: () => deleteZeugnis(id),
    onSuccess: () => {
      toast.success(t("zeugnisse.geloescht"));
      qc.invalidateQueries({ queryKey: zKeys.liste() });
      onDeleted();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  if (!form) return <div className="rounded-lg border p-6 text-sm text-muted-foreground">…</div>;

  const dims = ZEUGNIS_DIMENSIONEN.filter((d) => d !== "fuehrung" || form.fuehrungskraft);
  const setNote = (dim: string, note: number) =>
    setForm({ ...form, bewertungen: { ...form.bewertungen, [dim]: note } });
  const set = (k: keyof ZeugnisDetail, v: unknown) => setForm({ ...form, [k]: v });

  return (
    <div className="space-y-5">
      {/* Kopf: Name + Aktionen */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="text-base font-semibold">{form.name}</div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            className={ghost}
            disabled={!form.abschnitte || entfernen.isPending}
            onClick={() => downloadDocx(id, form.name).catch((e) => toast.error(String(e)))}
          >
            <Download className="h-3.5 w-3.5" /> DOCX
          </button>
          <button
            type="button"
            className={ghost}
            disabled={!form.abschnitte}
            onClick={() => downloadPdf(id, form.name).catch((e) => toast.error(String(e)))}
          >
            <Download className="h-3.5 w-3.5" /> PDF
          </button>
          <button
            type="button"
            className={`${ghost} text-destructive`}
            disabled={entfernen.isPending}
            onClick={() => {
              if (confirm(t("zeugnisse.loeschenBestaetigen"))) entfernen.mutate();
            }}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      {/* Stammdaten */}
      <section className="rounded-lg border p-3">
        <div className="mb-2 text-xs font-medium">{t("zeugnisse.stammdaten")}</div>
        <div className="grid gap-2 sm:grid-cols-2">
          <label className="text-xs">
            {t("zeugnisse.geschlecht")}
            <select
              className={`${feld} mt-1 w-full`}
              value={form.geschlecht ?? ""}
              onChange={(e) => set("geschlecht", e.target.value || null)}
            >
              <option value="">—</option>
              <option value="w">{t("zeugnisse.frau")}</option>
              <option value="m">{t("zeugnisse.herr")}</option>
              <option value="d">{t("zeugnisse.divers")}</option>
            </select>
          </label>
          <TextFeld label={t("zeugnisse.personalnummer")} value={form.personalnummer} onChange={(v) => set("personalnummer", v)} />
          <TextFeld label={t("zeugnisse.abteilung")} value={form.abteilung} onChange={(v) => set("abteilung", v)} />
          <TextFeld label={t("zeugnisse.taetigkeit")} value={form.taetigkeit} onChange={(v) => set("taetigkeit", v)} />
          <DatumFeld label={t("zeugnisse.geburtsdatum")} value={form.geburtsdatum} onChange={(v) => set("geburtsdatum", v)} />
          <DatumFeld label={t("zeugnisse.eintritt")} value={form.eintritt} onChange={(v) => set("eintritt", v)} />
          <DatumFeld label={t("zeugnisse.austritt")} value={form.austritt} onChange={(v) => set("austritt", v)} />
          <DatumFeld label={t("zeugnisse.ausstellungsdatum")} value={form.ausstellungsdatum} onChange={(v) => set("ausstellungsdatum", v)} />
          <TextFeld label={t("zeugnisse.anlass")} value={form.anlass} onChange={(v) => set("anlass", v)} />
          <label className="flex items-center gap-2 text-xs">
            <input
              type="checkbox"
              checked={form.fuehrungskraft}
              onChange={(e) => set("fuehrungskraft", e.target.checked)}
            />
            {t("zeugnisse.fuehrungskraft")}
          </label>
        </div>
      </section>

      {/* Tätigkeit / Erfolge */}
      <section className="rounded-lg border p-3">
        <div className="mb-2 text-xs font-medium">{t("zeugnisse.taetigkeitErfolge")}</div>
        <div className="space-y-2">
          <AreaFeld label={t("zeugnisse.stichpunkte")} value={form.taetigkeit_stichpunkte} onChange={(v) => set("taetigkeit_stichpunkte", v)} />
          <AreaFeld label={t("zeugnisse.kompetenzen")} value={form.besondere_kompetenzen} onChange={(v) => set("besondere_kompetenzen", v)} />
          <AreaFeld label={t("zeugnisse.erfolge")} value={form.besondere_erfolge} onChange={(v) => set("besondere_erfolge", v)} />
        </div>
      </section>

      {/* Bewertung */}
      <section className="rounded-lg border p-3">
        <div className="mb-2 flex items-center justify-between">
          <div className="text-xs font-medium">{t("zeugnisse.bewertung")}</div>
          <div className="text-xs text-muted-foreground">
            {t("zeugnisse.schlussnote")}:{" "}
            <span className="font-semibold">{form.schlussnote != null ? form.schlussnote.toFixed(1) : "—"}</span>
          </div>
        </div>
        <div className="mb-2 flex flex-wrap items-center gap-2 border-b pb-2">
          <span className="text-[0.7rem] font-medium uppercase tracking-wide text-muted-foreground">
            {t("zeugnisse.vorlagen")}
          </span>
          <VorlagenLeiste noten={form.bewertungen} onApply={(n) => setForm({ ...form, bewertungen: n })} />
        </div>
        <div className="space-y-1">
          {dims.map((dim) => (
            <div key={dim} className="flex items-center justify-between gap-2">
              <span className="text-sm">{t(`zeugnisse.dim.${dim}`)}</span>
              <div className="flex gap-1">
                {[1, 2, 3, 4].map((n) => (
                  <button
                    key={n}
                    type="button"
                    onClick={() => setNote(dim, n)}
                    className={`h-7 w-7 rounded-md border text-xs ${
                      form.bewertungen[dim] === n
                        ? "border-primary bg-primary text-primary-foreground"
                        : "border-input hover:bg-muted"
                    }`}
                    title={t(`zeugnisse.note.${n}`)}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      {/* Aktionen: speichern + erzeugen (Textbausteine oder KI) */}
      {(() => {
        const keineNoten = Object.keys(form.bewertungen).length === 0;
        const laeuft = baukasten.isPending || generieren.isPending;
        return (
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              className={ghost}
              disabled={speichern.isPending}
              onClick={() =>
                speichern.mutate({
                  geschlecht: form.geschlecht,
                  geburtsdatum: form.geburtsdatum,
                  personalnummer: form.personalnummer,
                  abteilung: form.abteilung,
                  taetigkeit: form.taetigkeit,
                  eintritt: form.eintritt,
                  austritt: form.austritt,
                  art: form.art,
                  anlass: form.anlass,
                  fuehrungskraft: form.fuehrungskraft,
                  ausstellungsdatum: form.ausstellungsdatum,
                  taetigkeit_stichpunkte: form.taetigkeit_stichpunkte,
                  besondere_kompetenzen: form.besondere_kompetenzen,
                  besondere_erfolge: form.besondere_erfolge,
                  bewertungen: form.bewertungen,
                })
              }
            >
              {speichern.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
              {t("zeugnisse.speichern")}
            </button>
            <button
              type="button"
              className={primary}
              disabled={laeuft || keineNoten}
              title={t("zeugnisse.ausBausteinenTitel")}
              onClick={() => baukasten.mutate()}
            >
              {baukasten.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Blocks className="h-3.5 w-3.5" />
              )}
              {t("zeugnisse.ausBausteinen")}
            </button>
            <button
              type="button"
              className={ghost}
              disabled={laeuft || keineNoten}
              title={t("zeugnisse.mitKiTitel")}
              onClick={() => generieren.mutate()}
            >
              {generieren.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5" />
              )}
              {t("zeugnisse.mitKi")}
            </button>
          </div>
        );
      })()}

      {/* Generierter, editierbarer Text */}
      {form.abschnitte && (
        <section className="rounded-lg border p-3">
          <div className="mb-2 text-xs font-medium">{t("zeugnisse.text")}</div>
          <div className="space-y-2">
            {ZEUGNIS_ABSCHNITTE.map((key) => {
              const kiLaeuft = neuAbschnitt.isPending && neuAbschnitt.variables === key;
              const bLaeuft = baustein.isPending && baustein.variables === key;
              const gesperrt = neuAbschnitt.isPending || baustein.isPending;
              const btn =
                "inline-flex items-center gap-1 rounded-md border border-input px-2 py-0.5 " +
                "text-[0.7rem] hover:bg-muted disabled:opacity-50";
              return (
                <AreaFeld
                  key={key}
                  label={t(`zeugnisse.abschnitt.${key}`)}
                  value={form.abschnitte?.[key] ?? ""}
                  rows={4}
                  onChange={(v) =>
                    setForm({ ...form, abschnitte: { ...(form.abschnitte ?? {}), [key]: v } })
                  }
                  action={
                    <span className="flex items-center gap-1">
                      <button
                        type="button"
                        className={btn}
                        disabled={gesperrt}
                        title={t("zeugnisse.abschnittBausteinTitel")}
                        onClick={() => baustein.mutate(key)}
                      >
                        {bLaeuft ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <Blocks className="h-3 w-3" />
                        )}
                        {t("zeugnisse.abschnittBausteinKurz")}
                      </button>
                      <button
                        type="button"
                        className={btn}
                        disabled={gesperrt}
                        title={t("zeugnisse.abschnittNeuTitel")}
                        onClick={() => neuAbschnitt.mutate(key)}
                      >
                        {kiLaeuft ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <RefreshCw className="h-3 w-3" />
                        )}
                        {t("zeugnisse.abschnittNeuKurz")}
                      </button>
                    </span>
                  }
                />
              );
            })}
          </div>
          <div className="mt-2">
            <button
              type="button"
              className={ghost}
              disabled={speichern.isPending}
              onClick={() => speichern.mutate({ abschnitte: form.abschnitte ?? {} })}
            >
              {t("zeugnisse.textSpeichern")}
            </button>
          </div>
        </section>
      )}

      {/* Vorschau: zusammengesetztes Zeugnis (schreibgeschützt) */}
      {form.abschnitte && (
        <section className="rounded-lg border bg-muted/30 p-4">
          <div className="mb-3 text-xs font-medium">{t("zeugnisse.vorschau")}</div>
          <article className="mx-auto max-w-[52rem] space-y-3 rounded-md bg-background p-6 text-sm leading-relaxed shadow-sm">
            {ZEUGNIS_ABSCHNITTE.map((key) => {
              const text = (form.abschnitte?.[key] ?? "").trim();
              if (!text) return null;
              return (
                <p key={key} className="whitespace-pre-wrap">
                  {text}
                </p>
              );
            })}
            {ZEUGNIS_ABSCHNITTE.every((k) => !(form.abschnitte?.[k] ?? "").trim()) && (
              <p className="text-muted-foreground">{t("zeugnisse.vorschauLeer")}</p>
            )}
          </article>
        </section>
      )}
    </div>
  );
}

function TextFeld({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string | null;
  onChange: (v: string | null) => void;
}) {
  return (
    <label className="text-xs">
      {label}
      <input
        className={`${feld} mt-1 w-full`}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
      />
    </label>
  );
}

function DatumFeld({
  label,
  value,
  onChange,
}: {
  label: string;
  value: string | null;
  onChange: (v: string | null) => void;
}) {
  return (
    <label className="text-xs">
      {label}
      <input
        type="date"
        className={`${feld} mt-1 w-full`}
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value || null)}
      />
    </label>
  );
}

function AreaFeld({
  label,
  value,
  onChange,
  rows = 2,
  action,
}: {
  label: string;
  value: string | null;
  onChange: (v: string) => void;
  rows?: number;
  action?: ReactNode;
}) {
  return (
    <label className="block text-xs">
      <span className="flex items-center justify-between gap-2">
        <span>{label}</span>
        {action}
      </span>
      <textarea
        rows={rows}
        className="mt-1 w-full rounded-md border border-input bg-background p-2 text-sm
                   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}
