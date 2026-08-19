"""Shared generate-and-deliver routine (Phase C).

Builds the three documents for a delivery (Phase B generators), stores the
bytes on the row, and — for scan-origin deliveries when the SMB share is
configured — writes them to the Output dir and archives the source PDF.
Used by both the scheduler (auto mode) and the Phase B Generate endpoint.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AtrDelivery, AtrTemplate
from app.schemas import AtrGenerateManifest
from app.services import atr_fileserver as fs
from app.services.atr_format import normalize_po_pos
from app.services.atr_generate_docx import build_containerbeschriftung
from app.services.atr_generate_xlsx import atr_doc_no, build_atr_xlsx, convert_xlsx_to_pdf

log = logging.getLogger(__name__)

# Illegal in Windows/SMB filenames; keep spaces, commas, dots, hyphens, underscores.
_ILLEGAL_FILENAME = re.compile(r'[\\/:*?"<>|\x00-\x1f]+')
_FILENAME_MAX = 130  # base+Pos budget; keeps the full path under Windows/SMB limits


def _sanitize_filename(name: str) -> str:
    cleaned = _ILLEGAL_FILENAME.sub("", name).strip().rstrip(". ")
    return cleaned or "atr"


def delivery_filename_base(delivery, items=None) -> str:
    """Descriptive output base name (no extension), e.g.
    ``ACM_ATR_WR_COC_A350_ATR_4820-01 BA1024796_FCRC_MSN 844_4501124711 6 BED Head Pos 190, 200``.

    Segments with no data are skipped; the trailing ``Pos …`` list is dropped
    when the name would exceed the length budget.
    """
    if items is None:
        items = list(delivery.items)
    prog = (delivery.ac_programme or "A350").strip()
    atr = (delivery.atr_number or "").strip()
    parts = [f"ACM_ATR_WR_COC_{prog}_ATR-{atr}-01" if atr
             else f"ACM_ATR_WR_COC_{prog}_ATR"]
    if delivery.ba_auftrag:
        parts.append(f" BA{str(delivery.ba_auftrag).strip()}")
    if delivery.compartment:
        parts.append(f"_{str(delivery.compartment).strip()}")
    if delivery.msn:
        parts.append(f"_MSN {str(delivery.msn).strip()}")
    if delivery.po_number:
        parts.append(f"_{str(delivery.po_number).strip()}")
    if delivery.bed_config:
        parts.append(f" {str(delivery.bed_config).strip()} BED")
    cat = next((i.category for i in items if i.category), None)
    if cat:
        parts.append(f" {cat.strip().title()}")
    base = "".join(parts)
    pos = [p for p in (normalize_po_pos(i.po_pos) for i in items if i.po_pos) if p]
    if pos:
        with_pos = f"{base} Pos {', '.join(pos)}"
        if len(with_pos) <= _FILENAME_MAX:
            base = with_pos
    return _sanitize_filename(base)


async def compute_next_atr_number(db: AsyncSession) -> str | None:
    """Next running ATR number = highest numeric ``atr_number`` on record + 1.
    Returns None when no numeric ATR number exists yet (seed the first one
    manually). Non-numeric (manually formatted) numbers are ignored."""
    rows = (await db.execute(select(AtrDelivery.atr_number))).scalars().all()
    nums = [int(v) for v in rows if v and v.strip().isdigit()]
    return str(max(nums) + 1) if nums else None


async def generate_and_deliver(db: AsyncSession, delivery, settings_row) -> AtrGenerateManifest:
    items = list(delivery.items)
    # Auto-assign a running ATR number when none was entered manually
    # (manual entry always wins). Covers both the review Generate button and
    # the unattended scan/auto path, which has no mask.
    if not (delivery.atr_number or "").strip():
        auto = await compute_next_atr_number(db)
        if auto:
            delivery.atr_number = auto
    tmpl = (await db.execute(select(AtrTemplate).where(AtrTemplate.id == 1))).scalar_one_or_none()
    if tmpl is None or tmpl.structure_xlsx is None:
        raise ValueError("no structural template set")

    warnings: list[str] = []
    logo_bytes = getattr(settings_row, "logo_data", None)
    logo_ext = "svg" if "svg" in (getattr(settings_row, "logo_mime", "") or "") else "png"
    xlsx = build_atr_xlsx(tmpl.structure_xlsx, delivery, items, logo_bytes=logo_bytes)
    docx = build_containerbeschriftung(delivery, items)
    pdf: bytes | None = None
    try:
        pdf = await convert_xlsx_to_pdf(xlsx, doc_no=atr_doc_no(delivery),
                                        logo_bytes=logo_bytes, logo_ext=logo_ext)
    except Exception as exc:  # noqa: BLE001
        log.warning("atr deliver: pdf conversion failed for delivery %s: %s", delivery.id, exc)
        warnings.append("PDF conversion failed; .xlsx and .docx are still available.")

    delivery.atr_xlsx = xlsx
    delivery.atr_pdf = pdf
    delivery.label_docx = docx
    delivery.status = "generated"
    delivery.updated_at = datetime.now(timezone.utc)

    cfg = fs.smb_config_from_settings(settings_row)
    if delivery.origin == "scan" and cfg is not None:
        base = delivery_filename_base(delivery, items)
        try:
            await asyncio.to_thread(fs.write_output, cfg, f"{base}.xlsx", xlsx)
            if pdf is not None:
                await asyncio.to_thread(fs.write_output, cfg, f"{base}.pdf", pdf)
            await asyncio.to_thread(fs.write_output, cfg, f"{base}_Container.docx", docx)
        except fs.AtrFileserverError as exc:
            log.warning("atr deliver: share write failed for delivery %s: %s", delivery.id, exc)
            warnings.append(f"writing to the fileserver failed: {exc}")
            await db.commit()  # status stays 'generated'; not delivered, source NOT archived
            return _manifest(delivery, items, pdf, warnings)
        # writes succeeded → record delivered, COMMIT, THEN archive
        delivery.output_written_at = datetime.now(timezone.utc)
        delivery.status = "delivered"
        await db.commit()
        if delivery.source_path:
            try:
                await asyncio.to_thread(fs.archive_input, cfg, delivery.source_path.rsplit("/", 1)[-1])
            except fs.AtrFileserverError as exc:
                log.warning("atr deliver: archive failed for delivery %s: %s", delivery.id, exc)
                warnings.append(f"archiving the source failed: {exc}")
        return _manifest(delivery, items, pdf, warnings)
    await db.commit()
    return _manifest(delivery, items, pdf, warnings)


def _manifest(delivery, items, pdf, warnings) -> AtrGenerateManifest:
    files = ["atr_xlsx", "label_docx"] + (["atr_pdf"] if pdf else [])
    unmatched = sum(1 for i in items if i.match_status != "matched")
    if unmatched:
        warnings.append(f"{unmatched} unmatched part(s) marked red in the ATR — fix in Excel.")
    return AtrGenerateManifest(delivery_id=delivery.id, files=files,
                               pdf_available=pdf is not None,
                               unmatched_count=unmatched, warnings=warnings)
