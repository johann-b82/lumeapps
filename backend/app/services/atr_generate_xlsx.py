# backend/app/services/atr_generate_xlsx.py
"""Fill the stored ATR template (frame) with a delivery's matched rows (Phase B).

Template-as-frame: keep the template's header block / table header / totals /
certification formatting; rewrite the part-table region with the delivery items
(grouped by category), copying cell style from a template part row. Unmatched
items get a red fill so the operator fixes them in Excel.
"""
from __future__ import annotations

import asyncio
import shutil
import uuid as _uuid
from copy import copy
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import PatternFill
from openpyxl.worksheet.properties import PageSetupProperties

_RED = PatternFill(start_color="FFFF0000", end_color="FFFF0000", fill_type="solid")
_TABLE_HEADER_ROW = 13
_FIRST_PART_ROW = 14
_NCOLS = 14  # A..N
_DE_NUM = "[$-407]0.00"  # force German decimal comma regardless of LibreOffice locale


def _de_date(d) -> str:
    """German TT.MM.JJJJ for date/datetime; passthrough for anything else."""
    try:
        return d.strftime("%d.%m.%Y")
    except AttributeError:
        return str(d)


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
    raise ValueError("ATR template has no 'Total weight' row in column F")


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
        ws["C12"] = _de_date(delivery.weighing_date)
    if getattr(delivery, "testing_date", None):
        ws["L12"] = _de_date(delivery.testing_date)
    # Doc-No lives in the print header (not a cell).
    if delivery.atr_number:
        ws.oddHeader.right.text = f"Doc-No.: {delivery.atr_number}"

    # --- capture reference styles BEFORE mutating the region ---
    part_style = _capture_row_styles(ws, _FIRST_PART_ROW + 1)  # a part row
    section_style = _capture_row_styles(ws, _FIRST_PART_ROW)   # a section header row

    totals_row = _find_totals_row(ws)
    region_count = max(0, totals_row - _FIRST_PART_ROW)

    # openpyxl delete_rows/insert_rows move cell CONTENT but leave merged-cell
    # ranges (and their wide legend/certification blocks) where they were.
    # Snapshot the merges now so we can realign them after the row surgery.
    _orig_merges = [(m.min_row, m.min_col, m.max_row, m.max_col)
                    for m in ws.merged_cells.ranges]

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

    # Realign merged cells to the shifted content: header block (above the part
    # region) stays; merges that were inside the rewritten region are dropped;
    # everything at/below the totals row shifts by the net row delta.
    delta = out_rows - region_count
    ws.merged_cells.ranges = []  # drop all stale ranges; re-add correctly below
    for (r1, c1, r2, c2) in _orig_merges:
        if r1 < _FIRST_PART_ROW:
            ws.merge_cells(start_row=r1, start_column=c1, end_row=r2, end_column=c2)
        elif r1 >= totals_row:
            ws.merge_cells(start_row=r1 + delta, start_column=c1,
                           end_row=r2 + delta, end_column=c2)

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
                wc = ws.cell(r, 8, float(it.weight_kg))
                wc.number_format = _DE_NUM
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
    tw = ws.cell(new_totals_row, 8, float(total_weight))
    tw.number_format = _DE_NUM
    # Max. Guaranteed weight on the next totals label row, if present
    for rr in range(new_totals_row, min(new_totals_row + 4, ws.max_row + 1)):
        if "max" in str(ws.cell(rr, 6).value or "").lower() and delivery.max_guaranteed_weight_kg is not None:
            mg = ws.cell(rr, 8, float(delivery.max_guaranteed_weight_kg))
            mg.number_format = _DE_NUM

    # Fit to one page WIDE (kills the horizontal overflow that doubled the page
    # count); height flows to as many pages as needed. Constrain print_area to
    # A..N so stray far-right cells don't spawn extra pages.
    ws.print_area = f"A1:N{ws.max_row}"
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.page_setup.scale = None  # scale and fitToPage are mutually exclusive
    ws.sheet_properties.pageSetUpPr = PageSetupProperties(fitToPage=True)

    bio = BytesIO()
    wb.save(bio)
    return bio.getvalue()


# Serialize LibreOffice across the single-worker api container (mirror signage_pptx).
_LO_SEMAPHORE = asyncio.Semaphore(1)
_LO_TIMEOUT_S = 60


# Constant Doc-No per ACM (always the same for this report family); the header
# date is the report generation date. Applied via LibreOffice UNO because
# openpyxl mangles the print header — see atr_uno_header.py.
_ATR_DOC_NO = "ACM-A350CRC-ATR-4545-01 / Issue: 01"
_UNO_SCRIPT = str(Path(__file__).with_name("atr_uno_header.py"))


async def convert_xlsx_to_pdf(xlsx_bytes: bytes, doc_no: str = _ATR_DOC_NO,
                              date_str: str | None = None) -> bytes:
    if date_str is None:
        date_str = date.today().strftime("%d.%m.%Y")
    async with _LO_SEMAPHORE:
        tempdir = Path(f"/tmp/atr_{_uuid.uuid4()}")
        try:
            tempdir.mkdir(parents=True, exist_ok=True)
            src = tempdir / "atr.xlsx"
            src.write_bytes(xlsx_bytes)
            out = tempdir / "atr.pdf"
            proc = await asyncio.create_subprocess_exec(
                "/usr/bin/python3", _UNO_SCRIPT, str(src), str(out), doc_no, date_str,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            try:
                _, err = await asyncio.wait_for(proc.communicate(), timeout=_LO_TIMEOUT_S)
            except asyncio.TimeoutError as exc:
                try:
                    proc.kill()
                except ProcessLookupError:
                    pass
                raise RuntimeError("xlsx->pdf conversion timed out") from exc
            if proc.returncode != 0 or not out.exists():
                raise RuntimeError(
                    f"uno header/pdf failed: {err.decode('utf-8', 'replace')[-500:]}"
                )
            return out.read_bytes()
        finally:
            shutil.rmtree(tempdir, ignore_errors=True)
