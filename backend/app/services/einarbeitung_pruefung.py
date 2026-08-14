"""Halbautomatische Prüfung eines hochgeladenen Einarbeitungsplan-Scans (v1.107).

Ablauf:
  1. Scan rastern (PDF via ``pdftoppm``, sonst direkt als Bild öffnen).
  2. QR-Code lesen → ``doc_uid`` (Zuordnung zum Vorgang) + die 4 QR-Ecken.
  3. Über die 4 QR-Ecken eine Homographie normiert→Scan bestimmen (entzerrt
     Verschiebung, Skalierung, Rotation und leichte Perspektive).
  4. Jedes Pflichtfeld-Rechteck aus dem gespeicherten ``feld_layout`` in den Scan
     abbilden und die Tintendichte im (eingerückten) Innenbereich messen →
     ausgefüllt/leer.

Erkennt zuverlässig, *ob* in einem Feld etwas steht (Handschrift/Unterschrift),
nicht *was*. Kein OCR. Das Gesamturteil ``vollstaendig`` ist bewusst manuell
überstimmbar (siehe Endpunkt/Frontend).
"""
from __future__ import annotations

import asyncio
import shutil
import uuid as _uuid
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image

#: Grauwert unterhalb dessen ein Pixel als „Tinte" gilt (0=schwarz, 255=weiß).
_TINTE_SCHWELLE = 140
#: Randanteile, die je Seite verworfen werden. Unten stärker, weil dort die
#: Unterschrifts-/Datumslinie sitzt (eine hauchdünne, kontrastreiche Linie würde
#: sonst bei minimalem Restversatz fälschlich als Tinte zählen).
_INSET_X, _INSET_TOP, _INSET_BOT = 0.12, 0.14, 0.30
#: Ausgefüllt, wenn die Netto-Tinte (Scan minus Blanko-Baseline) beide Schwellen
#: übertrifft. Maßgeblich ist der Flächenanteil (auflösungsunabhängig); die
#: absolute Pixelzahl ist nur ein niedriger Rauschboden. Kalibriert: Blanko-Rest
#: (Restversatz an Linien) ≤ ~1,3 %, echte Einträge ≥ ~9 %.
_MIN_NETTO_FRAC = 0.035
_MIN_NETTO_PX = 200
#: DPI für die Rasterung hochgeladener PDF-Scans (genug für QR + Tintenmessung).
_SCAN_DPI = 300

_LO_SEMAPHORE = asyncio.Semaphore(1)


@dataclass
class QRTreffer:
    doc_uid: str
    ecken: np.ndarray  # 4x2, sortiert TL, TR, BR, BL (Scan-Pixel)


# ── Rasterung ────────────────────────────────────────────────────────────────
async def scan_rastern(daten: bytes, ist_pdf: bool) -> Image.Image:
    """Hochgeladenen Scan als RGB-Bild öffnen; PDF wird zu PNG gerastert."""
    if not ist_pdf:
        return Image.open(BytesIO(daten)).convert("RGB")

    async with _LO_SEMAPHORE:
        tempdir = Path(f"/tmp/eascan_{_uuid.uuid4()}")
        try:
            tempdir.mkdir(parents=True, exist_ok=True)
            src = tempdir / "scan.pdf"
            src.write_bytes(daten)
            proc = await asyncio.create_subprocess_exec(
                "pdftoppm", "-png", "-r", str(_SCAN_DPI), "-singlefile",
                str(src), str(tempdir / "seite"),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            _, err = await proc.communicate()
            out = tempdir / "seite.png"
            if proc.returncode != 0 or not out.exists():
                raise RuntimeError(f"pdftoppm fehlgeschlagen: {err.decode('utf-8','replace')[-300:]}")
            return Image.open(out).convert("RGB")
        finally:
            shutil.rmtree(tempdir, ignore_errors=True)


# ── QR + Geometrie ───────────────────────────────────────────────────────────
def _order_pts(pts: np.ndarray) -> np.ndarray:
    """4 Punkte in die Reihenfolge TL, TR, BR, BL bringen."""
    pts = np.asarray(pts, dtype=float)
    s = pts.sum(axis=1)
    d = (pts[:, 1] - pts[:, 0])  # y - x
    return np.array([
        pts[np.argmin(s)],  # TL: kleinste Summe
        pts[np.argmin(d)],  # TR: kleinstes y-x
        pts[np.argmax(s)],  # BR: größte Summe
        pts[np.argmax(d)],  # BL: größtes y-x
    ])


def qr_dekodieren(img: Image.Image) -> QRTreffer | None:
    """Ersten QR-Code lesen; gibt doc_uid + sortierte Eckpunkte zurück."""
    from pyzbar.pyzbar import ZBarSymbol, decode

    codes = decode(img.convert("L"), symbols=[ZBarSymbol.QRCODE])
    for c in codes:
        data = c.data.decode("utf-8", "replace").strip()
        if not data:
            continue
        pts = [(p.x, p.y) for p in c.polygon] if len(c.polygon) >= 4 else [
            (c.rect.left, c.rect.top),
            (c.rect.left + c.rect.width, c.rect.top),
            (c.rect.left + c.rect.width, c.rect.top + c.rect.height),
            (c.rect.left, c.rect.top + c.rect.height),
        ]
        # Bei >4 Polygonpunkten die 4 Extrempunkte (konvexe Ecken) nehmen.
        pts_np = np.array(pts, dtype=float)
        if len(pts_np) > 4:
            s = pts_np.sum(axis=1)
            d = pts_np[:, 1] - pts_np[:, 0]
            idx = {np.argmin(s), np.argmax(s), np.argmin(d), np.argmax(d)}
            pts_np = pts_np[sorted(idx)]
        return QRTreffer(doc_uid=data, ecken=_order_pts(pts_np))
    return None


def _similaritaet(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Beste Ähnlichkeit (Skalierung + Rotation + Translation) src→dst (Umeyama).

    Rückgabe als 2x3-Affinmatrix. Nur 4 Freiheitsgrade — gut konditioniert für
    die grobe Ausrichtung allein aus dem kleinen QR.
    """
    src = np.asarray(src, dtype=float)
    dst = np.asarray(dst, dtype=float)
    mu_s, mu_d = src.mean(0), dst.mean(0)
    xs, xd = src - mu_s, dst - mu_d
    sigma = (xd.T @ xs) / len(src)
    U, D, Vt = np.linalg.svd(sigma)
    S = np.eye(2)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        S[-1, -1] = -1
    R = U @ S @ Vt
    var_s = (xs ** 2).sum() / len(src)
    scale = float((D * np.diag(S)).sum() / var_s)
    t = mu_d - scale * (R @ mu_s)
    return np.hstack([scale * R, t.reshape(2, 1)])


def _affine(src: np.ndarray, dst: np.ndarray) -> np.ndarray:
    """Beste Affine (6 Freiheitsgrade) src→dst als 2x3-Matrix (Least Squares)."""
    src = np.asarray(src, dtype=float)
    dst = np.asarray(dst, dtype=float)
    A = np.c_[src, np.ones(len(src))]
    sol, *_ = np.linalg.lstsq(A, dst, rcond=None)  # (3,2)
    return sol.T


def _abbilden(M: np.ndarray, pts: np.ndarray) -> np.ndarray:
    pts = np.asarray(pts, dtype=float)
    return pts @ M[:, :2].T + M[:, 2]


def _finde_marke(grau: np.ndarray, cx: float, cy: float, radius: float, k: int):
    """Zentrum des dunkelsten k×k-Quadrats um (cx,cy) — lokalisiert die Marke."""
    H, W = grau.shape
    x0, x1 = max(0, int(cx - radius)), min(W, int(cx + radius))
    y0, y1 = max(0, int(cy - radius)), min(H, int(cy + radius))
    if x1 - x0 <= k or y1 - y0 <= k:
        return None
    win = (grau[y0:y1, x0:x1] < 128).astype(np.int32)
    ii = np.zeros((win.shape[0] + 1, win.shape[1] + 1), dtype=np.int32)
    ii[1:, 1:] = win.cumsum(0).cumsum(1)
    summe = ii[k:, k:] - ii[:-k, k:] - ii[k:, :-k] + ii[:-k, :-k]
    if summe.size == 0 or summe.max() < 0.5 * k * k:
        return None  # kein ausreichend dunkles Quadrat → Marke nicht gefunden
    by, bx = np.unravel_index(int(np.argmax(summe)), summe.shape)
    return (x0 + bx + k / 2, y0 + by + k / 2)


def _refine_transform(img: Image.Image, layout: dict):
    """Ausrichtung Punkt-Raum→Scan: grob aus QR, verfeinert mit den Passermarken.

    Grobe Ähnlichkeit aus dem QR, dann jede Marke lokal suchen und aus QR-Ecken
    + gefundenen Marken eine gut verteilte Affine schätzen (robust über die
    ganze Seite). Ohne gefundene Marken bleibt die QR-Ähnlichkeit.
    """
    treffer = qr_dekodieren(img)
    if treffer is None:
        return None
    seite = layout["seite"]
    w_pt, h_pt = seite["w_pt"], seite["h_pt"]
    qr_src = _box_ecken_pt(layout["qr"]["box"], w_pt, h_pt)
    grob = _similaritaet(qr_src, treffer.ecken)  # rotationsbewusste Grobausrichtung
    grau = np.asarray(img.convert("L"))
    skala = float(np.hypot(grob[0, 0], grob[1, 0]))  # Scan-Pixel je Punkt

    # QR-Zentrum als erster, gut lokalisierter Referenzpunkt.
    src = [list(qr_src.mean(0))]
    dst = [list(treffer.ecken.mean(0))]
    for m in layout.get("marken", []):
        cx_pt, cy_pt = (m[0] + m[2]) / 2 * w_pt, (m[1] + m[3]) / 2 * h_pt
        k = max(4, int(round((m[2] - m[0]) * w_pt * skala)))
        pred = _abbilden(grob, np.array([[cx_pt, cy_pt]]))[0]
        # großzügiges Fenster: der QR-Grobfehler kann am Blattfuß groß sein; das
        # voll-schwarze Quadrat gewinnt als dunkelste Fläche gegen Text/Rahmen.
        gefunden = _finde_marke(grau, pred[0], pred[1],
                                radius=max(8 * k, int(0.16 * grau.shape[0])), k=k)
        if gefunden is not None:
            src.append([cx_pt, cy_pt])
            dst.append(list(gefunden))

    # Drei gut verteilte Punkte (QR-Zentrum + 2 Marken) → stabile Affine; sonst
    # bleibt die QR-Ähnlichkeit.
    M = _affine(np.array(src), np.array(dst)) if len(src) >= 3 else grob
    return M, treffer.doc_uid


def _feld_messung(grau: np.ndarray, bbox: tuple[float, float, float, float]) -> tuple[int, int]:
    """Dunkle Pixel und Fläche im eingerückten Innenbereich einer Bounding-Box."""
    x0, y0, x1, y1 = bbox
    w, h = x1 - x0, y1 - y0
    ix0, iy0 = int(round(x0 + _INSET_X * w)), int(round(y0 + _INSET_TOP * h))
    ix1, iy1 = int(round(x1 - _INSET_X * w)), int(round(y1 - _INSET_BOT * h))
    H, W = grau.shape
    ix0, iy0 = max(0, ix0), max(0, iy0)
    ix1, iy1 = min(W, ix1), min(H, iy1)
    if ix1 <= ix0 or iy1 <= iy0:
        return 0, 0
    crop = grau[iy0:iy1, ix0:ix1]
    return int((crop < _TINTE_SCHWELLE).sum()), int(crop.size)


def _box_ecken_pt(box: list[float], w_pt: float, h_pt: float) -> np.ndarray:
    """Normierte Box → 4 Eckpunkte im isotropen Punkt-Raum (TL,TR,BR,BL).

    Wichtig: die Umrechnung nach Punkten macht die Geometrie isotrop (der QR ist
    dort quadratisch), sonst kann die Ähnlichkeitstransformation nicht greifen.
    """
    x0, y0, x1, y1 = box[0] * w_pt, box[1] * h_pt, box[2] * w_pt, box[3] * h_pt
    return np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]])


def _feld_bbox(transform, box: list[float], w_pt: float, h_pt: float) -> tuple[float, float, float, float]:
    pix = _abbilden(transform, _box_ecken_pt(box, w_pt, h_pt))
    return (pix[:, 0].min(), pix[:, 1].min(), pix[:, 0].max(), pix[:, 1].max())


def feld_pruefung(img: Image.Image, layout: dict, referenz: Image.Image | None = None) -> dict:
    """Pflichtfelder aus ``layout`` im Scan prüfen.

    ``referenz`` ist das gerenderte Blanko-Formular: seine Tinte (Rahmen,
    Unterstriche) wird feldweise abgezogen, sodass nur die handschriftliche
    Netto-Tinte übrig bleibt. Beide Bilder werden über ihren QR ausgerichtet.
    """
    hq = _refine_transform(img, layout)
    if hq is None:
        return {"qr_ok": False, "doc_uid": None, "felder": [], "vollstaendig": False, "fehlend": []}
    H, doc_uid = hq
    grau = np.asarray(img.convert("L"))
    seite = layout["seite"]
    w_pt, h_pt = seite["w_pt"], seite["h_pt"]

    # Baseline aus dem Blanko (ebenfalls ausgerichtet über QR + Marken).
    base_grau = base_H = None
    if referenz is not None:
        hqr = _refine_transform(referenz, layout)
        if hqr is not None:
            base_H = hqr[0]
            base_grau = np.asarray(referenz.convert("L"))

    felder = []
    for f in layout.get("felder", []):
        scan_dark, area = _feld_messung(grau, _feld_bbox(H, f["box"], w_pt, h_pt))
        base_dark = 0
        if base_grau is not None:
            base_dark, _ = _feld_messung(base_grau, _feld_bbox(base_H, f["box"], w_pt, h_pt))
        netto = max(0, scan_dark - base_dark)
        frac = netto / area if area else 0.0
        erkannt = netto >= _MIN_NETTO_PX and frac >= _MIN_NETTO_FRAC
        felder.append({
            "key": f["key"], "label": f["label"], "erkannt": erkannt,
            "netto_px": netto, "frac": round(frac, 4),
        })

    fehlend = [f["label"] for f in felder if not f["erkannt"]]
    return {
        "qr_ok": True,
        "doc_uid": doc_uid,
        "felder": felder,
        "vollstaendig": bool(felder) and not fehlend,
        "fehlend": fehlend,
    }
