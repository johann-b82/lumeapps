/**
 * SVG overlay in natural page units (viewBox 0 0 pageW pageH). Sits inside the
 * same transformed wrapper as the drawing, so balloons scale/pan in lock-step.
 * The svg itself is click-through (pointer-events none) — only balloon handles
 * re-enable events; marking/panning are handled by the viewport underneath.
 */
import { Balloon } from "./Balloon";
import { FAIR_COLORS } from "./geometry";
import type { NormRect, Point, Rotation } from "./geometry";
import type { FairBalloon } from "@/lib/fairApi";

interface BalloonLayerProps {
  pageW: number;
  pageH: number;
  sizeScale: number;
  rotation: Rotation;
  balloons: readonly FairBalloon[];
  markRect: NormRect | null;
  selectedId: string | null;
  clientToNorm: (clientX: number, clientY: number) => Point;
  onSelect: (id: string) => void;
  onTailChange: (id: string, tail: Point, commit: boolean) => void;
}

export function BalloonLayer({
  pageW,
  pageH,
  sizeScale,
  rotation,
  balloons,
  markRect,
  selectedId,
  clientToNorm,
  onSelect,
  onTailChange,
}: BalloonLayerProps) {
  const sw = Math.max(1, Math.min(pageW, pageH) * 0.003);
  return (
    <svg
      width={pageW}
      height={pageH}
      viewBox={`0 0 ${pageW} ${pageH}`}
      style={{ position: "absolute", inset: 0, pointerEvents: "none" }}
    >
      {balloons.map((b) => (
        <Balloon
          key={b.id}
          balloon={b}
          pageW={pageW}
          pageH={pageH}
          sizeScale={sizeScale}
          rotation={rotation}
          selected={selectedId === b.id}
          clientToNorm={clientToNorm}
          onSelect={onSelect}
          onTailChange={onTailChange}
        />
      ))}
      {markRect && (
        <rect
          x={markRect.x * pageW}
          y={markRect.y * pageH}
          width={markRect.w * pageW}
          height={markRect.h * pageH}
          fill={FAIR_COLORS.region}
          fillOpacity={0.12}
          stroke={FAIR_COLORS.region}
          strokeWidth={sw * 1.5}
          strokeDasharray={`${sw * 3} ${sw * 3}`}
        />
      )}
    </svg>
  );
}
