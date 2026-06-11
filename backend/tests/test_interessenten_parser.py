"""Parser tests for app.parsing.interessenten_parser.

Builds a minimal fixture mirroring the real ``dev_excel_INT.txt``
export: an 88-column tab-separated file in Latin-1 with two header
lines (title + real headers) and N data rows. Only three columns are
asserted on the parser output — Adress-Nr., Name 1, Datum Save.
"""
from datetime import date

from app.parsing.interessenten_parser import parse_interessenten_file


HEADER_COLS = [
    "Adress-Nr.", "Anrede Brief", "Anrede", "Name 1", "Name 2", "Name 3",
    "Stra\xdfe", "PLZ", "Ort", "KZ-Land", "Land", "PLZ-Postfach", "Postfach",
    "Tel", "Fax", "E-Mail", "KD-Gruppe", "KD-Gruppe Beschreibung", "Branche",
    "Sperrdatum", "Sperrgrund", "Verband", "Vertreter 1", "Provision",
    "Vertreter 2", "Geburtstag", "Mahnart", "Kommentar 1", "Kommentar 2",
    "Kommentar 3", "Versandart", "Kundengruppe", "Preisgruppe",
    "Rabattgruppe", "Provisionsgruppe", "Klasse 1", "Klasse 2", "Klasse 3",
    "Klasse 4", "Klasse 5", "VK-Gebiet", "Uni 1", "Uni 2", "Rabatt 1",
    "Rabatt 2", "Rabatt 3", "Rabatt 4", "Rabatt 5", "Umsatz", "Umsatz VJ",
    "Umsatz VVJ", "Anrede Brief", "Anrede", "Ansprechpartner", "Name 2",
    "Telefon", "Telefax", "Zahlungsbedingungen", "Text", "Lieferbedingungen",
    "Text", "User", "Datum", "BLZ", "Konto", "Zollkennzeichen",
    "Zollhinweis 1", "Zollhinweis 2", "Email", "L\xe4nderklasse", "MwSt.",
    "Warnhinweis 1", "Warnhinweis 2", "Warnhinweis 3", "Spedition",
    "Sprache", "GLN", "Sammelrechnung", "Typ", "Frequenz", "Fibukonto",
    "Priorit\xe4t", "Limit", "EDI-Kz", "Datum Save",
]
# Real file has 3 trailing empty columns (88 total).
HEADER_COLS_88 = HEADER_COLS + ["", "", ""]
assert len(HEADER_COLS_88) == 88


def _row(adress_nr: str, name: str, datum_save: str) -> str:
    """Build a tab-separated data row with the three columns we care about
    populated and everything else blank. Returns a Python str (caller
    encodes to Latin-1 to match the real export)."""
    cols = [""] * 88
    cols[0] = adress_nr        # Adress-Nr.
    cols[3] = name             # Name 1
    cols[84] = datum_save      # Datum Save (Excel CG = index 84)
    return "\t".join(cols)


def _fixture(rows: list[str]) -> bytes:
    title = "Adressen\tInteressenten" + "\t" * 86
    header = "\t".join(HEADER_COLS_88)
    body = "\r\n".join([title, header, *rows, ""])
    return body.encode("latin-1")


def test_parser_extracts_three_fields():
    payload = _fixture([
        _row("1", "Adria Airways Tehnika d.d.", "22.09.2017"),
        _row("3", "Heinemann Aircraft Interiors GmbH & Co.", "13.10.2017"),
    ])
    rows, errors = parse_interessenten_file(payload, "dev_excel_INT.txt")
    assert errors == []
    assert len(rows) == 2
    assert rows[0]["adress_nr"] == "1"
    assert rows[0]["name"] == "Adria Airways Tehnika d.d."
    assert rows[0]["datum_save"] == date(2017, 9, 22)
    assert rows[1]["datum_save"] == date(2017, 10, 13)


def test_parser_skips_trailing_blank_rows():
    payload = _fixture([
        _row("1", "Adria Airways Tehnika d.d.", "22.09.2017"),
        "\t" * 87,  # fully blank padding row
        "\t" * 87,
    ])
    rows, errors = parse_interessenten_file(payload, "f.txt")
    assert len(rows) == 1
    assert errors == []


def test_parser_reports_unparseable_date():
    payload = _fixture([
        _row("99", "Bad Date", "NOT-A-DATE"),
    ])
    rows, errors = parse_interessenten_file(payload, "f.txt")
    assert rows == []
    assert any("Datum Save" in e["field"] for e in errors)


def test_parser_reports_missing_adress_nr():
    payload = _fixture([
        _row("", "Someone", "01.01.2024"),
    ])
    rows, errors = parse_interessenten_file(payload, "f.txt")
    assert rows == []
    assert any("Adress-Nr." in e["field"] for e in errors)


def test_parser_last_wins_on_duplicate_adress_nr():
    """Same Adress-Nr. on two rows → last one wins, matching the DB upsert."""
    payload = _fixture([
        _row("42", "Old Name", "01.01.2024"),
        _row("42", "New Name", "15.06.2024"),
    ])
    rows, errors = parse_interessenten_file(payload, "f.txt")
    assert errors == []
    assert len(rows) == 1
    assert rows[0]["name"] == "New Name"
    assert rows[0]["datum_save"] == date(2024, 6, 15)


def test_parser_accepts_utf8_when_no_latin1_bytes_present():
    title = "Adressen\tInteressenten" + "\t" * 86
    # Replace umlauts in the header with utf-8 bytes.
    header_utf8 = "\t".join([
        c.replace("\xdf", "ß").replace("\xe4", "ä") for c in HEADER_COLS_88
    ])
    body = "\r\n".join([title, header_utf8, _row("1", "Foo", "01.01.2024"), ""])
    payload = body.encode("utf-8")
    rows, errors = parse_interessenten_file(payload, "f.txt")
    assert errors == []
    assert rows[0]["adress_nr"] == "1"


def test_parser_rejects_file_missing_required_header():
    bad = b"Adressen\tInteressenten\r\nFoo\tBar\r\n1\tIvan\r\n"
    rows, errors = parse_interessenten_file(bad, "f.txt")
    assert rows == []
    assert any("Missing required column" in e["message"] for e in errors)
