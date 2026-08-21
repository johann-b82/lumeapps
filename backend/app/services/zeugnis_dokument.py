"""Arbeitszeugnis als DOCX (editierbar) und PDF (v1.110).

Der Fließtext kommt aus ``zeugnis.abschnitte_json`` (KI-generiert, danach von HR
editiert). Das DOCX entsteht mit python-docx auf Briefkopf (App-Logo), das PDF
per LibreOffice — derselbe ``soffice``-Pfad wie Wartung/ATR/Signage.
"""
from __future__ import annotations

import asyncio
import shutil
import uuid as _uuid
from io import BytesIO
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Cm, Pt, RGBColor

from app.models.zeugnis import ZEUGNIS_ABSCHNITTE, Zeugnis, ZeugnisAussteller

_MONATE = (
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
)


def _datum_lang(d) -> str:
    return f"{d.day}. {_MONATE[d.month - 1]} {d.year}" if d else ""


def _titel(art: str) -> str:
    if art == "zwischenzeugnis":
        return "Zwischenzeugnis"
    if art == "einfach":
        return "Arbeitszeugnis"
    return "Arbeitszeugnis"


def build_zeugnis_docx(
    zeugnis: Zeugnis,
    aussteller: ZeugnisAussteller | None,
    logo_png: bytes | None,
) -> bytes:
    """Baut das Arbeitszeugnis als .docx und gibt die Bytes zurück."""
    doc = Document()
    for section in doc.sections:
        section.top_margin = Cm(2.0)
        section.bottom_margin = Cm(2.0)
        section.left_margin = Cm(2.5)
        section.right_margin = Cm(2.5)

    # --- Briefkopf: Logo + Firma ---
    if logo_png:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        try:
            p.add_run().add_picture(BytesIO(logo_png), width=Cm(4.0))
        except Exception:  # pragma: no cover - defektes Bild bricht das Zeugnis nicht
            pass
    if aussteller and aussteller.firma:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        run = p.add_run(aussteller.firma)
        run.bold = True
        if aussteller.standort:
            ps = doc.add_paragraph()
            ps.alignment = WD_ALIGN_PARAGRAPH.RIGHT
            r = ps.add_run(aussteller.standort)
            r.font.size = Pt(9)
            r.font.color.rgb = RGBColor(0x55, 0x55, 0x55)

    doc.add_paragraph()

    # --- Titel ---
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run(_titel(zeugnis.art))
    run.bold = True
    run.font.size = Pt(16)
    doc.add_paragraph()

    # --- Fließtext-Abschnitte (leere überspringen) ---
    abschnitte = zeugnis.abschnitte_json or {}
    for key in ZEUGNIS_ABSCHNITTE:
        text = str(abschnitte.get(key, "") or "").strip()
        if not text:
            continue
        para = doc.add_paragraph(text)
        para.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        para.paragraph_format.space_after = Pt(10)

    # --- Ort, Datum ---
    doc.add_paragraph()
    ort = (aussteller.standort if aussteller else None) or ""
    datum = _datum_lang(zeugnis.ausstellungsdatum)
    if ort or datum:
        p = doc.add_paragraph(", ".join(x for x in (ort, f"den {datum}" if datum else "") if x))

    # --- Unterschriften ---
    if aussteller and (aussteller.unterzeichner1_name or aussteller.unterzeichner2_name):
        doc.add_paragraph()
        doc.add_paragraph()
        zeile = doc.add_paragraph()
        for name, titel in (
            (aussteller.unterzeichner1_name, aussteller.unterzeichner1_titel),
            (aussteller.unterzeichner2_name, aussteller.unterzeichner2_titel),
        ):
            if not name:
                continue
            block = f"{name}"
            if titel:
                block += f"\n{titel}"
            run = zeile.add_run(block + "\t\t")
            run.font.size = Pt(10)

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()


# LibreOffice über den api-Container serialisieren (wie Wartung/ATR/Signage).
_LO_SEMAPHORE = asyncio.Semaphore(1)
_LO_TIMEOUT_S = 60


async def convert_docx_to_pdf(docx_bytes: bytes) -> bytes:
    async with _LO_SEMAPHORE:
        tempdir = Path(f"/tmp/zeugnis_{_uuid.uuid4()}")
        try:
            tempdir.mkdir(parents=True, exist_ok=True)
            src = tempdir / "zeugnis.docx"
            src.write_bytes(docx_bytes)
            profile = tempdir / "profile"
            proc = await asyncio.create_subprocess_exec(
                "soffice", "--headless", "--invisible", "--nodefault",
                "--norestore", "--nologo", "--nofirststartwizard",
                f"-env:UserInstallation=file://{profile}",
                "--convert-to", "pdf:writer_pdf_Export",
                "--outdir", str(tempdir), str(src),
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, err = await asyncio.wait_for(
                    proc.communicate(), timeout=_LO_TIMEOUT_S
                )
            except asyncio.TimeoutError as exc:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                raise RuntimeError("docx->pdf conversion timed out") from exc
            out = tempdir / "zeugnis.pdf"
            if proc.returncode != 0 or not out.exists():
                raise RuntimeError(
                    f"soffice pdf export failed: {err.decode('utf-8', 'replace')[-500:]}"
                )
            return out.read_bytes()
        finally:
            shutil.rmtree(tempdir, ignore_errors=True)
