"""Containerbeschriftung (.docx) generator (ATR Phase B)."""
from __future__ import annotations

from io import BytesIO

from docx import Document
from docx.shared import Pt

from app.services.atr_format import normalize_po_pos


def build_containerbeschriftung(delivery, items) -> bytes:
    pos_list = sorted(
        {p for it in items if (p := (normalize_po_pos(it.po_pos) or "").strip())}
    )
    lines = [
        f"BA {delivery.ba_auftrag or ''}".rstrip(),
        f"PO {delivery.po_number or ''}".rstrip(),
        f"Pos. {', '.join(pos_list)}",
        f"{delivery.ac_programme or ''} Teppiche MSN {delivery.msn or ''}".strip(),
        f"Container {delivery.container_number or ''}".rstrip(),
    ]
    doc = Document()
    for line in lines:
        p = doc.add_paragraph()
        run = p.add_run(line)
        run.bold = True
        run.font.size = Pt(20)
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()
