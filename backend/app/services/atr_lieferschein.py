# backend/app/services/atr_lieferschein.py
"""Parse a Diehl Lieferschein PDF into header + positions (ATR Phase B).

Text extraction via poppler `pdftotext -layout` (async subprocess); the
text→struct parser is pure and unit-tested.
"""
from __future__ import annotations

import asyncio
import re
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from app.services.atr_reference_import import norm_partno

_POS_RE = re.compile(r"^\s*(\d+)\s+(\d+)\s+(\d+)\s+([A-Za-z]+)\b")
_NR_RE = re.compile(r"\bNr\.\s+(\d+)")
_DATUM_RE = re.compile(r"\bDatum\s+(\d{2}\.\d{2}\.\d{4})")
_INDEX_RE = re.compile(r"Bauteil[- ]?[Ii]ndex:\s*([A-Za-z0-9]+)")
_IHRE_RE = re.compile(r"Ihre Nr\.\s*(\S+)")
_AUFTRAG_RE = re.compile(r"Auftrag Nr\.\s*(\d+)\s*/\s*(\d+)")
_BESTELL_RE = re.compile(r"Bestelldaten\s*(\S+)")


@dataclass
class ParsedPosition:
    pos: int | None = None
    supplier_article_code: str | None = None
    qty: int = 1
    bezeichnung: str | None = None
    index: str | None = None
    part_number: str | None = None
    part_number_norm: str | None = None
    ba_auftrag: str | None = None
    po_base: str | None = None
    ac_programme: str | None = None
    compartment: str | None = None
    msn: str | None = None
    bed_config: str | None = None


@dataclass
class ParsedLieferschein:
    lieferschein_nr: str | None = None
    datum: str | None = None
    positions: list[ParsedPosition] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _parse_bestelldaten(token: str, p: ParsedPosition) -> None:
    parts = token.split("/")
    if parts:
        p.po_base = parts[0] or None
    for seg in parts[1:]:
        s = seg.strip()
        if s in ("CCRC", "FCRC"):
            p.compartment = s
        elif s.upper().startswith("MSN"):
            p.msn = s[3:] or None
        elif re.fullmatch(r"\d-?Bett", s, re.IGNORECASE) or s.lower().endswith("bett"):
            m = re.match(r"(\d+)", s)
            p.bed_config = m.group(1) if m else None
        elif re.fullmatch(r"A\d{3}", s):
            p.ac_programme = s


def parse_lieferschein_text(text: str) -> ParsedLieferschein:
    pl = ParsedLieferschein()
    lines = text.splitlines()
    for line in lines:
        if pl.lieferschein_nr is None:
            m = _NR_RE.search(line)
            if m:
                pl.lieferschein_nr = m.group(1)
        if pl.datum is None:
            m = _DATUM_RE.search(line)
            if m:
                pl.datum = m.group(1)
        if pl.lieferschein_nr and pl.datum:
            break

    cur: ParsedPosition | None = None

    def _flush(p: ParsedPosition | None) -> None:
        if p is None:
            return
        for fname, label in (("ba_auftrag", "Auftrag"), ("part_number", "Ihre Nr"),
                             ("po_base", "Bestelldaten")):
            if getattr(p, fname) is None:
                pl.warnings.append(f"position {p.pos}: missing {label}")
        pl.positions.append(p)

    for line in lines:
        m = _POS_RE.match(line)
        if m:
            _flush(cur)
            cur = ParsedPosition(
                pos=int(m.group(1)), supplier_article_code=m.group(2),
                qty=int(m.group(3)),
            )
            continue
        if cur is None:
            continue
        mi = _IHRE_RE.search(line)
        if mi:
            cur.part_number = mi.group(1)
            cur.part_number_norm = norm_partno(mi.group(1))
            continue
        ma = _AUFTRAG_RE.search(line)
        if ma:
            cur.ba_auftrag = ma.group(1)
            continue
        mb = _BESTELL_RE.search(line)
        if mb:
            _parse_bestelldaten(mb.group(1), cur)
            continue
        mx = _INDEX_RE.search(line)
        if mx:
            cur.index = mx.group(1)
            continue
        # First non-empty, non-keyword line after the Pos line → Bezeichnung.
        s = line.strip()
        if s and cur.bezeichnung is None and not s.lower().startswith("teppich"):
            cur.bezeichnung = s
    _flush(cur)

    if not pl.positions:
        pl.warnings.append("no positions parsed")
    return pl


async def extract_pdf_text(pdf_bytes: bytes) -> str:
    """Run `pdftotext -layout <pdf> -` and return stdout text (async subprocess)."""
    with tempfile.TemporaryDirectory() as td:
        src = Path(td) / "in.pdf"
        src.write_bytes(pdf_bytes)
        proc = await asyncio.create_subprocess_exec(
            "pdftotext", "-layout", str(src), "-",
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=30)
        except asyncio.TimeoutError as exc:
            try:
                proc.kill()
            except ProcessLookupError:
                pass
            await proc.wait()
            raise ValueError("pdftotext timed out after 30s") from exc
        if proc.returncode != 0:
            raise ValueError(f"pdftotext failed: {err.decode('utf-8', 'replace')[-500:]}")
        return out.decode("utf-8", "replace")


async def parse_lieferschein(pdf_bytes: bytes) -> ParsedLieferschein:
    return parse_lieferschein_text(await extract_pdf_text(pdf_bytes))
