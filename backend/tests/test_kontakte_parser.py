from datetime import date

from app.parsing.kontakte_parser import parse_kontakte_file


def _build(rows: list[bytes]) -> bytes:
    """Build a minimal Kontakte dump (header + rows) in iso-8859-1."""
    header = (
        b'="Datum"\t="Wer"\t="Typ"\t="Gruppe"\t="Sta"\t="Name"\t='
        b'"Kommentar"\t="VrgID"\r\n'
    )
    return header + b"".join(rows)


def test_parser_returns_one_row_with_canonical_fields():
    body = _build([
        b'08.02.2012\t="KARRER"\t="ERS"\t="L"\t1\t='
        b'"Sonatech GmbH + Co.KG"\t="Angebot 5000000"\t1\r\n'
    ])
    rows, errors = parse_kontakte_file(body, "kontakte.txt")
    assert errors == []
    assert len(rows) == 1
    r = rows[0]
    assert r["contact_date"] == date(2012, 2, 8)
    assert r["employee_token"] == "KARRER"
    assert r["contact_type"] == "ERS"
    assert r["customer_group"] == "L"
    assert r["status"] == 1
    assert r["customer_name"] == "Sonatech GmbH + Co.KG"
    assert r["comment"].startswith("Angebot")
    assert r["external_id"] == "1"
    assert r["raw"]["Wer"] == "KARRER"


def test_parser_keeps_status_zero_rows_for_caller_to_filter():
    # KPI rules drop status=0 at compute time; the parser should not lose them.
    body = _build([
        b'08.02.2012\t="X"\t="ERS"\t="L"\t0\t="A"\t="x"\t1\r\n',
    ])
    rows, _ = parse_kontakte_file(body, "k.txt")
    assert rows[0]["status"] == 0


def test_parser_skips_rows_with_unparseable_date_or_blank_wer():
    body = _build([
        b'NOTADATE\t="X"\t="ERS"\t="L"\t1\t="A"\t="x"\t1\r\n',
        b'08.02.2012\t=""\t="ERS"\t="L"\t1\t="A"\t="x"\t2\r\n',
        b'09.02.2012\t="Y"\t="ORT"\t="L"\t1\t="B"\t="y"\t3\r\n',
    ])
    rows, errors = parse_kontakte_file(body, "k.txt")
    assert len(rows) == 1
    assert rows[0]["employee_token"] == "Y"
    assert len(errors) == 2


def test_parser_uppercases_wer_token():
    body = _build([b'08.02.2012\t="karrer"\t=""\t=""\t1\t=""\t=""\t1\r\n'])
    rows, _ = parse_kontakte_file(body, "k.txt")
    assert rows[0]["employee_token"] == "KARRER"
