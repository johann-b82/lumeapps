"""Tests für den Rechenkern der Produktions-Priorisierung (v1.126) — ohne DB."""
from datetime import date
from decimal import Decimal

from app.services.produktion_prio import (
    ListenTreffer,
    PlanZeile,
    automatische_reihenfolge,
    bereich_fuer,
    loese_auf,
    waehle_treffer,
    wende_manuell_an,
)


def _t(liste_id, stand, rang=None, termin=None):
    return ListenTreffer(liste_id=liste_id, liste_name="L", stand=stand, rang=rang, termin=termin, kommentar=None)


def test_neueste_liste_gewinnt():
    alt = _t(1, date(2026, 9, 1), rang=1)
    neu = _t(2, date(2026, 9, 14), rang=40)
    assert waehle_treffer([neu, alt]) is neu
    assert waehle_treffer([]) is None


def test_automatisch_nach_termin_dann_rang_dann_ba():
    a, b, c, d = ("1024906", 1, 0), ("1024900", 2, 0), ("1024800", 1, 0), ("1024700", 1, 0)
    positionen = {a: date(2026, 9, 1), b: date(2026, 9, 1), c: date(2026, 8, 1), d: None}
    treffer = {
        a: _t(1, date(2026, 9, 14), rang=2),
        b: _t(1, date(2026, 9, 14), rang=5),
        # Listen-Termin ersetzt das Lieferdatum
        c: _t(1, date(2026, 9, 14), termin=date(2026, 9, 1)),
    }
    assert automatische_reihenfolge(positionen, treffer) == [a, b, c, d]


def test_manuell_belegt_eigene_plaetze_neue_bleiben_automatisch():
    a, b, c, neu = ("1", 1, 0), ("2", 1, 0), ("3", 1, 0), ("4", 1, 0)
    auto = [a, neu, b, c]
    manuell = {c: 0, a: 1, b: 2}
    assert wende_manuell_an(auto, manuell) == [c, neu, a, b]


def test_bereich_zuordnung():
    assert bereich_fuer("41000") == "wandverkleidung"
    assert bereich_fuer("10000MA01") == "zuschnitt"
    assert bereich_fuer("128000") == "fremdvergabe"
    assert bereich_fuer("91000") == "sonstige"


def _res(pos, ref, op="10", ruest="5"):
    return PlanZeile(pos=pos, typ="RES", ref=ref, text=None, menge=None, kostenstelle=None,
                     ruestzeit=Decimal(ruest), operativzeit=Decimal(op))


def _komp(pos, ref, menge="1"):
    return PlanZeile(pos=pos, typ="HLB", ref=ref, text=None, menge=Decimal(menge), kostenstelle=None,
                     ruestzeit=None, operativzeit=None)


def test_aufloesung_rekursiv_mit_mengen_und_zyklenschutz():
    plan = {
        "6817": [_komp(1, "H3058"), _res(3, "41000"), _res(4, "70000")],
        "H3058": [_komp(1, "H0189", menge="4"), _res(12, "41000")],
        "H0189": [_res(1, "16000"), _komp(2, "H3058")],  # Zyklus zurück
    }
    t = loese_auf("6817", plan)
    assert [(x.pfad, x.ressource, x.ebene) for x in t] == [
        ("1.1.1", "16000", 2), ("1.12", "41000", 1), ("3", "41000", 0), ("4", "70000", 0)]
    assert t[0].menge == Decimal(4)
    assert t[0].bereich == "zuschnitt"
