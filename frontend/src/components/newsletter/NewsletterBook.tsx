import { useRef } from "react";
import { useTranslation } from "react-i18next";
// @ts-expect-error - react-pageflip liefert keine vollständigen Typen
import HTMLFlipBook from "react-pageflip";
import { ChevronLeft, ChevronRight } from "lucide-react";
import {
  AuthImageUrl,
  BlockInhalt,
  InhaltSeite,
  OliveMast,
  SeiteRahmen,
  blockTitelText,
  ordereBloecke,
} from "./NewsletterView";
import { coverUrl, rueckUrl, type AusgabeDetail } from "@/lib/newsletterApi";

/** Online-Newsletter als Blätter-Buch (react-pageflip) mit Umblätter-Animation. */
export function NewsletterBook({ ausgabe }: { ausgabe: AusgabeDetail }) {
  const { t } = useTranslation();
  const book = useRef<{ pageFlip: () => { flipNext: () => void; flipPrev: () => void } } | null>(null);
  const bloecke = ordereBloecke(ausgabe);
  const inhalt = bloecke.map((b, i) => ({ titel: blockTitelText(b, ausgabe.rubrik_titel, t), seite: 3 + i }));

  const seiten = [
    <div key="cover" className="relative h-full overflow-hidden bg-neutral-200">
      {ausgabe.hat_cover ? (
        <AuthImageUrl url={coverUrl(ausgabe.id)} alt={t("newsletter.titelbild")} className="absolute inset-0 block h-full w-full object-cover" />
      ) : (
        <OliveMast ausgabe={ausgabe} />
      )}
    </div>,
    <div key="inhalt" className="h-full overflow-hidden">
      <InhaltSeite ausgabe={ausgabe} eintraege={inhalt} />
    </div>,
    ...bloecke.map((b, i) => (
      <div key={i} className="h-full overflow-hidden">
        <SeiteRahmen ausgabe={ausgabe} titel={blockTitelText(b, ausgabe.rubrik_titel, t)} seiteNr={3 + i}>
          <BlockInhalt block={b} />
        </SeiteRahmen>
      </div>
    )),
    <div key="back" className="relative h-full overflow-hidden bg-neutral-200">
      {ausgabe.hat_rueck ? (
        <AuthImageUrl url={rueckUrl(ausgabe.id)} alt={t("newsletter.rueckseitenbild")} className="absolute inset-0 block h-full w-full object-cover" />
      ) : (
        <OliveMast ausgabe={ausgabe} />
      )}
    </div>,
  ];

  return (
    <div className="flex flex-col items-center gap-3">
      <HTMLFlipBook
        width={440}
        height={440}
        size="stretch"
        minWidth={260}
        maxWidth={480}
        minHeight={260}
        maxHeight={480}
        showCover
        maxShadowOpacity={0.35}
        drawShadow
        flippingTime={700}
        usePortrait={false}
        mobileScrollSupport
        className="nl-book shadow-xl"
        ref={book}
      >
        {seiten}
      </HTMLFlipBook>

      <div className="flex items-center gap-2">
        <button
          type="button"
          onClick={() => book.current?.pageFlip()?.flipPrev()}
          className="inline-flex h-8 items-center gap-1 rounded-md border border-input px-3 text-xs
                     hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <ChevronLeft className="h-3.5 w-3.5" /> {t("newsletter.zurueckblaettern")}
        </button>
        <button
          type="button"
          onClick={() => book.current?.pageFlip()?.flipNext()}
          className="inline-flex h-8 items-center gap-1 rounded-md border border-input px-3 text-xs
                     hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {t("newsletter.weiterblaettern")} <ChevronRight className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}
