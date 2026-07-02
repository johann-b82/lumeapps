/**
 * Zoom/pan state for the FAIR editor viewport. Holds a single
 * `translate(tx,ty) scale(s)` transform applied to the wrapper that contains
 * BOTH the drawing and the SVG overlay, so they scale/pan in lock-step.
 * Wheel = zoom toward the cursor; panning is driven by the canvas in pan mode.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import type { RefObject } from "react";
import { fitTransform, zoomAround } from "./geometry";
import type { Transform } from "./geometry";

export interface Natural {
  w: number;
  h: number;
}

export function useZoomPan<T extends HTMLElement>(
  viewportRef: RefObject<T | null>,
  natural: Natural | null,
) {
  const [transform, setTransform] = useState<Transform>({
    scale: 1,
    tx: 0,
    ty: 0,
  });
  // Guard so we only auto-fit once per drawing (not on every resize, which
  // would fight the user's manual zoom).
  const fittedFor = useRef<string>("");

  const fit = useCallback(() => {
    const el = viewportRef.current;
    if (!el || !natural) return;
    const rect = el.getBoundingClientRect();
    setTransform(fitTransform(rect.width, rect.height, natural.w, natural.h));
  }, [viewportRef, natural]);

  // Auto-fit when a new drawing's natural size becomes known.
  useEffect(() => {
    if (!natural) return;
    const key = `${natural.w}x${natural.h}`;
    if (fittedFor.current === key) return;
    fittedFor.current = key;
    fit();
  }, [natural, fit]);

  // Wheel = zoom toward the cursor. Non-passive so preventDefault works (React's
  // onWheel is passive, so we attach manually).
  useEffect(() => {
    const el = viewportRef.current;
    if (!el) return;
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const rect = el.getBoundingClientRect();
      const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
      setTransform((t) =>
        zoomAround(t, e.clientX - rect.left, e.clientY - rect.top, factor),
      );
    };
    el.addEventListener("wheel", onWheel, { passive: false });
    return () => el.removeEventListener("wheel", onWheel);
  }, [viewportRef]);

  const zoomByButton = useCallback(
    (factor: number) => {
      const el = viewportRef.current;
      if (!el) return;
      const rect = el.getBoundingClientRect();
      setTransform((t) => zoomAround(t, rect.width / 2, rect.height / 2, factor));
    },
    [viewportRef],
  );

  return { transform, setTransform, fit, zoomByButton };
}
