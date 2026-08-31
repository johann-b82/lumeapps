import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { BarChart3, ChevronLeft, FileDown, FileText, GripVertical, Image as ImageIcon, Loader2, Plus, Trash2, Upload, Eye, EyeOff } from "lucide-react";
import { DndContext, closestCenter, type DragEndEvent } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy, rectSortingStrategy, useSortable, arrayMove } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { AuthImage, AuthImageUrl, NewsletterPdfPages, PuzzleBilder } from "@/components/newsletter/NewsletterView";
import { exportNewsletterPdf } from "@/lib/newsletterPdf";
import {
  NEWSLETTER_RUBRIKEN,
  addEintrag,
  coverUrl,
  createAusgabe,
  deleteAusgabe,
  deleteBild,
  deleteCover,
  deleteEintrag,
  deleteEintragBild,
  deleteRueck,
  eintragBildUrl,
  fetchAdminAusgabe,
  fetchAdminAusgaben,
  insertKpi,
  kapitelKeys,
  removeKpi,
  reorderEintragBilder,
  rubrikAnlegen,
  rubrikLoeschen,
  rueckUrl,
  updateAusgabe,
  updateEintrag,
  updateEintragBildLayout,
  uploadBild,
  uploadCover,
  uploadEintragBild,
  uploadRueck,
  type AusgabeDetail,
  type Eintrag,
  type EintragBild,
} from "@/lib/newsletterApi";

const feld =
  "h-8 rounded-md border border-input bg-background px-2 text-sm " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
const btn =
  "inline-flex h-8 items-center gap-2 rounded-md border border-input px-3 text-xs " +
  "hover:bg-muted disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";
const primary =
  "inline-flex h-8 items-center gap-2 rounded-md bg-primary px-3 text-xs text-primary-foreground " +
  "disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring";

const qk = {
  liste: () => ["newsletter", "admin"] as const,
  detail: (id: number) => ["newsletter", "admin", id] as const,
};

export function NewsletterAdminPage({ id }: { id?: number }) {
  return id ? <Editor id={id} /> : <AdminListe />;
}

function AdminListe() {
  const { t } = useTranslation();
  const [, setLocation] = useLocation();
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: qk.liste(), queryFn: fetchAdminAusgaben });

  const jetztJahr = new Date().getFullYear();
  const [jahr, setJahr] = useState(jetztJahr);
  const [quartal, setQuartal] = useState(1);
  const anlegen = useMutation({
    mutationFn: () => createAusgabe({ jahr, quartal }),
    onSuccess: (a) => {
      qc.invalidateQueries({ queryKey: qk.liste() });
      setLocation(`/newsletter/admin/${a.id}`);
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="mx-auto max-w-3xl px-6 pt-4 pb-10">
      <div className="mb-4 flex items-center gap-2">
        <button type="button" onClick={() => setLocation("/newsletter")} className={btn}>
          <ChevronLeft className="h-3.5 w-3.5" /> {t("newsletter.zurueck")}
        </button>
        <h1 className="text-lg font-semibold">{t("newsletter.redaktion")}</h1>
      </div>

      <div className="mb-4 flex flex-wrap items-end gap-2 rounded-lg border p-3">
        <label className="text-xs">
          {t("newsletter.jahr")}
          <input
            type="number"
            value={jahr}
            onChange={(e) => setJahr(Number(e.target.value))}
            className={`${feld} mt-1 w-24`}
          />
        </label>
        <label className="text-xs">
          {t("newsletter.quartal")}
          <select
            value={quartal}
            onChange={(e) => setQuartal(Number(e.target.value))}
            className={`${feld} mt-1 w-20`}
          >
            {[1, 2, 3, 4].map((q) => (
              <option key={q} value={q}>
                Q{q}
              </option>
            ))}
          </select>
        </label>
        <button type="button" className={primary} disabled={anlegen.isPending} onClick={() => anlegen.mutate()}>
          {anlegen.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          <Plus className="h-3.5 w-3.5" /> {t("newsletter.neueAusgabe")}
        </button>
      </div>

      <ul className="space-y-2">
        {(data ?? []).map((a) => (
          <li key={a.id}>
            <button
              type="button"
              onClick={() => setLocation(`/newsletter/admin/${a.id}`)}
              className="flex w-full items-center justify-between rounded-lg border px-4 py-2 text-left
                         hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            >
              <span className="font-medium">{a.titel || `Q${a.quartal} ${a.jahr}`}</span>
              <span
                className={`text-xs ${
                  a.status === "veroeffentlicht" ? "text-emerald-600" : "text-amber-600"
                }`}
              >
                {t(`newsletter.status.${a.status}`)}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

function Editor({ id }: { id: number }) {
  const { t } = useTranslation();
  const [, setLocation] = useLocation();
  const qc = useQueryClient();
  const { data: ausgabe } = useQuery({ queryKey: qk.detail(id), queryFn: () => fetchAdminAusgabe(id) });

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: qk.detail(id) });
    qc.invalidateQueries({ queryKey: qk.liste() });
    qc.invalidateQueries({ queryKey: ["newsletter"] });
  };

  const [titel, setTitel] = useState("");
  useEffect(() => {
    if (ausgabe) setTitel(ausgabe.titel ?? "");
  }, [ausgabe]);

  const speichernTitel = useMutation({
    mutationFn: () => updateAusgabe(id, { titel: titel.trim() || null }),
    onSuccess: () => {
      toast.success(t("newsletter.gespeichert"));
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const statusUmschalten = useMutation({
    mutationFn: (status: "entwurf" | "veroeffentlicht") => updateAusgabe(id, { status }),
    onSuccess: () => invalidate(),
    onError: (e: Error) => toast.error(e.message),
  });
  const loeschen = useMutation({
    mutationFn: () => deleteAusgabe(id),
    onSuccess: () => {
      toast.success(t("newsletter.geloescht"));
      setLocation("/newsletter/admin");
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const kpiEin = useMutation({
    mutationFn: () => insertKpi(id),
    onSuccess: () => {
      toast.success(t("newsletter.kpiEingefuegt"));
      invalidate();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const kpiWeg = useMutation({
    mutationFn: () => removeKpi(id),
    onSuccess: () => invalidate(),
    onError: (e: Error) => toast.error(e.message),
  });

  const previewRef = useRef<HTMLDivElement>(null);
  const [vorschau, setVorschau] = useState(false);
  const [pdfLaeuft, setPdfLaeuft] = useState(false);
  const alsPdf = async () => {
    if (!previewRef.current || !ausgabe) return;
    setPdfLaeuft(true);
    try {
      await exportNewsletterPdf(
        previewRef.current,
        `Newsletter_Q${ausgabe.quartal}_${ausgabe.jahr}.pdf`,
      );
    } catch (e) {
      console.error("PDF-Export fehlgeschlagen:", e);
      toast.error(t("newsletter.pdfFehler"));
    } finally {
      setPdfLaeuft(false);
    }
  };

  if (!ausgabe) return <div className="p-6 text-sm text-muted-foreground">…</div>;
  const veroeffentlicht = ausgabe.status === "veroeffentlicht";

  return (
    <div className="mx-auto max-w-6xl px-6 pt-4 pb-10">
      <div className="mx-auto max-w-3xl">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => setLocation("/newsletter/admin")} className={btn}>
          <ChevronLeft className="h-3.5 w-3.5" /> {t("newsletter.zurueck")}
        </button>
        <span className="text-sm text-muted-foreground">
          {t("newsletter.kopf", { quartal: ausgabe.quartal, jahr: ausgabe.jahr })}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <button type="button" className={btn} onClick={() => setVorschau((v) => !v)}>
            <FileText className="h-3.5 w-3.5" />
            {vorschau ? t("newsletter.vorschauAus") : t("newsletter.vorschau")}
          </button>
          <button
            type="button"
            className={btn}
            onClick={() => statusUmschalten.mutate(veroeffentlicht ? "entwurf" : "veroeffentlicht")}
          >
            {veroeffentlicht ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}
            {veroeffentlicht ? t("newsletter.zurueckziehen") : t("newsletter.veroeffentlichen")}
          </button>
          <button
            type="button"
            className={`${btn} text-destructive`}
            onClick={() => {
              if (confirm(t("newsletter.loeschenBestaetigen"))) loeschen.mutate();
            }}
          >
            <Trash2 className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>

      <div className="mb-4 flex items-end gap-2 rounded-lg border p-3">
        <label className="flex-1 text-xs">
          {t("newsletter.ausgabentitel")}
          <input
            value={titel}
            onChange={(e) => setTitel(e.target.value)}
            placeholder={`Q${ausgabe.quartal} ${ausgabe.jahr}`}
            className={`${feld} mt-1 w-full`}
          />
        </label>
        <button type="button" className={primary} disabled={speichernTitel.isPending} onClick={() => speichernTitel.mutate()}>
          {t("newsletter.speichern")}
        </button>
        <span
          className={`ml-1 text-xs ${veroeffentlicht ? "text-emerald-600" : "text-amber-600"}`}
        >
          {t(`newsletter.status.${ausgabe.status}`)}
        </span>
      </div>

      {/* ACM-KPI-Block: eingefrorener Snapshot der Belegschafts-KPIs. */}
      <div className="mb-4 flex flex-wrap items-center gap-2 rounded-lg border p-3">
        <BarChart3 className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        <div className="min-w-[8rem] flex-1">
          <AbschnittTitel ausgabe={ausgabe} blockKey="kpi" standard={t("newsletter.kpiTitel")} onSaved={invalidate} />
        </div>
        <span className="text-xs text-muted-foreground">
          {ausgabe.kpi_snapshot ? t("newsletter.kpiEnthalten") : t("newsletter.kpiOhne")}
        </span>
        <div className="ml-auto flex gap-2">
          <button type="button" className={btn} disabled={kpiEin.isPending} onClick={() => kpiEin.mutate()}>
            {kpiEin.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
            {ausgabe.kpi_snapshot ? t("newsletter.kpiAktualisieren") : t("newsletter.kpiEinfuegen")}
          </button>
          {ausgabe.kpi_snapshot && (
            <button type="button" className={btn} disabled={kpiWeg.isPending} onClick={() => kpiWeg.mutate()}>
              {t("newsletter.kpiEntfernen")}
            </button>
          )}
        </div>
      </div>

      <CoverBilder ausgabe={ausgabe} onChange={invalidate} />

      <BlockReihenfolge ausgabe={ausgabe} onSaved={invalidate} />
      </div>

      {vorschau && (
        <div className="mb-4">
          <div className="mx-auto mb-2 flex max-w-3xl items-center justify-end">
            <button type="button" className={primary} disabled={pdfLaeuft} onClick={alsPdf}>
              {pdfLaeuft ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileDown className="h-3.5 w-3.5" />}
              {t("newsletter.pdf")}
            </button>
          </div>
          <div ref={previewRef} className="flex justify-center overflow-x-auto rounded-lg border bg-muted/40 p-4">
            <NewsletterPdfPages ausgabe={ausgabe} />
          </div>
        </div>
      )}

      <div className="mx-auto max-w-3xl">
        {kapitelKeys(ausgabe).map((rubrik) => (
          <RubrikSektion
            key={rubrik}
            ausgabe={ausgabe}
            rubrik={rubrik}
            onChange={invalidate}
          />
        ))}
        <NeuesKapitel ausgabe={ausgabe} onChange={invalidate} />
      </div>
    </div>
  );
}

function RubrikSektion({
  ausgabe,
  rubrik,
  onChange,
}: {
  ausgabe: AusgabeDetail;
  rubrik: string;
  onChange: () => void;
}) {
  const { t } = useTranslation();
  const istStandard = (NEWSLETTER_RUBRIKEN as readonly string[]).includes(rubrik);
  const eintraege = ausgabe.eintraege
    .filter((e) => e.rubrik === rubrik)
    .sort((a, b) => a.reihenfolge - b.reihenfolge);

  const hinzufuegen = useMutation({
    mutationFn: () =>
      addEintrag(ausgabe.id, { rubrik, untertitel: t("newsletter.neuerEintrag"), inhalt_md: "" }),
    onSuccess: () => onChange(),
    onError: (e: Error) => toast.error(e.message),
  });
  const loeschen = useMutation({
    mutationFn: () => rubrikLoeschen(ausgabe.id, rubrik),
    onSuccess: () => {
      toast.success(t("newsletter.kapitelGeloescht"));
      onChange();
    },
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <section className="mb-5 rounded-lg border p-3">
      <div className="mb-2 flex items-center gap-2">
        <AbschnittTitel
          ausgabe={ausgabe}
          blockKey={rubrik}
          standard={istStandard ? t(`newsletter.rubrik.${rubrik}`) : rubrik}
          onSaved={onChange}
        />
        <button type="button" className={`${btn} shrink-0`} disabled={hinzufuegen.isPending} onClick={() => hinzufuegen.mutate()}>
          <Plus className="h-3.5 w-3.5" /> {t("newsletter.eintragHinzufuegen")}
        </button>
        <button
          type="button"
          className={`${btn} shrink-0 text-destructive`}
          disabled={loeschen.isPending}
          title={t("newsletter.kapitelLoeschen")}
          onClick={() => {
            if (confirm(t("newsletter.kapitelLoeschenBestaetigen"))) loeschen.mutate();
          }}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
      {eintraege.length === 0 ? (
        <p className="text-xs text-muted-foreground">{t("newsletter.rubrikLeer")}</p>
      ) : (
        <div className="space-y-3">
          {eintraege.map((e) => (
            <EintragEditor key={e.id} eintrag={e} onChange={onChange} />
          ))}
        </div>
      )}
    </section>
  );
}

/** „Neues Kapitel" — legt ein Ausgabe-eigenes Kapitel an (ans Ende der Liste). */
function NeuesKapitel({ ausgabe, onChange }: { ausgabe: AusgabeDetail; onChange: () => void }) {
  const { t } = useTranslation();
  const [titel, setTitel] = useState("");
  const anlegen = useMutation({
    mutationFn: () => rubrikAnlegen(ausgabe.id, titel.trim()),
    onSuccess: () => {
      setTitel("");
      toast.success(t("newsletter.kapitelAngelegt"));
      onChange();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  return (
    <div className="mb-5 flex items-center gap-2 rounded-lg border border-dashed p-3">
      <input
        value={titel}
        onChange={(e) => setTitel(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && titel.trim()) anlegen.mutate();
        }}
        placeholder={t("newsletter.kapitelName")}
        className={`${feld} flex-1`}
      />
      <button
        type="button"
        className={`${primary} shrink-0`}
        disabled={anlegen.isPending || !titel.trim()}
        onClick={() => anlegen.mutate()}
      >
        {anlegen.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
        {t("newsletter.kapitelHinzufuegen")}
      </button>
    </div>
  );
}

function EintragEditor({ eintrag, onChange }: { eintrag: Eintrag; onChange: () => void }) {
  const { t } = useTranslation();
  const [untertitel, setUntertitel] = useState(eintrag.untertitel);
  const [inhalt, setInhalt] = useState(eintrag.inhalt_md);
  useEffect(() => {
    setUntertitel(eintrag.untertitel);
    setInhalt(eintrag.inhalt_md);
  }, [eintrag.id, eintrag.untertitel, eintrag.inhalt_md]);

  const speichern = useMutation({
    mutationFn: () => updateEintrag(eintrag.id, { untertitel: untertitel.trim(), inhalt_md: inhalt }),
    onSuccess: () => {
      toast.success(t("newsletter.gespeichert"));
      onChange();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const entfernen = useMutation({
    mutationFn: () => deleteEintrag(eintrag.id),
    onSuccess: () => onChange(),
    onError: (e: Error) => toast.error(e.message),
  });
  const bildHoch = useMutation({
    mutationFn: (f: File) => uploadBild(eintrag.id, f),
    onSuccess: () => onChange(),
    onError: (e: Error) => toast.error(e.message),
  });
  const bildWeg = useMutation({
    mutationFn: () => deleteBild(eintrag.id),
    onSuccess: () => onChange(),
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <div className="rounded-md border border-border/70 p-2">
      <input
        value={untertitel}
        onChange={(e) => setUntertitel(e.target.value)}
        placeholder={t("newsletter.untertitel")}
        className={`${feld} mb-2 w-full font-medium`}
      />
      <textarea
        value={inhalt}
        onChange={(e) => setInhalt(e.target.value)}
        rows={4}
        placeholder={t("newsletter.inhaltPlatzhalter")}
        className="mb-2 w-full rounded-md border border-input bg-background p-2 text-sm font-mono
                   focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      />
      {eintrag.hat_bild && (
        <div className="mb-2">
          <AuthImage eintragId={eintrag.id} alt={untertitel} />
        </div>
      )}
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" className={primary} disabled={speichern.isPending || !untertitel.trim()} onClick={() => speichern.mutate()}>
          {speichern.isPending && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          {t("newsletter.speichern")}
        </button>
        <label className={`${btn} cursor-pointer`}>
          <Upload className="h-3.5 w-3.5" /> {t("newsletter.bild")}
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) bildHoch.mutate(f);
              e.currentTarget.value = "";
            }}
          />
        </label>
        {eintrag.hat_bild && (
          <button type="button" className={btn} onClick={() => bildWeg.mutate()}>
            {t("newsletter.bildEntfernen")}
          </button>
        )}
        <button
          type="button"
          className={`${btn} ml-auto text-destructive`}
          onClick={() => {
            if (confirm(t("newsletter.eintragLoeschenBestaetigen"))) entfernen.mutate();
          }}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
      <PuzzleEditor eintrag={eintrag} onChange={onChange} />
    </div>
  );
}

/** Ein Puzzle-Bild im Editor: sortierbare Kachel mit Größen-Steuerung + Löschen. */
function PuzzleThumb({ bild, onChange }: { bild: EintragBild; onChange: () => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: bild.id,
  });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 };
  const layout = useMutation({
    mutationFn: (patch: { spalten?: number; zeilen?: number }) => updateEintragBildLayout(bild.id, patch),
    onSuccess: () => onChange(),
    onError: (e: Error) => toast.error(e.message),
  });
  const entfernen = useMutation({
    mutationFn: () => deleteEintragBild(bild.id),
    onSuccess: () => onChange(),
    onError: (e: Error) => toast.error(e.message),
  });
  const stepBtn = "rounded border px-1 leading-none disabled:opacity-30";
  return (
    <div ref={setNodeRef} style={style} className="w-24 shrink-0 rounded-md border p-1">
      <div className="relative mb-1 aspect-square overflow-hidden rounded bg-muted">
        <AuthImageUrl url={eintragBildUrl(bild.id)} alt="" className="absolute inset-0 block h-full w-full object-cover" />
        <button
          type="button"
          {...attributes}
          {...listeners}
          className="absolute left-0.5 top-0.5 cursor-grab rounded bg-black/40 p-0.5 text-white"
          aria-label="Ziehen"
        >
          <GripVertical className="h-3 w-3" />
        </button>
      </div>
      <div className="flex items-center justify-between text-[0.62rem]">
        <span aria-hidden>↔</span>
        <div className="flex items-center gap-0.5">
          <button type="button" className={stepBtn} disabled={bild.spalten <= 1} onClick={() => layout.mutate({ spalten: bild.spalten - 1 })}>−</button>
          <span className="w-3 text-center">{bild.spalten}</span>
          <button type="button" className={stepBtn} disabled={bild.spalten >= 4} onClick={() => layout.mutate({ spalten: bild.spalten + 1 })}>+</button>
        </div>
      </div>
      <div className="mt-0.5 flex items-center justify-between text-[0.62rem]">
        <span aria-hidden>↕</span>
        <div className="flex items-center gap-0.5">
          <button type="button" className={stepBtn} disabled={bild.zeilen <= 1} onClick={() => layout.mutate({ zeilen: bild.zeilen - 1 })}>−</button>
          <span className="w-3 text-center">{bild.zeilen}</span>
          <button type="button" className={stepBtn} disabled={bild.zeilen >= 2} onClick={() => layout.mutate({ zeilen: bild.zeilen + 1 })}>+</button>
        </div>
      </div>
      <button
        type="button"
        className="mt-1 w-full rounded border py-0.5 text-[0.62rem] text-destructive"
        onClick={() => entfernen.mutate()}
      >
        <Trash2 className="mx-auto h-3 w-3" />
      </button>
    </div>
  );
}

/** Mehrere Bilder je Eintrag hochladen, per Drag&Drop anordnen, Zellen spannen. */
function PuzzleEditor({ eintrag, onChange }: { eintrag: Eintrag; onChange: () => void }) {
  const { t } = useTranslation();
  const bilder = eintrag.bilder;
  const hochladen = useMutation({
    mutationFn: async (dateien: File[]) => {
      for (const f of dateien) await uploadEintragBild(eintrag.id, f);
    },
    onSuccess: () => onChange(),
    onError: (e: Error) => toast.error(e.message),
  });
  const anordnen = useMutation({
    mutationFn: (ids: number[]) => reorderEintragBilder(eintrag.id, ids),
    onSuccess: () => onChange(),
    onError: (e: Error) => toast.error(e.message),
  });
  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (over && active.id !== over.id) {
      const ids = bilder.map((b) => b.id);
      anordnen.mutate(arrayMove(ids, ids.indexOf(Number(active.id)), ids.indexOf(Number(over.id))));
    }
  };
  return (
    <div className="mt-2 rounded-md border border-border/60 p-2">
      <div className="mb-2 flex items-center gap-2">
        <ImageIcon className="h-3.5 w-3.5 text-muted-foreground" aria-hidden="true" />
        <span className="text-xs font-medium">{t("newsletter.puzzleBilder")}</span>
        <label className={`${btn} ml-auto cursor-pointer`}>
          <Upload className="h-3.5 w-3.5" /> {t("newsletter.bildHinzufuegen")}
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            multiple
            className="hidden"
            onChange={(e) => {
              const fs = Array.from(e.target.files ?? []);
              if (fs.length) hochladen.mutate(fs);
              e.currentTarget.value = "";
            }}
          />
        </label>
      </div>
      {bilder.length === 0 ? (
        <p className="text-xs text-muted-foreground">{t("newsletter.puzzleLeer")}</p>
      ) : (
        <>
          <DndContext collisionDetection={closestCenter} onDragEnd={onDragEnd}>
            <SortableContext items={bilder.map((b) => b.id)} strategy={rectSortingStrategy}>
              <div className="flex flex-wrap gap-2">
                {bilder.map((b) => (
                  <PuzzleThumb key={b.id} bild={b} onChange={onChange} />
                ))}
              </div>
            </SortableContext>
          </DndContext>
          <div className="mt-2">
            <div className="mb-1 text-[0.62rem] uppercase tracking-wide text-muted-foreground">
              {t("newsletter.vorschau")}
            </div>
            <div className="max-w-[240px]">
              <PuzzleBilder bilder={bilder} />
            </div>
          </div>
        </>
      )}
    </div>
  );
}

function SortItem({ id, label }: { id: string; label: string }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({ id });
  const style = { transform: CSS.Transform.toString(transform), transition, opacity: isDragging ? 0.5 : 1 };
  return (
    <div
      ref={setNodeRef}
      style={style}
      {...attributes}
      {...listeners}
      className="flex cursor-grab items-center gap-2 rounded-md border bg-background px-3 py-2 text-sm"
    >
      <GripVertical className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
      {label}
    </div>
  );
}

/** Bearbeitbarer Abschnitts-Titel — überschreibt den i18n-Standardnamen je Block
 *  (Rubrik oder "kpi") pro Ausgabe. Leer = Standardname. Speichert beim Verlassen. */
function AbschnittTitel({
  ausgabe,
  blockKey,
  standard,
  onSaved,
}: {
  ausgabe: AusgabeDetail;
  blockKey: string;
  standard: string;
  onSaved: () => void;
}) {
  const gespeichert = ausgabe.rubrik_titel?.[blockKey] ?? "";
  const [wert, setWert] = useState(gespeichert);
  useEffect(() => {
    setWert(ausgabe.rubrik_titel?.[blockKey] ?? "");
  }, [ausgabe.id, ausgabe.rubrik_titel, blockKey]);
  const speichern = useMutation({
    mutationFn: (v: string) =>
      updateAusgabe(ausgabe.id, { rubrik_titel: { ...(ausgabe.rubrik_titel ?? {}), [blockKey]: v.trim() } }),
    onSuccess: () => onSaved(),
    onError: (e: Error) => toast.error(e.message),
  });
  return (
    <input
      value={wert}
      onChange={(e) => setWert(e.target.value)}
      onBlur={() => {
        if (wert.trim() !== gespeichert) speichern.mutate(wert);
      }}
      placeholder={standard}
      className={`${feld} w-full font-semibold`}
    />
  );
}

/** Titel- & Rückseitenbild (vollflächig) hochladen/entfernen. */
function CoverBilder({ ausgabe, onChange }: { ausgabe: AusgabeDetail; onChange: () => void }) {
  const { t } = useTranslation();
  return (
    <div className="mb-4 rounded-lg border p-3">
      <div className="mb-2 flex items-center gap-2">
        <ImageIcon className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        <span className="text-sm font-medium">{t("newsletter.coverBereich")}</span>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <BildSlot
          label={t("newsletter.titelbild")}
          hat={ausgabe.hat_cover}
          urlFn={coverUrl}
          ausgabeId={ausgabe.id}
          upload={(f) => uploadCover(ausgabe.id, f)}
          remove={() => deleteCover(ausgabe.id)}
          onChange={onChange}
        />
        <BildSlot
          label={t("newsletter.rueckseitenbild")}
          hat={ausgabe.hat_rueck}
          urlFn={rueckUrl}
          ausgabeId={ausgabe.id}
          upload={(f) => uploadRueck(ausgabe.id, f)}
          remove={() => deleteRueck(ausgabe.id)}
          onChange={onChange}
        />
      </div>
      <p className="mt-2 text-xs text-muted-foreground">{t("newsletter.coverHinweis")}</p>
    </div>
  );
}

function BildSlot({
  label,
  hat,
  urlFn,
  ausgabeId,
  upload,
  remove,
  onChange,
}: {
  label: string;
  hat: boolean;
  urlFn: (id: number, bust?: number) => string;
  ausgabeId: number;
  upload: (f: File) => Promise<AusgabeDetail>;
  remove: () => Promise<AusgabeDetail>;
  onChange: () => void;
}) {
  const { t } = useTranslation();
  const [bust, setBust] = useState(0);
  const hochladen = useMutation({
    mutationFn: (f: File) => upload(f),
    onSuccess: () => {
      setBust(Date.now());
      onChange();
    },
    onError: (e: Error) => toast.error(e.message),
  });
  const entfernen = useMutation({
    mutationFn: () => remove(),
    onSuccess: () => onChange(),
    onError: (e: Error) => toast.error(e.message),
  });
  return (
    <div className="rounded-md border border-border/70 p-2">
      <div className="mb-1 text-xs font-medium">{label}</div>
      <div className="mb-2 flex aspect-square items-center justify-center overflow-hidden rounded bg-muted">
        {hat ? (
          <AuthImageUrl
            url={urlFn(ausgabeId, bust || undefined)}
            alt={label}
            className="h-full w-full object-cover"
          />
        ) : (
          <span className="text-xs text-muted-foreground">{t("newsletter.ohneBild")}</span>
        )}
      </div>
      <div className="flex flex-wrap gap-2">
        <label className={`${btn} cursor-pointer`}>
          <Upload className="h-3.5 w-3.5" /> {hat ? t("newsletter.bildErsetzen") : t("newsletter.bild")}
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            className="hidden"
            onChange={(e) => {
              const f = e.target.files?.[0];
              if (f) hochladen.mutate(f);
              e.currentTarget.value = "";
            }}
          />
        </label>
        {hat && (
          <button type="button" className={btn} disabled={entfernen.isPending} onClick={() => entfernen.mutate()}>
            {t("newsletter.bildEntfernen")}
          </button>
        )}
      </div>
    </div>
  );
}

/** Drag&Drop-Reihenfolge der Rubriken. Die KPIs sind kein eigener Block mehr,
 *  sondern erscheinen fest als eigene Seite am Anfang von „Intern". */
function BlockReihenfolge({ ausgabe, onSaved }: { ausgabe: AusgabeDetail; onSaved: () => void }) {
  const { t } = useTranslation();
  const standard = [...NEWSLETTER_RUBRIKEN] as string[];
  const [items, setItems] = useState<string[]>(kapitelKeys(ausgabe));
  useEffect(() => {
    setItems(kapitelKeys(ausgabe));
  }, [ausgabe.id, ausgabe.block_reihenfolge]);

  const save = useMutation({
    mutationFn: (order: string[]) => updateAusgabe(ausgabe.id, { block_reihenfolge: order }),
    onSuccess: () => onSaved(),
    onError: (e: Error) => toast.error(e.message),
  });
  const label = (k: string) =>
    ausgabe.rubrik_titel?.[k]?.trim() ||
    (standard.includes(k) ? t(`newsletter.rubrik.${k}`) : k);
  const onDragEnd = (e: DragEndEvent) => {
    const { active, over } = e;
    if (over && active.id !== over.id) {
      const neu = arrayMove(items, items.indexOf(String(active.id)), items.indexOf(String(over.id)));
      setItems(neu);
      save.mutate(neu);
    }
  };

  return (
    <div className="mb-4 rounded-lg border p-3">
      <div className="mb-2 text-sm font-medium">{t("newsletter.reihenfolge")}</div>
      <DndContext collisionDetection={closestCenter} onDragEnd={onDragEnd}>
        <SortableContext items={items} strategy={verticalListSortingStrategy}>
          <div className="space-y-1">
            {items.map((k) => (
              <SortItem key={k} id={k} label={label(k)} />
            ))}
          </div>
        </SortableContext>
      </DndContext>
    </div>
  );
}
