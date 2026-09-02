from app.models import AtrPart, AtrTemplate
from app.database import Base


def test_atr_tables_registered():
    assert "atr_part" in Base.metadata.tables
    assert "atr_template" in Base.metadata.tables


def test_atr_part_columns():
    cols = {c.name for c in AtrPart.__table__.columns}
    assert {
        "id", "part_number", "part_number_norm", "supplier_article_code",
        "part_name", "drawing_number_issue", "default_weight_kg", "qty",
        "category", "po_pos", "source_filename", "imported_at", "updated_at",
    } <= cols
    assert AtrPart.__table__.c.part_number_norm.unique is True


def test_atr_template_is_per_programme():
    # Templates are per programme (id=1 A350, id=2 A380); the old singleton
    # CHECK (id = 1) was dropped in v1_116.
    names = {c.name for c in AtrTemplate.__table__.constraints}
    assert "ck_atr_template_singleton" not in names
