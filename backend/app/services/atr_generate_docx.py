"""Containerbeschriftung (.docx) generator (ATR Phase B)."""
from __future__ import annotations

from io import BytesIO

from docx import Document
from docx.enum.section import WD_ORIENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor

from app.services.atr_format import normalize_po_pos

_BLACK = RGBColor(0x00, 0x00, 0x00)
_RED = RGBColor(0xC0, 0x00, 0x00)
_GREEN = RGBColor(0x00, 0x80, 0x00)
_BIG = Pt(32)      # BA + MSN line — emphasised
_NORMAL = Pt(20)


def build_containerbeschriftung(delivery, items) -> bytes:
    pos_list = sorted(
        {p for it in items if (p := (normalize_po_pos(it.po_pos) or "").strip())}
    )
    # All product groups (categories) actually shipped, in first-seen order —
    # not just carpets. Matches the ATR's section grouping.
    groups = ", ".join(dict.fromkeys(
        c for it in items if (c := (it.category or "").strip())
    ))
    # (text, colour, size) per line: BA/Container black, PO/Pos red, MSN green;
    # BA and the MSN line larger.
    lines = [
        (f"BA {delivery.ba_auftrag or ''}".rstrip(), _BLACK, _BIG),
        (f"PO {delivery.po_number or ''}".rstrip(), _RED, _NORMAL),
        (f"Pos. {', '.join(pos_list)}", _RED, _NORMAL),
        (" ".join(s for s in (
            delivery.ac_programme or "", groups, f"MSN {delivery.msn or ''}".rstrip()
        ) if s), _GREEN, _BIG),
        (f"Container {delivery.container_number or ''}".rstrip(), _BLACK, _NORMAL),
    ]
    doc = Document()
    # Landscape: switch orientation and swap page width/height.
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    for text, colour, size in lines:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run(text)
        run.bold = True
        run.font.size = size
        run.font.color.rgb = colour
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()
