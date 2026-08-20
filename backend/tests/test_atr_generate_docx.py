from io import BytesIO
from types import SimpleNamespace

from docx import Document

from app.services.atr_generate_docx import build_containerbeschriftung


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
