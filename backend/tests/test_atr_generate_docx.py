from io import BytesIO
from types import SimpleNamespace

from docx import Document

from app.services.atr_generate_docx import (
    build_container_label,
    build_containerbeschriftung,
)


def _it(po_pos, category="Teppiche"):
    return SimpleNamespace(po_pos=po_pos, category=category)


def test_label_lines():
    delivery = SimpleNamespace(ba_auftrag="1024738", po_number="4501119979",
                               ac_programme="A350", msn="830", container_number="AK111XXX")
    items = [_it("300"), _it("050"), _it("340")]
    out = build_containerbeschriftung(delivery, items)
    doc = Document(BytesIO(out))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "BA 1024738" in text
    assert "PO 4501119979" in text
    assert "Pos. 050, 300, 340" in text  # sorted, comma-joined
    assert "A350 Teppiche MSN 830" in text
    assert "Container AK111XXX" in text


def _delivery(ba, msn, po="4501119979"):
    return SimpleNamespace(ba_auftrag=ba, po_number=po, ac_programme="A350", msn=msn,
                           container_number="AK111XXX")


def test_container_label_lists_every_delivery():
    out = build_container_label("AK111XXX", [
        (_delivery("1024738", "830"), [_it("300"), _it("050")]),
        (_delivery("1024739", "831"), [_it("010")]),
    ])
    doc = Document(BytesIO(out))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert text.startswith("Container AK111XXX")
    assert "BA 1024738" in text and "BA 1024739" in text
    assert "Pos. 050, 300" in text and "Pos. 010" in text
    assert "A350 Teppiche MSN 830" in text and "A350 Teppiche MSN 831" in text
    assert text.count("Container ") == 1  # heading only, no per-delivery line


def test_container_label_shrinks_font_in_two_steps():
    def ba_size(n):
        doc = Document(BytesIO(build_container_label("C1", [
            (_delivery("1", "1"), [_it("1")]) for _ in range(n)])))
        return next(p.runs[0].font.size for p in doc.paragraphs if p.text.startswith("BA "))

    assert ba_size(2) > ba_size(3) == ba_size(4) > ba_size(5)
