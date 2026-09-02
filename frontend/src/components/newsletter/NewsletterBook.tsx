import { useRef, type ComponentType } from "react";
import { useTranslation } from "react-i18next";
import HTMLFlipBookImport from "react-pageflip";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { SeiteInhalt, baueSeiten } from "./NewsletterView";
import { type AusgabeDetail } from "@/lib/newsletterApi";

// react-pageflip liefert unvollständige Prop-Typen — als permissive Komponente casten.
const HTMLFlipBook = HTMLFlipBookImport as unknown as ComponentType<Record<string, unknown>>;

/** Online-Newsletter als Blätter-Buch (react-pageflip) mit Umblätter-Animation. */
export function NewsletterBook({ ausgabe }: { ausgabe: AusgabeDetail }) {
  const { t } = useTranslation();
  const book = useRef<{ pageFlip: () => { flipNext: () => void; flipPrev: () => void } } | null>(null);

  const seiten = baueSeiten(ausgabe, t).map((desc, i) => (
    <div key={i} className="relative h-full overflow-hidden bg-[#3e3a1d]">
      <SeiteInhalt desc={desc} ausgabe={ausgabe} schmal />
    </div>
  ));

  return (
    <div className="flex flex-col items-center gap-3">
      <HTMLFlipBook
        width={430}
        height={608}
        size="stretch"
        minWidth={300}
        maxWidth={470}
        minHeight={424}
        maxHeight={664}
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
