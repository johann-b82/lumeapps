import { describe, expect, it } from "vitest";
import {
  asRotation,
  balloonPixels,
  buildCsv,
  buildTsv,
  clamp01,
  fitTransform,
  invRotatePx,
  normToScreen,
  rectExitPoint,
  rectFromCorners,
  regionCenter,
  rotatePx,
  sanitizeFilename,
  rotatedDims,
  screenToNorm,
  zoomAround,
} from "./geometry";
import type { Rotation } from "./geometry";
import type { FairBalloon } from "@/lib/fairApi";

const NAT_W = 800;
const NAT_H = 600;

function makeBalloon(over: Partial<FairBalloon> = {}): FairBalloon {
  return {
    id: "b1",
    number: 1,
    page_no: 1,
    region_x: 0.4,
    region_y: 0.4,
    region_w: 0.1,
    region_h: 0.05,
    tail_x: 0.7,
    tail_y: 0.8,
    value_text: "Ø12,5",
    ...over,
  };
}

describe("clamp01", () => {
  it("clamps out-of-range values", () => {
    expect(clamp01(-0.2)).toBe(0);
    expect(clamp01(1.5)).toBe(1);
    expect(clamp01(0.3)).toBe(0.3);
  });
});

describe("screenToNorm / normToScreen", () => {
  it("round-trips regardless of zoom/pan", () => {
    const t = { scale: 2.5, tx: 40, ty: -30 };
    const norm = { x: 0.37, y: 0.62 };
    const screen = normToScreen(norm, t, NAT_W, NAT_H);
    const back = screenToNorm(screen.x, screen.y, t, NAT_W, NAT_H);
    expect(back.x).toBeCloseTo(norm.x, 6);
    expect(back.y).toBeCloseTo(norm.y, 6);
  });

  it("maps the same drawing point to the same norm under different transforms", () => {
    // A fixed drawing point at norm (0.5, 0.5) must resolve identically no
    // matter the zoom — proves balloons are zoom-invariant.
    const p = { x: 0.5, y: 0.5 };
    const t1 = { scale: 1, tx: 0, ty: 0 };
    const t2 = { scale: 4, tx: 123, ty: 77 };
    const s1 = normToScreen(p, t1, NAT_W, NAT_H);
    const s2 = normToScreen(p, t2, NAT_W, NAT_H);
    expect(screenToNorm(s1.x, s1.y, t1, NAT_W, NAT_H).x).toBeCloseTo(0.5, 6);
    expect(screenToNorm(s2.x, s2.y, t2, NAT_W, NAT_H).x).toBeCloseTo(0.5, 6);
  });
});

describe("zoomAround", () => {
  it("keeps the anchor point stationary in screen space", () => {
    const t = { scale: 1, tx: 0, ty: 0 };
    const anchor = { x: 300, y: 200 };
    // The drawing point currently under the anchor.
    const before = screenToNorm(anchor.x, anchor.y, t, NAT_W, NAT_H);
    const zoomed = zoomAround(t, anchor.x, anchor.y, 2);
    const after = normToScreen(before, zoomed, NAT_W, NAT_H);
    expect(after.x).toBeCloseTo(anchor.x, 4);
    expect(after.y).toBeCloseTo(anchor.y, 4);
  });
});

describe("rectFromCorners", () => {
  it("normalizes corner order", () => {
    const r = rectFromCorners({ x: 0.6, y: 0.7 }, { x: 0.4, y: 0.5 });
    expect(r).toEqual({ x: 0.4, y: 0.5, w: expect.closeTo(0.2, 6), h: expect.closeTo(0.2, 6) });
  });
});

describe("regionCenter", () => {
  it("computes the normalized region centre", () => {
    const c = regionCenter(makeBalloon());
    expect(c.x).toBeCloseTo(0.45, 6);
    expect(c.y).toBeCloseTo(0.425, 6);
  });
});

describe("rectExitPoint / balloonPixels tip outside region", () => {
  it("exits the side facing the target, pushed out by the gap", () => {
    // rect centre (100,100), half 20×10; target far left → exits left edge.
    const tip = rectExitPoint(100, 100, 20, 10, { x: -100, y: 100 }, 5);
    expect(tip.y).toBeCloseTo(100, 6);
    expect(tip.x).toBeCloseTo(75, 6); // left edge 80, minus 5 gap
    expect(tip.x).toBeLessThan(80); // strictly outside the rect
  });

  it("exits the top edge when the target is above", () => {
    const tip = rectExitPoint(100, 100, 20, 10, { x: 100, y: -100 }, 5);
    expect(tip.x).toBeCloseTo(100, 6);
    expect(tip.y).toBeCloseTo(85, 6); // top edge 90, minus 5 gap
  });

  it("balloonPixels puts the tip outside the marked rectangle", () => {
    const g = balloonPixels(makeBalloon(), NAT_W, NAT_H);
    const inside =
      g.tip.x >= g.region.x &&
      g.tip.x <= g.region.x + g.region.w &&
      g.tip.y >= g.region.y &&
      g.tip.y <= g.region.y + g.region.h;
    expect(inside).toBe(false);
  });
});

describe("fitTransform", () => {
  it("fits and centres the page", () => {
    const t = fitTransform(1000, 800, NAT_W, NAT_H, 0);
    // Height-bound: 800/600 = 1.333; width 1000/800 = 1.25 → min = 1.25.
    expect(t.scale).toBeCloseTo(1.25, 6);
    expect(t.tx).toBeCloseTo(0, 6);
    expect(t.ty).toBeCloseTo((800 - 600 * 1.25) / 2, 6);
  });
});

describe("asRotation", () => {
  it("normalises to the nearest valid rotation", () => {
    expect(asRotation(0)).toBe(0);
    expect(asRotation(90)).toBe(90);
    expect(asRotation(270)).toBe(270);
    expect(asRotation(360)).toBe(0);
    expect(asRotation(-90)).toBe(270);
    expect(asRotation(45)).toBe(90); // rounds to nearest 90
    expect(asRotation(NaN as unknown as number)).toBe(0);
  });
});

describe("rotation", () => {
  const WC = 200;
  const HC = 100;
  const rots: Rotation[] = [0, 90, 180, 270];

  it("swaps dims for 90/270 only", () => {
    expect(rotatedDims(WC, HC, 0)).toEqual({ w: 200, h: 100 });
    expect(rotatedDims(WC, HC, 90)).toEqual({ w: 100, h: 200 });
    expect(rotatedDims(WC, HC, 180)).toEqual({ w: 200, h: 100 });
    expect(rotatedDims(WC, HC, 270)).toEqual({ w: 100, h: 200 });
  });

  it("rotatePx / invRotatePx are inverses for every angle and point", () => {
    const pts = [
      [0, 0],
      [WC, 0],
      [0, HC],
      [WC, HC],
      [37, 61],
    ];
    for (const rot of rots) {
      for (const [cx, cy] of pts) {
        const r = rotatePx(cx, cy, WC, HC, rot);
        const back = invRotatePx(r.x, r.y, WC, HC, rot);
        expect(back.x).toBeCloseTo(cx, 6);
        expect(back.y).toBeCloseTo(cy, 6);
      }
    }
  });

  it("maps corners into the rotated box for 90° CW", () => {
    // canonical top-left → top-right of the (HC×WC) box
    expect(rotatePx(0, 0, WC, HC, 90)).toEqual({ x: 100, y: 0 });
    // canonical top-right → bottom-right
    expect(rotatePx(WC, 0, WC, HC, 90)).toEqual({ x: 100, y: 200 });
    // canonical bottom-left → top-left
    expect(rotatePx(0, HC, WC, HC, 90)).toEqual({ x: 0, y: 0 });
  });
});

describe("sanitizeFilename", () => {
  it("replaces Windows-invalid chars and spaces with underscores", () => {
    expect(sanitizeFilename("AB/12:3*4 5")).toBe("AB_12_3_4_5");
    expect(sanitizeFilename('a<b>c|d?e"f')).toBe("a_b_c_d_e_f");
  });
  it("collapses runs and trims, falling back when empty", () => {
    expect(sanitizeFilename("  //  ", "x")).toBe("x");
    expect(sanitizeFilename("__P N__")).toBe("P_N");
  });
});

describe("balloonPixels sizeScale", () => {
  it("scales the bubble radius linearly", () => {
    const g1 = balloonPixels(makeBalloon(), NAT_W, NAT_H, 1);
    const g2 = balloonPixels(makeBalloon(), NAT_W, NAT_H, 2);
    expect(g2.r).toBeCloseTo(g1.r * 2, 6);
    expect(g2.fontSize).toBeCloseTo(g1.fontSize * 2, 6);
  });
});

describe("buildTsv / buildCsv", () => {
  const rows = [
    { number: 2, value_text: "M6" },
    { number: 1, value_text: "Ø12,5" },
  ];
  it("sorts by number and tab-separates", () => {
    expect(buildTsv(rows, ["Nr", "Wert"])).toBe("Nr\tWert\r\n1\tØ12,5\r\n2\tM6");
  });
  it("neutralises embedded tabs/newlines", () => {
    const tsv = buildTsv([{ number: 1, value_text: "a\tb\nc" }], ["Nr", "Wert"]);
    expect(tsv).toBe("Nr\tWert\r\n1\ta b c");
  });
  it("csv is semicolon-separated and quoted", () => {
    expect(buildCsv(rows, ["Nr", "Wert"])).toBe(
      '"Nr";"Wert"\r\n1;"Ø12,5"\r\n2;"M6"',
    );
  });
});
