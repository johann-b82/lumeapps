# backend/app/services/atr_generate_xlsx.py
"""Fill the stored ATR template (frame) with a delivery's matched rows (Phase B).

Template-as-frame: keep the template's header block / table header / totals /
certification formatting; rewrite the part-table region with the delivery items
(grouped by category), copying cell style from a template part row. Unmatched
items get a red fill so the operator fixes them in Excel.
"""
from __future__ import annotations

from copy import copy
from decimal import Decimal
from io import BytesIO

from openpyxl import load_workbook
from openpyxl.styles import PatternFill

_RED = PatternFill(start_color="FFFF0000", end_color="FFFF0000", fill_type="solid")
_TABLE_HEADER_ROW = 13
_FIRST_PART_ROW = 14
_NCOLS = 14  # A..N


def _visible_sheet(wb):
    vis = [w for w in wb.worksheets if w.sheet_state == "visible"]
    if len(vis) != 1:
        raise ValueError(f"expected one visible sheet, found {len(vis)}")
    return vis[0]


def _find_totals_row(ws) -> int:
    for r in range(_FIRST_PART_ROW, ws.max_row + 1):
        f = ws.cell(r, 6).value
        if f and "total" in str(f).lower():
            return r
    return ws.max_row + 1


def _capture_row_styles(ws, row: int) -> list:
    return [copy(ws.cell(row, c)._style) for c in range(1, _NCOLS + 1)]


def build_atr_xlsx(template_bytes: bytes, delivery, items) -> bytes:
    wb = load_workbook(BytesIO(template_bytes))
    ws = _visible_sheet(wb)

    # --- header block (template defaults stay; per-delivery values overwrite) ---
    if delivery.set_title is not None:
        ws["A11"] = delivery.set_title
    if delivery.po_number is not None:
        ws["G1"] = delivery.po_number
    if delivery.msn is not None:
        ws["G2"] = delivery.msn
    if delivery.ba_auftrag is not None:
        ws["D9"] = delivery.ba_auftrag
    if getattr(delivery, "weighing_date", None):
        ws["C12"] = str(delivery.weighing_date)
    if getattr(delivery, "testing_date", None):
        ws["L12"] = str(delivery.testing_date)
    # Doc-No lives in the print header (not a cell).
    if delivery.atr_number:
        ws.oddHeader.right.text = f"Doc-No.: {delivery.atr_number}"

    # --- capture reference styles BEFORE mutating the region ---
    part_style = _capture_row_styles(ws, _FIRST_PART_ROW + 1)  # a part row
    section_style = _capture_row_styles(ws, _FIRST_PART_ROW)   # a section header row

    totals_row = _find_totals_row(ws)
    region_count = max(0, totals_row - _FIRST_PART_ROW)

    # group items by category in first-seen order
    grouped: list[tuple[str | None, list]] = []
    index: dict[str | None, int] = {}
    for it in items:
        cat = it.category
        if cat not in index:
            index[cat] = len(grouped)
            grouped.append((cat, []))
        grouped[index[cat]][1].append(it)

    # rows we will write: one section header per category + one per item
    out_rows = sum(1 + len(lst) for _, lst in grouped)

    # clear the example region and resize it to out_rows
    if region_count:
        ws.delete_rows(_FIRST_PART_ROW, region_count)
    if out_rows:
        ws.insert_rows(_FIRST_PART_ROW, out_rows)

    r = _FIRST_PART_ROW
    total_weight = Decimal("0")
    for cat, lst in grouped:
        # section header row
        for c in range(1, _NCOLS + 1):
            ws.cell(r, c)._style = copy(section_style[c - 1])
        ws.cell(r, 1, cat or "")
        r += 1
        for it in lst:
            for c in range(1, _NCOLS + 1):
                ws.cell(r, c)._style = copy(part_style[c - 1])
            ws.cell(r, 1, it.po_pos or "")
            ws.cell(r, 2, it.supplier_article_code or "")
            ws.cell(r, 3, it.part_number or "")
            ws.cell(r, 4, it.part_name or "")
            ws.cell(r, 5, "N/A")
            ws.cell(r, 6, it.drawing_number_issue or "")
            ws.cell(r, 7, it.qty)
            if it.weight_kg is not None:
                ws.cell(r, 8, float(it.weight_kg))
                total_weight += it.weight_kg
            for c, mark in zip(range(9, 14), ("P", "P", "P", "P", "P")):
                ws.cell(r, c, mark)
            ws.cell(r, 14, "OK")
            if it.match_status != "matched":
                for c in range(1, _NCOLS + 1):
                    ws.cell(r, c).fill = _RED
            r += 1

    # totals block shifted down by (out_rows - region_count + region_count) — re-find it
    new_totals_row = _find_totals_row(ws)
    if new_totals_row <= ws.max_row:
        ws.cell(new_totals_row, 8, float(total_weight))
        # Max. Guaranteed weight on the next totals label row, if present
        for rr in range(new_totals_row, min(new_totals_row + 4, ws.max_row + 1)):
            if "max" in str(ws.cell(rr, 6).value or "").lower() and delivery.max_guaranteed_weight_kg is not None:
                ws.cell(rr, 8, float(delivery.max_guaranteed_weight_kg))

    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()
