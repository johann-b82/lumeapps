/**
 * Puzzle-Raster: packt Bilder mit Zellen-Spanne (spalten × zeilen) in ein
 * `cols`-spaltiges Raster (first-fit, dicht) und liefert explizite Platzierung
 * + benötigte Zeilenzahl. Damit rendert ein CSS-Grid mit quadratischen Zellen
 * (`aspect-ratio: cols / rows`, `grid-template-rows: repeat(rows, 1fr)`), und
 * die Anordnung ist deterministisch (wichtig für den html-to-image-PDF-Export).
 */
export interface PuzzleItem {
  spalten: number;
  zeilen: number;
}

export interface PuzzlePlatz {
  colStart: number;
  rowStart: number;
  spalten: number;
  zeilen: number;
}

export function packePuzzle(items: PuzzleItem[], cols = 4): { platz: PuzzlePlatz[]; rows: number } {
  const occ: boolean[][] = [];
  const ensure = (r: number) => {
    while (occ.length <= r) occ.push(new Array<boolean>(cols).fill(false));
  };
  const platz: PuzzlePlatz[] = [];
  for (const it of items) {
    const w = Math.max(1, Math.min(cols, it.spalten));
    const hh = Math.max(1, it.zeilen);
    let gesetzt = false;
    for (let r = 0; !gesetzt; r++) {
      ensure(r + hh - 1);
      for (let c = 0; c + w <= cols && !gesetzt; c++) {
        let frei = true;
        for (let rr = r; rr < r + hh && frei; rr++)
          for (let cc = c; cc < c + w && frei; cc++) if (occ[rr][cc]) frei = false;
        if (frei) {
          for (let rr = r; rr < r + hh; rr++) for (let cc = c; cc < c + w; cc++) occ[rr][cc] = true;
          platz.push({ colStart: c + 1, rowStart: r + 1, spalten: w, zeilen: hh });
          gesetzt = true;
        }
      }
    }
  }
  return { platz, rows: occ.length };
}
