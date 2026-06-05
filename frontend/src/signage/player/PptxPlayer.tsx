import { useEffect, useRef, useState } from "react";

export interface PptxPlayerProps {
  slidePaths: string[] | null;
  /** Seconds each slide is shown. The total visible time per playlist item is
   *  durationS * slidePaths.length. */
  durationS: number;
  /** Optional. Fired after the last slide has been shown for `durationS` seconds.
   *  When provided, PptxPlayer freezes on the last slide rather than looping —
   *  the parent decides what comes next (e.g. advance to the next playlist item).
   *  Without it, the player loops back to the first slide. */
  onCycleEnd?: () => void;
}

export function PptxPlayer({ slidePaths, durationS, onCycleEnd }: PptxPlayerProps) {
  const [index, setIndex] = useState(0);
  const paths = slidePaths ?? [];
  // Latest onCycleEnd in a ref so the cycle effect doesn't re-subscribe (which
  // would reset the timer) when the callback identity changes between renders.
  const onCycleEndRef = useRef(onCycleEnd);
  useEffect(() => {
    onCycleEndRef.current = onCycleEnd;
  }, [onCycleEnd]);

  // Identity of the slide deck IGNORING query strings — the per-slide URLs
  // carry the rotating device token (`?token=…`), so the array identity
  // changes every ~60 s. Resetting `index` on every such churn would trap the
  // kiosk on the first slide forever instead of cycling. Compare base paths.
  const pathsKey = paths.map((p) => p.split("?")[0]).join("|");

  // Reset to slide 1 whenever the slide SET actually changes (new item or
  // reconvert), not when only the token changed.
  useEffect(() => {
    setIndex(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathsKey]);

  useEffect(() => {
    if (paths.length === 0) return;
    const perSlide = Math.max(1000, durationS * 1000);
    const id = window.setTimeout(() => {
      const isLast = index + 1 >= paths.length;
      if (isLast) {
        if (onCycleEndRef.current) {
          onCycleEndRef.current();
        } else {
          setIndex(0);
        }
      } else {
        setIndex(index + 1);
      }
    }, perSlide);
    return () => window.clearTimeout(id);
  }, [paths, durationS, index]);

  if (paths.length === 0) return null;
  return <img src={paths[index]} alt="" className="w-full h-full object-contain" />;
}
