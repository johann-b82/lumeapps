import { useEffect, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { fetchBlob } from "@/lib/download";
import { BelegschaftKpiCharts } from "@/components/dashboard/BelegschaftKpiSection";
import type { BelegschaftKpi } from "@/lib/belegschaftApi";
import {
  NEWSLETTER_RUBRIKEN,
  bildUrl,
  coverUrl,
  eintragBildUrl,
  rueckUrl,
  type AusgabeDetail,
  type Eintrag,
  type EintragBild,
  type NeuerMitarbeiter,
  type Rubrik,
} from "@/lib/newsletterApi";
import { packePuzzle } from "@/lib/puzzle";

/** Ein Block des Newsletters: eine Rubrik (mit Einträgen) oder der KPI-Block. */
export type NewsletterBlock =
  | { art: "kpi"; data: BelegschaftKpi }
  | {
      art: "rubrik";
      rubrik: Rubrik;
      eintraege: Eintrag[];
      /** Nur „Menschen": Neuzugänge aus Personio (vor den Einträgen gezeigt). */
      neueMitarbeiter?: NeuerMitarbeiter[];
    };

/** Die Blöcke einer Ausgabe in gespeicherter Reihenfolge; leere Rubriken fallen
 *  raus. Der KPI-Block ist kein eigenständiger Block mehr: die KPIs gehören ins
 *  Kapitel „Intern" und werden als eigene Seite VOR den Intern-Einträgen
 *  eingefügt (ein evtl. altes "kpi" in block_reihenfolge wird ignoriert). */
export function ordereBloecke(a: AusgabeDetail): NewsletterBlock[] {
  const istRubrik = (k: string): k is Rubrik => (NEWSLETTER_RUBRIKEN as readonly string[]).includes(k);
  const reihenfolge = (a.block_reihenfolge ?? []).filter(istRubrik);
  for (const k of NEWSLETTER_RUBRIKEN) if (!reihenfolge.includes(k)) reihenfolge.push(k);

  const bloecke: NewsletterBlock[] = [];
  for (const k of reihenfolge) {
    // KPIs kommen als eigene Seite an den Anfang von „Intern".
    if (k === "intern" && a.kpi_snapshot) bloecke.push({ art: "kpi", data: a.kpi_snapshot });

    const eintraege = a.eintraege
      .filter((e) => e.rubrik === k)
      .sort((x, y) => x.reihenfolge - y.reihenfolge);
    // „Menschen": Neuzugänge aus Personio kommen vor die Einträge.
    const neueMitarbeiter = k === "menschen" ? a.neue_mitarbeiter ?? [] : [];
    if (eintraege.length || neueMitarbeiter.length)
      bloecke.push({ art: "rubrik", rubrik: k, eintraege, neueMitarbeiter });
  }
  return bloecke;
}

/** Bild von einem auth-gegateten Endpoint (Bearer nötig) → Blob → Object-URL.
 *  Rendert nichts, solange der Blob nicht geladen ist. */
export function AuthImageUrl({
  url,
  alt,
  className,
}: {
  url: string;
  alt: string;
  className?: string;
}) {
  const [obj, setObj] = useState<string | null>(null);
  useEffect(() => {
    let aktiv = true;
    let objUrl: string | null = null;
    fetchBlob(url)
      .then((b) => {
        if (!aktiv) return;
        objUrl = URL.createObjectURL(b);
        setObj(objUrl);
      })
      .catch(() => setObj(null));
    return () => {
      aktiv = false;
      if (objUrl) URL.revokeObjectURL(objUrl);
    };
  }, [url]);
  if (!obj) return null;
  return <img src={obj} alt={alt} className={className} />;
}

/** Bild eines Eintrags (auth-gegatet), im Inhalt eingebettet. */
export function AuthImage({ eintragId, alt }: { eintragId: number; alt: string }) {
  return (
    <AuthImageUrl
      url={bildUrl(eintragId)}
      alt={alt}
      className="my-2 max-h-72 w-auto max-w-full rounded-md border border-border object-contain"
    />
  );
}

/** Mehrere Bilder eines Eintrags als Raster-Puzzle (quadratische Zellen). */
export function PuzzleBilder({ bilder }: { bilder: EintragBild[] }) {
  if (!bilder.length) return null;
  const { platz, rows } = packePuzzle(bilder.map((b) => ({ spalten: b.spalten, zeilen: b.zeilen })));
  return (
    <div
      className="my-2 grid gap-1"
      style={{
        gridTemplateColumns: "repeat(4, 1fr)",
        gridTemplateRows: `repeat(${rows}, 1fr)`,
        aspectRatio: `4 / ${rows}`,
      }}
    >
      {bilder.map((b, i) => (
        <div
          key={b.id}
          className="relative overflow-hidden rounded"
          style={{
            gridColumn: `${platz[i].colStart} / span ${platz[i].spalten}`,
            gridRow: `${platz[i].rowStart} / span ${platz[i].zeilen}`,
          }}
        >
          <AuthImageUrl url={eintragBildUrl(b.id)} alt="" className="absolute inset-0 block h-full w-full object-cover" />
        </div>
      ))}
    </div>
  );
}

/** „Neu im Team" — Neuzugänge des Quartals aus Personio (Rubrik Menschen). */
function NeuImTeam({ leute }: { leute: NeuerMitarbeiter[] }) {
  const { t } = useTranslation();
  return (
    <div
      className="mb-4 break-inside-avoid rounded-md border border-border/60 p-3"
      style={{ borderLeft: `4px solid ${NL_BLUE}` }}
    >
      <h3 className="mb-1.5 text-base font-semibold" style={{ color: NL_OLIVE }}>
        {t("newsletter.neuImTeam")}
      </h3>
      <ul className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm sm:grid-cols-3">
        {leute.map((p, i) => (
          <li key={i} className="leading-tight">
            <span className="font-medium">{p.name}</span>
            {(p.abteilung || p.position) && (
              <span className="block text-xs text-muted-foreground">
                {p.abteilung || p.position}
              </span>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}

function EintragBlock({ eintrag }: { eintrag: Eintrag }) {
  return (
    <div className="mb-4 break-inside-avoid">
      <h3 className="mb-1 text-base font-semibold">{eintrag.untertitel}</h3>
      {eintrag.hat_bild && <AuthImage eintragId={eintrag.id} alt={eintrag.untertitel} />}
      <PuzzleBilder bilder={eintrag.bilder} />
      {eintrag.inhalt_md.trim() && (
        <div className="prose prose-sm max-w-none dark:prose-invert">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{eintrag.inhalt_md}</ReactMarkdown>
        </div>
      )}
    </div>
  );
}

/** Block-Schlüssel (Rubrik oder "kpi"). */
export function blockKey(block: NewsletterBlock): string {
  return block.art === "kpi" ? "kpi" : block.rubrik;
}

/** Titel eines Blocks: Override (rubrik_titel) sonst i18n-Standard. */
export function blockTitelText(
  block: NewsletterBlock,
  rubrikTitel: Record<string, string> | null | undefined,
  t: TFunction,
): string {
  const eigen = rubrikTitel?.[blockKey(block)]?.trim();
  return eigen || (block.art === "kpi" ? t("newsletter.kpiTitel") : t(`newsletter.rubrik.${block.rubrik}`));
}

/** Reiner Block-Inhalt (KPI-Charts bzw. Einträge) — den Titel liefert der
 *  Seiten-Rahmen ({@link SeiteRahmen}). `schmal` = Online-Hochformat. */
export function BlockInhalt({ block, schmal }: { block: NewsletterBlock; schmal?: boolean }) {
  if (block.art === "kpi") {
    return <BelegschaftKpiCharts data={block.data} compact schmal={schmal} />;
  }
  return (
    <>
      {block.neueMitarbeiter && block.neueMitarbeiter.length > 0 && (
        <NeuImTeam leute={block.neueMitarbeiter} />
      )}
      {/* Beiträge nebeneinander (zweispaltig); jeder Beitrag bleibt zusammen. */}
      <div className="columns-2 gap-x-5">
        {block.eintraege.map((e) => (
          <EintragBlock key={e.id} eintrag={e} />
        ))}
      </div>
    </>
  );
}

// --- Design-Skin (Referenz: Oliv/Gold + Blau-Akzent) ------------------------
export const NL_OLIVE = "#3e3a1d";
export const NL_OLIVE_DK = "#2a2711";
export const NL_BLUE = "#2f9fd9";

/** Skin einer Inhaltsseite: Oliv-Kopfband + zentrierter Titel mit blauen
 *  Akzent-Strichen + Fußzeile mit Seitenzahl. Größen in `cqw` (Container-Query-
 *  Einheiten) → skaliert proportional in PDF (945 px) und Buch (440 px). Füllt
 *  die quadratische Elternseite. */
export function SeiteRahmen({
  ausgabe,
  titel,
  seiteNr,
  edgeLabel,
  children,
}: {
  ausgabe: AusgabeDetail;
  titel: string;
  seiteNr: number;
  edgeLabel?: string;
  children: ReactNode;
}) {
  return (
    <div
      className="relative flex h-full w-full flex-col bg-white text-neutral-900"
      style={{ containerType: "inline-size" }}
    >
      <div
        className="flex items-center justify-between"
        style={{ background: NL_OLIVE, color: "#fff", padding: "3cqw 5cqw" }}
      >
        <span
          style={{
            border: "1px solid rgba(255,255,255,.55)",
            fontSize: "2.1cqw",
            letterSpacing: "0.22em",
            padding: "0.7cqw 1.8cqw",
            textTransform: "uppercase",
          }}
        >
          ACM Newsletter
        </span>
        <span style={{ fontSize: "2.1cqw", letterSpacing: "0.14em", opacity: 0.85 }}>
          {`Q${ausgabe.quartal} · ${ausgabe.jahr}`}
        </span>
      </div>
      <div className="text-center" style={{ paddingTop: "5cqw" }}>
        <div className="mx-auto" style={{ height: "0.7cqw", width: "9cqw", background: NL_BLUE }} />
        <h2 className="font-bold" style={{ fontSize: "6.2cqw", lineHeight: 1.05, margin: "2.4cqw 0", padding: "0 8cqw" }}>
          {titel}
        </h2>
        <div className="mx-auto" style={{ height: "0.7cqw", width: "9cqw", background: NL_BLUE }} />
      </div>
      <div className="min-h-0 flex-1 overflow-auto" style={{ padding: "4cqw 8.5cqw 7cqw 6cqw" }}>
        {children}
      </div>
      {edgeLabel && (
        <div style={{ position: "absolute", right: "1cqw", top: "15cqw", bottom: "6cqw", display: "flex", alignItems: "center" }}>
          <span style={{ writingMode: "vertical-rl", fontSize: "2.3cqw", letterSpacing: "0.34em", textTransform: "uppercase", fontWeight: 600, color: NL_BLUE }}>
            {edgeLabel}
          </span>
        </div>
      )}
      <div
        className="absolute flex items-center justify-between"
        style={{ left: "6cqw", right: "6cqw", bottom: "2.6cqw", fontSize: "1.9cqw", color: "#9aa3ad" }}
      >
        <span style={{ letterSpacing: "0.12em" }}>ACM · acm-aerospace.com</span>
        <span style={{ fontVariantNumeric: "tabular-nums" }}>{seiteNr}</span>
      </div>
    </div>
  );
}

/** Voll-Bleed Abschnitts-Trenner (Oliv) mit großem Titel + vertikalem Rand-Label. */
export function DividerSeite({ titel, edgeLabel }: { titel: string; edgeLabel?: string }) {
  return (
    <div
      className="relative flex h-full w-full items-center justify-center text-center text-white"
      style={{ containerType: "inline-size", background: `linear-gradient(150deg, ${NL_OLIVE}, ${NL_OLIVE_DK})` }}
    >
      <div style={{ padding: "0 10cqw" }}>
        <div className="mx-auto" style={{ height: "0.9cqw", width: "16cqw", background: NL_BLUE }} />
        <h2 style={{ fontSize: "9cqw", fontWeight: 800, lineHeight: 1.05, margin: "4cqw 0" }}>{titel}</h2>
        <div className="mx-auto" style={{ height: "0.9cqw", width: "16cqw", background: NL_BLUE }} />
      </div>
      {edgeLabel && (
        <div style={{ position: "absolute", right: "3cqw", top: "10cqw", bottom: "10cqw", display: "flex", alignItems: "center" }}>
          <span style={{ writingMode: "vertical-rl", fontSize: "2.4cqw", letterSpacing: "0.4em", textTransform: "uppercase", fontWeight: 600, color: "rgba(255,255,255,.8)" }}>
            {edgeLabel}
          </span>
        </div>
      )}
    </div>
  );
}

/** Cover-/Rückseite ohne Bild: Oliv-Verlauf + Masthead (Fallback). */
export function OliveMast({ ausgabe }: { ausgabe: AusgabeDetail }) {
  const { t } = useTranslation();
  const titel = ausgabe.titel || `Q${ausgabe.quartal} ${ausgabe.jahr}`;
  return (
    <div
      className="flex h-full w-full flex-col items-center justify-center text-center text-white"
      style={{ containerType: "inline-size", background: `linear-gradient(150deg, ${NL_OLIVE}, ${NL_OLIVE_DK})` }}
    >
      <div style={{ fontSize: "2.6cqw", letterSpacing: "0.3em", textTransform: "uppercase", opacity: 0.85 }}>
        {t("newsletter.kopf", { quartal: ausgabe.quartal, jahr: ausgabe.jahr })}
      </div>
      <div style={{ fontSize: "13cqw", fontWeight: 800, lineHeight: 1, margin: "3cqw 0 2.5cqw" }}>Newsletter</div>
      <div style={{ height: "0.9cqw", width: "16cqw", background: NL_BLUE }} />
      <div style={{ fontSize: "5cqw", fontWeight: 600, marginTop: "3cqw" }}>{titel}</div>
      <div style={{ fontSize: "2.4cqw", opacity: 0.8, marginTop: "6cqw", letterSpacing: "0.2em" }}>ACM</div>
    </div>
  );
}

/** Inhaltsverzeichnis-Seite (nach dem Cover). */
export function InhaltSeite({
  ausgabe,
  eintraege,
}: {
  ausgabe: AusgabeDetail;
  eintraege: { titel: string; seite: number }[];
}) {
  const { t } = useTranslation();
  return (
    <div
      className="flex h-full w-full flex-col text-white"
      style={{ containerType: "inline-size", background: `linear-gradient(150deg, ${NL_OLIVE}, ${NL_OLIVE_DK})` }}
    >
      <div style={{ padding: "9cqw 8cqw 0" }}>
        <div style={{ height: "0.7cqw", width: "9cqw", background: NL_BLUE }} />
        <h2 style={{ fontSize: "8cqw", fontWeight: 800, letterSpacing: "0.04em", margin: "2.4cqw 0 1cqw" }}>
          {t("newsletter.inhalt")}
        </h2>
        <div style={{ fontSize: "2.2cqw", opacity: 0.8, letterSpacing: "0.15em" }}>{`Q${ausgabe.quartal} · ${ausgabe.jahr}`}</div>
      </div>
      <div className="min-h-0 flex-1 overflow-auto" style={{ padding: "5cqw 8cqw" }}>
        {eintraege.map((e, i) => (
          <div
            key={i}
            className="flex items-baseline justify-between"
            style={{ padding: "2.1cqw 0", borderBottom: "1px solid rgba(255,255,255,.16)", fontSize: "3cqw" }}
          >
            <span>{e.titel}</span>
            <span style={{ color: NL_BLUE, fontWeight: 700, fontVariantNumeric: "tabular-nums" }}>{e.seite}</span>
          </div>
        ))}
      </div>
      <div style={{ padding: "0 8cqw 6cqw", fontSize: "2cqw", opacity: 0.7, letterSpacing: "0.12em" }}>
        ACM · acm-aerospace.com
      </div>
    </div>
  );
}

/** Ein Seiten-Deskriptor der Ausgabe (Cover, INHALT, Divider, Inhaltsseite, Back). */
export type SeiteDesc =
  | { art: "cover" }
  | { art: "inhalt"; toc: { titel: string; seite: number }[] }
  | { art: "divider"; titel: string; edgeLabel: string }
  | { art: "content"; block: NewsletterBlock; titel: string; edgeLabel: string; seiteNr: number }
  | { art: "back" };

/** Baut die flache Seitenfolge: Cover → INHALT → (Divider je Rubrik →) Inhalt je
 *  Block → Rückseite, inkl. Seitenzahlen. Vertikales Label = Rubrik-Kategorie. */
export function baueSeiten(ausgabe: AusgabeDetail, t: TFunction): SeiteDesc[] {
  const bloecke = ordereBloecke(ausgabe);
  const seiten: SeiteDesc[] = [{ art: "cover" }, { art: "inhalt", toc: [] }];
  const toc: { titel: string; seite: number }[] = [];
  for (const b of bloecke) {
    const titel = blockTitelText(b, ausgabe.rubrik_titel, t);
    const kategorie = b.art === "kpi" ? t("newsletter.rubrik.intern") : t(`newsletter.rubrik.${b.rubrik}`);
    const edge = kategorie.toUpperCase();
    if (b.art === "rubrik") seiten.push({ art: "divider", titel, edgeLabel: edge });
    const nr = seiten.length + 1; // 1-basierte Seite der gleich gepushten Inhaltsseite
    seiten.push({ art: "content", block: b, titel, edgeLabel: edge, seiteNr: nr });
    toc.push({ titel, seite: b.art === "rubrik" ? nr - 1 : nr }); // Divider-Seite bzw. Inhalt
  }
  seiten.push({ art: "back" });
  (seiten[1] as { art: "inhalt"; toc: { titel: string; seite: number }[] }).toc = toc;
  return seiten;
}

/** Rendert den Inhalt eines Seiten-Deskriptors (ohne den Seiten-Wrapper).
 *  `schmal` (Online-Hochformat) reicht bis zur KPI-Kachel durch. */
export function SeiteInhalt({
  desc,
  ausgabe,
  schmal,
}: {
  desc: SeiteDesc;
  ausgabe: AusgabeDetail;
  schmal?: boolean;
}) {
  const { t } = useTranslation();
  if (desc.art === "cover" || desc.art === "back") {
    const hat = desc.art === "cover" ? ausgabe.hat_cover : ausgabe.hat_rueck;
    const url = desc.art === "cover" ? coverUrl(ausgabe.id) : rueckUrl(ausgabe.id);
    return hat ? (
      <AuthImageUrl
        url={url}
        alt={t(desc.art === "cover" ? "newsletter.titelbild" : "newsletter.rueckseitenbild")}
        className="absolute inset-0 block h-full w-full object-contain"
      />
    ) : (
      <OliveMast ausgabe={ausgabe} />
    );
  }
  if (desc.art === "inhalt") return <InhaltSeite ausgabe={ausgabe} eintraege={desc.toc} />;
  if (desc.art === "divider") return <DividerSeite titel={desc.titel} edgeLabel={desc.edgeLabel} />;
  return (
    <SeiteRahmen ausgabe={ausgabe} titel={desc.titel} seiteNr={desc.seiteNr} edgeLabel={desc.edgeLabel}>
      <BlockInhalt block={desc.block} schmal={schmal} />
    </SeiteRahmen>
  );
}

/** Seitenweise Ansicht — je Deskriptor eine quadratische Seite (945 px = 250 mm)
 *  im Referenz-Design (Oliv-Kopfband, Divider je Rubrik, vertikale Rand-Labels,
 *  INHALT, Seitenzahlen). Jede trägt `data-pdf-page` für den seitenweisen Export
 *  ({@link exportNewsletterPdf}). */
export function NewsletterPdfPages({ ausgabe }: { ausgabe: AusgabeDetail }) {
  const { t } = useTranslation();
  const seiten = baueSeiten(ausgabe, t);
  return (
    <div className="flex flex-col items-center gap-4">
      {seiten.map((desc, i) => (
        <div
          key={i}
          data-pdf-page
          style={{ width: 945, height: 945 }}
          className="relative overflow-hidden bg-[#3e3a1d]"
        >
          <SeiteInhalt desc={desc} ausgabe={ausgabe} />
        </div>
      ))}
    </div>
  );
}
