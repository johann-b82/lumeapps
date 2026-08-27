import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useLocation } from "wouter";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { BarChart3, ChevronLeft, FileDown, FileText, GripVertical, Loader2, Plus, Trash2, Upload, Eye, EyeOff } from "lucide-react";
import { DndContext, closestCenter, type DragEndEvent } from "@dnd-kit/core";
import { SortableContext, verticalListSortingStrategy, useSortable, arrayMove } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { AuthImage, NewsletterPdfPages } from "@/components/newsletter/NewsletterView";
import { exportNewsletterPdf } from "@/lib/newsletterPdf";
import {
  NEWSLETTER_RUBRIKEN,
  addEintrag,
  createAusgabe,
  deleteAusgabe,
  deleteBild,
  deleteEintrag,
  fetchAdminAusgabe,
  fetchAdminAusgaben,
  insertKpi,
  removeKpi,
  updateAusgabe,
  updateEintrag,
  uploadBild,
  type AusgabeDetail,
  type Eintrag,
  type Rubrik,
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
    <div className="mx-auto max-w-3xl px-6 pt-4 pb-10">
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
        <span className="text-sm">{t("newsletter.kpiTitel")}</span>
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

      <BlockReihenfolge ausgabe={ausgabe} onSaved={invalidate} />

      {vorschau && (
        <div className="mb-4">
          <div className="mb-2 flex items-center justify-end">
            <button type="button" className={primary} disabled={pdfLaeuft} onClick={alsPdf}>
              {pdfLaeuft ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <FileDown className="h-3.5 w-3.5" />}
              {t("newsletter.pdf")}
            </button>
          </div>
          <div ref={previewRef} className="overflow-x-auto rounded-lg border bg-muted/40 p-4">
            <NewsletterPdfPages ausgabe={ausgabe} />
          </div>
        </div>
      )}

      {NEWSLETTER_RUBRIKEN.map((rubrik) => (
        <RubrikSektion
          key={rubrik}
          ausgabe={ausgabe}
          rubrik={rubrik}
          onChange={invalidate}
        />
      ))}
    </div>
  );
}

function RubrikSektion({
  ausgabe,
  rubrik,
  onChange,
}: {
  ausgabe: AusgabeDetail;
  rubrik: Rubrik;
  onChange: () => void;
}) {
  const { t } = useTranslation();
  const eintraege = ausgabe.eintraege
    .filter((e) => e.rubrik === rubrik)
    .sort((a, b) => a.reihenfolge - b.reihenfolge);

  const hinzufuegen = useMutation({
    mutationFn: () =>
      addEintrag(ausgabe.id, { rubrik, untertitel: t("newsletter.neuerEintrag"), inhalt_md: "" }),
    onSuccess: () => onChange(),
    onError: (e: Error) => toast.error(e.message),
  });

  return (
    <section className="mb-5 rounded-lg border p-3">
      <div className="mb-2 flex items-center justify-between">
        <h2 className="text-sm font-semibold">{t(`newsletter.rubrik.${rubrik}`)}</h2>
        <button type="button" className={btn} disabled={hinzufuegen.isPending} onClick={() => hinzufuegen.mutate()}>
          <Plus className="h-3.5 w-3.5" /> {t("newsletter.eintragHinzufuegen")}
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

/** Drag&Drop-Reihenfolge der Rubriken. Die KPIs sind kein eigener Block mehr,
 *  sondern erscheinen fest als eigene Seite am Anfang von „Intern". */
function BlockReihenfolge({ ausgabe, onSaved }: { ausgabe: AusgabeDetail; onSaved: () => void }) {
  const { t } = useTranslation();
  const standard = [...NEWSLETTER_RUBRIKEN] as string[];
  const merge = (gespeichert: string[] | null | undefined) => {
    const g = (gespeichert ?? []).filter((k) => standard.includes(k));
    return [...g, ...standard.filter((k) => !g.includes(k))];
  };
  const [items, setItems] = useState<string[]>(merge(ausgabe.block_reihenfolge));
  useEffect(() => {
    setItems(merge(ausgabe.block_reihenfolge));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ausgabe.id]);

  const save = useMutation({
    mutationFn: (order: string[]) => updateAusgabe(ausgabe.id, { block_reihenfolge: order }),
    onSuccess: () => onSaved(),
    onError: (e: Error) => toast.error(e.message),
  });
  const label = (k: string) => (k === "kpi" ? t("newsletter.kpiTitel") : t(`newsletter.rubrik.${k}`));
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
