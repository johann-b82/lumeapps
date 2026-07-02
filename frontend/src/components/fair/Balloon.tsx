/**
 * One numbered bubble-arrow, drawn in natural page units inside the SVG overlay.
 * The circle is the drag handle: dragging updates the tail through the same
 * screen→normalized transform, so it is zoom-invariant. Only the tail moves;
 * the tip (region centre) is fixed and the arrow re-aims automatically.
 */
import { useRef } from "react";
import { balloonPixels, FAIR_COLORS } from "./geometry";
import type { Point, Rotation } from "./geometry";
import type { FairBalloon } from "@/lib/fairApi";

interface BalloonProps {
  balloon: FairBalloon;
  pageW: number;
  pageH: number;
  sizeScale: number;
  /** View rotation — the number is counter-rotated so it stays upright. */
  rotation: Rotation;
  selected: boolean;
  clientToNorm: (clientX: number, clientY: number) => Point;
  onSelect: (id: string) => void;
  onTailChange: (id: string, tail: Point, commit: boolean) => void;
}

export function Balloon({
  balloon,
  pageW,
  pageH,
  sizeScale,
  rotation,
  selected,
  clientToNorm,
  onSelect,
  onTailChange,
}: BalloonProps) {
  const dragging = useRef(false);
  const g = balloonPixels(balloon, pageW, pageH, sizeScale);
  const sw = Math.max(1, g.r * 0.14);

  const handlePointerDown = (e: React.PointerEvent) => {
    // Only the left button drags a bubble; let right-drag bubble up to pan.
    if (e.button !== 0) return;
    e.stopPropagation();
    e.preventDefault();
    (e.target as Element).setPointerCapture(e.pointerId);
    dragging.current = true;
    onSelect(balloon.id);
  };
  const handlePointerMove = (e: React.PointerEvent) => {
    if (!dragging.current) return;
    e.stopPropagation();
    onTailChange(balloon.id, clientToNorm(e.clientX, e.clientY), false);
  };
  const endDrag = (e: React.PointerEvent) => {
    if (!dragging.current) return;
    dragging.current = false;
    e.stopPropagation();
    try {
      (e.target as Element).releasePointerCapture(e.pointerId);
    } catch {
      /* pointer already released */
    }
    onTailChange(balloon.id, clientToNorm(e.clientX, e.clientY), true);
  };

  return (
    <g>
      {/* Marked region — the area the value was read from. */}
      <rect
        x={g.region.x}
        y={g.region.y}
        width={g.region.w}
        height={g.region.h}
        fill="none"
        stroke={FAIR_COLORS.region}
        strokeOpacity={selected ? 0.9 : 0.45}
        strokeWidth={sw}
      />
      {/* Solid wedge leader (behind the bubble) pointing at the region. */}
      <polygon points={g.arrowPoints} fill={FAIR_COLORS.stroke} />
      <circle
        cx={g.tail.x}
        cy={g.tail.y}
        r={g.r}
        fill={FAIR_COLORS.bubbleFill}
        stroke={FAIR_COLORS.stroke}
        strokeWidth={selected ? sw * 1.8 : sw}
        style={{ cursor: "grab", pointerEvents: "auto" }}
        onPointerDown={handlePointerDown}
        onPointerMove={handlePointerMove}
        onPointerUp={endDrag}
        onPointerCancel={endDrag}
      />
      <text
        x={g.tail.x}
        y={g.tail.y}
        transform={
          rotation ? `rotate(${-rotation} ${g.tail.x} ${g.tail.y})` : undefined
        }
        fontFamily="Arial, Helvetica, sans-serif"
        fontSize={g.fontSize}
        fontWeight="bold"
        fill={FAIR_COLORS.text}
        textAnchor="middle"
        dominantBaseline="central"
        style={{ pointerEvents: "none", userSelect: "none" }}
      >
        {balloon.number}
      </text>
    </g>
  );
}
