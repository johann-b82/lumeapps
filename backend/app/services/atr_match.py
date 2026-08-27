# backend/app/services/atr_match.py
"""Match Lieferschein positions against the ATR catalog (Phase B)."""
from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AtrPart
from app.services.atr_lieferschein import ParsedLieferschein


@dataclass
class MatchedItem:
    pos: int | None
    supplier_article_code: str | None
    part_number: str | None
    part_number_norm: str | None
    matched_part_id: int | None
    part_name: str | None
    drawing_number_issue: str | None
    category: str | None
    qty: int
    weight_kg: Decimal | None
    po_pos: str | None
    match_status: str
    row_order: int
    serials: list[str] = field(default_factory=list)


@dataclass
class MatchedDelivery:
    source_filename: str
    lieferschein_nr: str | None
    datum: str | None
    ba_auftrag: str | None
    po_number: str | None
    ac_programme: str | None
    compartment: str | None
    msn: str | None
    bed_config: str | None
    set_title: str | None
    programme_reason: str | None = None
    items: list[MatchedItem] = field(default_factory=list)


async def match_positions(
    db: AsyncSession, parsed: ParsedLieferschein, source_filename: str
) -> MatchedDelivery:
    norms = [p.part_number_norm for p in parsed.positions if p.part_number_norm]
    catalog: dict[str, AtrPart] = {}
    if norms:
        rows = (await db.execute(
            select(AtrPart).where(AtrPart.part_number_norm.in_(norms))
        )).scalars().all()
        catalog = {r.part_number_norm: r for r in rows}

    head = parsed.positions[0] if parsed.positions else None
    compartment = head.compartment if head else None
    bed = head.bed_config if head else None
    prog = head.ac_programme if head else None
    set_title = f"SET {bed} BED {compartment}" if bed and compartment else None
    # Programme auto-detection + traceability (A380 has its own set-title default).
    if prog == "A380":
        set_title = set_title or "SET MSN UAE"
        reason = "A380 automatisch erkannt (Bestelldaten enthalten „A380“)"
    elif prog == "A350":
        reason = "A350 automatisch erkannt (Bestelldaten enthalten „A350“)"
    else:
        reason = "Kein A350/A380-Merkmal im Lieferschein — bitte Programm manuell prüfen"

    items: list[MatchedItem] = []
    for order, p in enumerate(parsed.positions, start=1):
        part = catalog.get(p.part_number_norm or "")
        if part is not None:
            items.append(MatchedItem(
                pos=p.pos, supplier_article_code=p.supplier_article_code,
                part_number=p.part_number, part_number_norm=p.part_number_norm,
                matched_part_id=part.id, part_name=part.part_name,
                drawing_number_issue=part.drawing_number_issue, category=part.category,
                qty=p.qty, weight_kg=part.default_weight_kg, po_pos=p.po_pos,
                match_status="matched", row_order=order, serials=p.serials,
            ))
        else:
            items.append(MatchedItem(
                pos=p.pos, supplier_article_code=p.supplier_article_code,
                part_number=p.part_number, part_number_norm=p.part_number_norm,
                matched_part_id=None, part_name=p.bezeichnung,
                drawing_number_issue=None, category=None, qty=p.qty,
                weight_kg=None, po_pos=p.po_pos, match_status="unmatched", row_order=order,
                serials=p.serials,
            ))

    return MatchedDelivery(
        source_filename=source_filename, lieferschein_nr=parsed.lieferschein_nr,
        datum=parsed.datum, ba_auftrag=head.ba_auftrag if head else None,
        po_number=head.po_base if head else None,
        ac_programme=head.ac_programme if head else None,
        compartment=compartment, msn=head.msn if head else None,
        bed_config=bed, set_title=set_title, programme_reason=reason, items=items,
    )
