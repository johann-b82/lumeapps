"""Befund 17: der UNC-Erbauer lässt niemanden aus der Freigabe heraus."""
from __future__ import annotations

import pytest

from app.services.atr_fileserver import AtrFileserverError, _unc


def test_gewoehnlicher_pfad():
    assert _unc("srv", "daten", "eingang", "a.pdf") == r"\\srv\daten\eingang\a.pdf"


def test_schraegstriche_werden_vereinheitlicht():
    assert _unc("srv", "daten", "a/b", "c.pdf") == r"\\srv\daten\a\b\c.pdf"


def test_leere_bestandteile_fallen_weg():
    assert _unc("srv", "daten", "", "//") == r"\\srv\daten"


def test_einzelner_punkt_faellt_weg():
    assert _unc("srv", "daten", "./eingang", "a.pdf") == r"\\srv\daten\eingang\a.pdf"


@pytest.mark.parametrize(
    "teil",
    ["..", "../..", r"eingang\..\..\windows", "eingang/../../etc", r"..\geheim"],
)
def test_aufstieg_wird_abgelehnt(teil):
    with pytest.raises(AtrFileserverError):
        _unc("srv", "daten", teil)


def test_aufstieg_auch_im_dateinamen():
    """Der Name kommt vom Dateiserver — auch der ist keine vertrauenswürdige Quelle."""
    with pytest.raises(AtrFileserverError):
        _unc("srv", "daten", "eingang", "..\\..\\boese.pdf")
