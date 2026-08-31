import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
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
  mitarbeiterFotoUrl,
  rueckUrl,
  type AusgabeDetail,
  type Eintrag,
  type EintragBild,
  type NeuerMitarbeiter,
} from "@/lib/newsletterApi";
import { packePuzzle } from "@/lib/puzzle";

/** Ein Block des Newsletters: eine Rubrik (mit Einträgen) oder der KPI-Block. */
export type NewsletterBlock =
  | { art: "kpi"; data: BelegschaftKpi }
  | {
      art: "rubrik";
      /** Standard-Rubrik oder ein Ausgabe-eigener Kapitel-Schlüssel. */
      rubrik: string;
      eintraege: Eintrag[];
      /** Nur „Menschen": Neuzugänge aus Personio (vor den Einträgen gezeigt). */
      neueMitarbeiter?: NeuerMitarbeiter[];
    };

/** Die Blöcke einer Ausgabe in gespeicherter Reihenfolge; leere Rubriken fallen
 *  raus. Der KPI-Block ist kein eigenständiger Block mehr: die KPIs gehören ins
 *  Kapitel „Intern" und werden als eigene Seite VOR den Intern-Einträgen
 *  eingefügt (ein evtl. altes "kpi" in block_reihenfolge wird ignoriert). */
export function ordereBloecke(a: AusgabeDetail): NewsletterBlock[] {
  // block_reihenfolge ist maßgeblich: Teilmenge der Standard-Sechs = entfernt,
  // Custom-Keys erlaubt; null → die Standard-Sechs. „kpi" ist kein Kapitel
  // (wird als eigene Seite VOR „Intern" injiziert).
  const reihenfolge = (a.block_reihenfolge ?? [...NEWSLETTER_RUBRIKEN]).filter((k) => k !== "kpi");

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
      className="mb-2 mx-auto block max-h-40 w-auto max-w-full rounded-lg border border-border shadow-sm"
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

/** Personio-Profilfoto (rund) mit Initialen-Fallback, falls kein Foto vorliegt. */
function MitarbeiterFoto({ id, name }: { id: number; name: string }) {
  const [obj, setObj] = useState<string | null>(null);
  useEffect(() => {
    let aktiv = true;
    let u: string | null = null;
    fetchBlob(mitarbeiterFotoUrl(id))
      .then((b) => {
        if (!aktiv) return;
        u = URL.createObjectURL(b);
        setObj(u);
      })
      .catch(() => {
        if (aktiv) setObj(null);
      });
    return () => {
      aktiv = false;
      if (u) URL.revokeObjectURL(u);
    };
  }, [id]);
  if (obj) {
    return (
      <img
        src={obj}
        alt=""
        className="h-10 w-10 shrink-0 rounded-full border border-border object-cover"
      />
    );
  }
  const initialen = name
    .split(/\s+/)
    .filter(Boolean)
    .map((w) => w[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();
  return (
    <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-border bg-muted text-[0.7rem] font-semibold text-muted-foreground">
      {initialen}
    </span>
  );
}

/** „Neu im Team" — Neuzugänge des Quartals aus Personio (mit Foto, Rubrik Menschen). */
function NeuImTeam({ leute }: { leute: NeuerMitarbeiter[] }) {
  const { t } = useTranslation();
  return (
    <div
      className="mb-5 break-inside-avoid rounded-md border border-border/60 p-3"
      style={{ borderLeft: `4px solid ${NL_BLUE}` }}
    >
      <h3 className="mb-2 text-base font-semibold" style={{ color: NL_OLIVE }}>
        {t("newsletter.neuImTeam")}
      </h3>
      <ul className="grid grid-cols-2 gap-x-4 gap-y-2.5 sm:grid-cols-3">
        {leute.map((p) => (
          <li key={p.employee_id} className="flex items-center gap-2">
            <MitarbeiterFoto id={p.employee_id} name={p.name} />
            <div className="min-w-0 leading-tight">
              <div className="truncate text-sm font-medium">{p.name}</div>
              {(p.abteilung || p.position) && (
                <div className="truncate text-xs text-muted-foreground">
                  {p.abteilung || p.position}
                </div>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Editorial-Beitrag: Bild oben (vollflächig), großer Titel mit blauem Kicker,
 *  Lead-Absatz betont — Magazin-Anmutung wie im Referenz-Newsletter. */
function EintragBlock({ eintrag }: { eintrag: Eintrag }) {
  return (
    <div className="mb-6 break-inside-avoid">
      {eintrag.hat_bild && <AuthImage eintragId={eintrag.id} alt={eintrag.untertitel} />}
      <PuzzleBilder bilder={eintrag.bilder} />
      <div className="mt-2">
        <div
          className="mb-1"
          style={{ height: "0.55cqw", minHeight: 3, width: "6cqw", minWidth: 26, background: NL_BLUE }}
        />
        <h3 className="font-bold leading-tight" style={{ fontSize: "3.6cqw", color: NL_OLIVE }}>
          {eintrag.untertitel}
        </h3>
      </div>
      {eintrag.inhalt_md.trim() && (
        <div className="prose prose-sm mt-2 max-w-none dark:prose-invert [&_p:first-of-type]:font-medium [&_p:first-of-type]:text-neutral-800">
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
  if (eigen) return eigen;
  if (block.art === "kpi") return t("newsletter.kpiTitel");
  // Custom-Kapitel haben keinen i18n-Standardtitel → Schlüssel als Fallback.
  return (NEWSLETTER_RUBRIKEN as readonly string[]).includes(block.rubrik)
    ? t(`newsletter.rubrik.${block.rubrik}`)
    : block.rubrik;
}

/** Reiner Block-Inhalt (KPI-Charts bzw. Einträge) — den Titel liefert der
 *  Seiten-Rahmen ({@link SeiteRahmen}). `schmal` = Online-Hochformat. */
export function BlockInhalt({ block, schmal }: { block: NewsletterBlock; schmal?: boolean }) {
  if (block.art === "kpi") {
    return <BelegschaftKpiCharts data={block.data} compact schmal={schmal} />;
  }
  const neu = block.neueMitarbeiter?.length ? (
    <NeuImTeam leute={block.neueMitarbeiter} />
  ) : null;

  // Online-Hochformat: einspaltig. PDF (breit): zwei feste Spalten, wobei jeder
  // Beitrag KOMPLETT in seiner Spalte bleibt (kein CSS-Mehrspalten-Umbruch, der
  // Beiträge zerreißt/überlappt). Verteilung abwechselnd → ausgewogene Höhen.
  if (schmal) {
    return (
      <>
        {neu}
        {block.eintraege.map((e) => (
          <EintragBlock key={e.id} eintrag={e} />
        ))}
      </>
    );
  }
  const links = block.eintraege.filter((_, i) => i % 2 === 0);
  const rechts = block.eintraege.filter((_, i) => i % 2 === 1);
  return (
    <>
      {neu}
      <div className="flex items-start gap-5">
        <div className="min-w-0 flex-1">
          {links.map((e) => (
            <EintragBlock key={e.id} eintrag={e} />
          ))}
        </div>
        <div className="min-w-0 flex-1">
          {rechts.map((e) => (
            <EintragBlock key={e.id} eintrag={e} />
          ))}
        </div>
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
      <div className="text-center" style={{ paddingTop: "7cqw" }}>
        <div className="mx-auto" style={{ height: "0.9cqw", width: "13cqw", background: NL_BLUE }} />
        <h2
          className="font-bold"
          style={{
            fontSize: "9.5cqw",
            lineHeight: 1.02,
            margin: "3.4cqw 0",
            padding: "0 6cqw",
            textWrap: "balance",
          }}
        >
          {titel}
        </h2>
        <div className="mx-auto" style={{ height: "0.9cqw", width: "13cqw", background: NL_BLUE }} />
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
/** Max. Einträge pro Inhaltsseite — mehr Einträge laufen unter demselben Titel
 *  auf Folgeseiten (ausgewogen verteilt). */
const MAX_EINTRAEGE_PRO_SEITE = 6;

export function baueSeiten(ausgabe: AusgabeDetail, t: TFunction): SeiteDesc[] {
  const bloecke = ordereBloecke(ausgabe);
  const seiten: SeiteDesc[] = [{ art: "cover" }, { art: "inhalt", toc: [] }];
  const toc: { titel: string; seite: number }[] = [];
  for (const b of bloecke) {
    const titel = blockTitelText(b, ausgabe.rubrik_titel, t);
    const kategorie =
      b.art === "kpi"
        ? t("newsletter.rubrik.intern")
        : (NEWSLETTER_RUBRIKEN as readonly string[]).includes(b.rubrik)
          ? t(`newsletter.rubrik.${b.rubrik}`)
          : titel;
    const edge = kategorie.toUpperCase();
    // Der Titel steht im Seitenrahmen der Inhaltsseite (keine eigene Trennseite).

    if (b.art === "kpi") {
      const nr = seiten.length + 1;
      seiten.push({ art: "content", block: b, titel, edgeLabel: edge, seiteNr: nr });
      toc.push({ titel, seite: nr });
      continue;
    }

    // Rubrik: Einträge ausgewogen auf so wenige Seiten wie nötig verteilen.
    // Der „Neu im Team"-Block kommt nur auf die erste Seite.
    const anzahl = Math.max(1, Math.ceil(b.eintraege.length / MAX_EINTRAEGE_PRO_SEITE));
    const proSeite = Math.ceil(b.eintraege.length / anzahl);
    for (let sN = 0; sN < anzahl; sN++) {
      const teilBlock: NewsletterBlock = {
        art: "rubrik",
        rubrik: b.rubrik,
        eintraege: b.eintraege.slice(sN * proSeite, (sN + 1) * proSeite),
        neueMitarbeiter: sN === 0 ? b.neueMitarbeiter : [],
      };
      const nr = seiten.length + 1;
      seiten.push({ art: "content", block: teilBlock, titel, edgeLabel: edge, seiteNr: nr });
      if (sN === 0) toc.push({ titel, seite: nr });
    }
  }
  seiten.push({ art: "back" });
  (seiten[1] as { art: "inhalt"; toc: { titel: string; seite: number }[] }).toc = toc;
  return seiten;
}

/** Skaliert den Inhalt so, dass er die feste Seitenhöhe füllt — bei wenig Inhalt
 *  größer, bei viel kleiner. Selbstjustierend (Fixpunkt: sichtbare Höhe →
 *  verfügbare Höhe), geclampt. Breiten-Kompensation hält die sichtbare Breite bei
 *  100 %; `transform: scale` ändert nur die Optik, nicht das Layout/scrollHeight. */
function FitToPage({ children }: { children: ReactNode }) {
  const aussen = useRef<HTMLDivElement>(null);
  const innen = useRef<HTMLDivElement>(null);
  const [scale, setScale] = useState(1);
  useLayoutEffect(() => {
    const a = aussen.current;
    const i = innen.current;
    if (!a || !i) return;
    let raf = 0;
    // Skalierung so bestimmen, dass die sichtbare Höhe die Seite füllt.
    // (Fixpunkt-Iteration; `width = 100/s%` kompensiert den Transform.)
    const mess = () => {
      const verfuegbar = a.clientHeight;
      if (verfuegbar <= 8) return;
      let s = 1;
      for (let k = 0; k < 6; k++) {
        i.style.width = `${100 / s}%`;
        const natuerlich = i.scrollHeight;
        if (natuerlich <= 8) break;
        const ziel = Math.min(2.0, Math.max(0.6, verfuegbar / natuerlich));
        if (Math.abs(ziel - s) < 0.01) {
          s = ziel;
          break;
        }
        s = ziel;
      }
      // Schluss-Korrektur gegen Beschnitt (bild-lastiger Inhalt konvergiert nicht
      // exakt): finale Höhe messen, s nötigenfalls senken.
      i.style.width = `${100 / s}%`;
      const final_nat = i.scrollHeight;
      if (final_nat > 8 && final_nat * s > verfuegbar) {
        s = Math.max(0.6, verfuegbar / final_nat);
      }
      i.style.width = `${100 / s}%`;
      setScale(s);
    };
    // Nachmessen (entprellt), wenn sich Inhalt/Höhe ändert — z. B. wenn Bilder
    // asynchron nachladen. rAF verhindert die ResizeObserver-Schleife.
    const plan = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(mess);
    };
    mess();
    const ro = new ResizeObserver(plan);
    ro.observe(i);
    ro.observe(a);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);
  return (
    <div ref={aussen} className="h-full overflow-hidden">
      <div
        ref={innen}
        style={{ width: `${100 / scale}%`, transform: `scale(${scale})`, transformOrigin: "top left" }}
      >
        {children}
      </div>
    </div>
  );
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
  const inhalt = <BlockInhalt block={desc.block} schmal={schmal} />;
  return (
    <SeiteRahmen ausgabe={ausgabe} titel={desc.titel} seiteNr={desc.seiteNr} edgeLabel={desc.edgeLabel}>
      {/* Fit-to-Page NUR im PDF (feste Seiten): Rubrik-Inhalte füllen die Seite.
          Online-Hochformat (schmal, scrollend) bleibt unskaliert; KPI-Charts
          messen sich selbst und werden nie skaliert. */}
      {desc.block.art === "rubrik" && !schmal ? <FitToPage>{inhalt}</FitToPage> : inhalt}
    </SeiteRahmen>
  );
}

/** Seitenweise Ansicht — je Deskriptor eine Seite im A4-Hochformat (945×1337 px
 *  ≈ 210×297 mm), passend zum Online-Buch. Oliv-Kopfband, vertikale Rand-Labels,
 *  INHALT, Seitenzahlen. Jede trägt `data-pdf-page` für den seitenweisen Export
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
          style={{ width: 945, height: 1337 }}
          className="relative overflow-hidden bg-[#3e3a1d]"
        >
          <SeiteInhalt desc={desc} ausgabe={ausgabe} />
        </div>
      ))}
    </div>
  );
}
