from app.services.sales_aliases import canonical_token


def test_simple():
    assert canonical_token("Karrer") == "KARRER"


def test_already_uppercase_passthrough():
    assert canonical_token("GUENDEL") == "GUENDEL"


def test_umlauts_folded():
    assert canonical_token("Müller") == "MUELLER"
    assert canonical_token("Größe") == "GROESSE"
    assert canonical_token("Bäcker") == "BAECKER"


def test_strips_non_alpha():
    assert canonical_token("O'Brien") == "OBRIEN"
    assert canonical_token("van der Berg") == "VANDERBERG"


def test_empty_returns_empty_string():
    assert canonical_token("") == ""
    assert canonical_token(None) == ""
