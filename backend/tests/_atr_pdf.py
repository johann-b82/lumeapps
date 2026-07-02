"""Minimal single-page PDF with a text layer pdftotext can read — test-only."""


def make_text_pdf(text: str) -> bytes:
    # Render each \n-separated line on its own PDF text line (decreasing Y) so
    # `pdftotext` emits a multi-line layout the line-oriented parser can read.
    def _esc(s: str) -> bytes:
        return s.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)").encode("latin-1", "replace")
    parts = [b"BT /F1 10 Tf 36 750 Td"]
    for i, ln in enumerate(text.split("\n")):
        if i:
            parts.append(b"0 -14 Td")
        parts.append(b"(" + _esc(ln) + b") Tj")
    parts.append(b"ET")
    stream = b" ".join(parts)
    objs = []
    objs.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objs.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
    objs.append(b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>")
    objs.append(b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream")
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref_pos = len(out)
    out += b"xref\n0 " + str(len(objs) + 1).encode() + b"\n0000000000 65535 f \n"
    for off in offsets:
        out += ("%010d 00000 n \n" % off).encode()
    out += (b"trailer\n<< /Size " + str(len(objs) + 1).encode() +
            b" /Root 1 0 R >>\nstartxref\n" + str(xref_pos).encode() + b"\n%%EOF")
    return bytes(out)
