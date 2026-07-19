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

from app.models import AtrTemplate
from app.schemas import AtrGenerateManifest
from app.services import atr_fileserver as fs
from app.services.atr_generate_docx import build_containerbeschriftung
from app.services.atr_generate_xlsx import build_atr_xlsx, convert_xlsx_to_pdf

log = logging.getLogger(__name__)


def _base_name(delivery) -> str:
    raw = delivery.atr_number or delivery.ba_auftrag or (
        (delivery.source_filename or "atr").rsplit(".", 1)[0])
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("_") or "atr"


async def generate_and_deliver(db: AsyncSession, delivery, settings_row) -> AtrGenerateManifest:
    items = list(delivery.items)
    tmpl = (await db.execute(select(AtrTemplate).where(AtrTemplate.id == 1))).scalar_one_or_none()
    if tmpl is None or tmpl.structure_xlsx is None:
        raise ValueError("no structural template set")

    warnings: list[str] = []
    xlsx = build_atr_xlsx(tmpl.structure_xlsx, delivery, items)
    docx = build_containerbeschriftung(delivery, items)
    pdf: bytes | None = None
    logo_bytes = getattr(settings_row, "logo_data", None)
    logo_ext = "svg" if "svg" in (getattr(settings_row, "logo_mime", "") or "") else "png"
    try:
        pdf = await convert_xlsx_to_pdf(xlsx, logo_bytes=logo_bytes, logo_ext=logo_ext)
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
        base = _base_name(delivery)
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
