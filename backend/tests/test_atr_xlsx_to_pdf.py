# backend/tests/test_atr_xlsx_to_pdf.py
from app.services.atr_generate_xlsx import convert_xlsx_to_pdf
from tests._atr_fixtures import build_atr_workbook_bytes


async def test_xlsx_to_pdf_smoke():
    pdf = await convert_xlsx_to_pdf(build_atr_workbook_bytes())
    assert pdf[:5] == b"%PDF-" and len(pdf) > 500
