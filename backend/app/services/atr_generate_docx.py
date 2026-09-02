"""Containerbeschriftung (.docx) generator (ATR Phase B).

Two entry points: ``build_containerbeschriftung`` (one delivery, generated
alongside the ATR) and ``build_container_label`` (all deliveries sharing one
container number, built on the fly for the deliveries list).
"""
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


def _delivery_lines(delivery, items, big=_BIG, normal=_NORMAL):
    """(text, colour, size) per line: BA black, PO/Pos red, MSN green; BA and
    the MSN line larger."""
    pos_list = sorted(
        {p for it in items if (p := (normalize_po_pos(it.po_pos) or "").strip())}
    )
    # All product groups (categories) actually shipped, in first-seen order —
    # not just carpets. Matches the ATR's section grouping.
    groups = ", ".join(dict.fromkeys(
        c for it in items if (c := (it.category or "").strip())
    ))
    return [
        (f"BA {delivery.ba_auftrag or ''}".rstrip(), _BLACK, big),
        (f"PO {delivery.po_number or ''}".rstrip(), _RED, normal),
        (f"Pos. {', '.join(pos_list)}", _RED, normal),
        (" ".join(s for s in (
            delivery.ac_programme or "", groups, f"MSN {delivery.msn or ''}".rstrip()
        ) if s), _GREEN, big),
    ]


def _render(lines, compact: bool = False) -> bytes:
    """``compact`` drops the default paragraph spacing so the block heights are
    predictable (used by the multi-delivery label to stay on one page)."""
    doc = Document()
    # Landscape: switch orientation and swap page width/height.
    section = doc.sections[0]
    section.orientation = WD_ORIENT.LANDSCAPE
    section.page_width, section.page_height = section.page_height, section.page_width
    for text, colour, size in lines:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if compact:
            p.paragraph_format.space_before = Pt(0)
            p.paragraph_format.space_after = Pt(0)
        run = p.add_run(text)
        run.bold = True
        run.font.size = size
        run.font.color.rgb = colour
    bio = BytesIO()
    doc.save(bio)
    return bio.getvalue()


def build_containerbeschriftung(delivery, items) -> bytes:
    lines = _delivery_lines(delivery, items) + [
        (f"Container {delivery.container_number or ''}".rstrip(), _BLACK, _NORMAL),
    ]
    return _render(lines)


def build_container_label(container_number: str, deliveries) -> bytes:
    """One label for a whole container: heading with the container number, then
    one block (BA/PO/Pos/MSN) per delivery. ``deliveries`` is a list of
    ``(delivery, items)`` pairs. Stays on one landscape page: the font shrinks
    with the number of deliveries (1-2 / 3-4 / 5 / scaled down beyond that)."""
    n = len(deliveries)
    if n <= 2:
        big, normal, gap = _BIG, _NORMAL, Pt(12)
    elif n <= 4:
        big, normal, gap = Pt(20), Pt(13), Pt(8)
    else:
        f = 5 / n  # five blocks fit at 14/10; scale linearly beyond
        big, normal, gap = Pt(14 * f), Pt(10 * f), Pt(6 * f)
    lines = [(f"Container {container_number}", _BLACK, _BIG)]
    for delivery, items in deliveries:
        lines.append(("", _BLACK, gap))
        lines.extend(_delivery_lines(delivery, items, big=big, normal=normal))
    return _render(lines, compact=True)
