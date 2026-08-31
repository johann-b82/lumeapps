"""Deterministischer Zeugnis-Baukasten (ohne KI).

Baut die fünf Zeugnis-Abschnitte aus den Stammdaten und den Einzelnoten mit
festen Textbausteinen zusammen — die klassische Zeugnis-„Bausteinmethode".
Jede Note (1–4, Schulnotenprinzip) wählt eine Standardformulierung; die
Gesamtaussage folgt der verkehrsüblichen Zufriedenheitsskala.

Die Person steht — wie im KI-Pfad — als Platzhalter ``[NAME]`` im Text; der
Aufrufer ersetzt ihn lokal durch „Herr/Frau Nachname". Anders als die KI läuft
dieser Baukasten vollständig offline und ohne API-Key.
"""
from __future__ import annotations

from datetime import date

from app.models.zeugnis import ZEUGNIS_ABSCHNITTE

#: Zufriedenheitsskala für den zusammenfassenden Leistungssatz (Note → Wortlaut).
_ZUFRIEDENHEIT = {
    1: "stets zu unserer vollsten Zufriedenheit",
    2: "stets zu unserer vollen Zufriedenheit",
    3: "zu unserer vollen Zufriedenheit",
    4: "zu unserer Zufriedenheit",
}

#: Textbausteine je Dimension und Note (1–4).
_BAUSTEINE: dict[str, dict[int, str]] = {
    "fachwissen": {
        1: "[NAME] verfügte über ein außergewöhnlich fundiertes und breites "
        "Fachwissen, das stets auf dem neuesten Stand war und sicher in der "
        "Praxis angewendet wurde.",
        2: "[NAME] verfügte über ein fundiertes und umfassendes Fachwissen, das "
        "sicher in der Praxis angewendet wurde.",
        3: "[NAME] verfügte über solides Fachwissen, das den Anforderungen "
        "gerecht wurde.",
        4: "[NAME] verfügte über Fachwissen, das den grundlegenden Anforderungen "
        "entsprach.",
    },
    "auffassungsgabe": {
        1: "Neue und komplexe Sachverhalte erfasste [NAME] stets außerordentlich "
        "schnell und setzte sie sicher um.",
        2: "Neue Sachverhalte erfasste [NAME] rasch und setzte sie zuverlässig um.",
        3: "Neue Sachverhalte erfasste [NAME] in angemessener Zeit.",
        4: "Neue Sachverhalte erfasste [NAME] nach entsprechender Einarbeitung.",
    },
    "arbeitsweise": {
        1: "[NAME] arbeitete stets äußerst selbstständig, sorgfältig und "
        "zielgerichtet.",
        2: "[NAME] arbeitete selbstständig, sorgfältig und zielgerichtet.",
        3: "[NAME] arbeitete sorgfältig und zuverlässig.",
        4: "[NAME] arbeitete im Wesentlichen sorgfältig.",
    },
    "belastbarkeit": {
        1: "Auch bei hohem Arbeitsanfall und unter Termindruck war [NAME] "
        "jederzeit außerordentlich belastbar und behielt stets den Überblick.",
        2: "Auch bei hohem Arbeitsanfall war [NAME] belastbar und behielt den "
        "Überblick.",
        3: "Den üblichen Anforderungen war [NAME] auch bei erhöhtem Arbeitsanfall "
        "gewachsen.",
        4: "Den üblichen Anforderungen war [NAME] gewachsen.",
    },
    "arbeitserfolg": {
        1: "[NAME] lieferte stets Arbeitsergebnisse von hervorragender Qualität.",
        2: "[NAME] lieferte Arbeitsergebnisse von sehr guter Qualität.",
        3: "[NAME] lieferte stets Arbeitsergebnisse, die den Erwartungen "
        "entsprachen.",
        4: "[NAME] lieferte Arbeitsergebnisse, die den Erwartungen entsprachen.",
    },
    "fuehrung": {
        1: "Als Führungskraft überzeugte [NAME] durch einen kooperativen, "
        "motivierenden Führungsstil und wurde von den Mitarbeitenden jederzeit "
        "als Vorbild anerkannt.",
        2: "Als Führungskraft führte [NAME] das Team kooperativ und "
        "zielorientiert und wurde von den Mitarbeitenden anerkannt.",
        3: "[NAME] nahm die übertragenen Führungsaufgaben zur Zufriedenheit wahr.",
        4: "[NAME] nahm die übertragenen Führungsaufgaben wahr.",
    },
    "sozialverhalten": {
        1: "[NAME] verhielt sich gegenüber Vorgesetzten, Kolleginnen und Kollegen "
        "sowie Kundinnen und Kunden stets vorbildlich und begegnete allen mit "
        "Respekt und Hilfsbereitschaft.",
        2: "[NAME] verhielt sich gegenüber Vorgesetzten, Kolleginnen und Kollegen "
        "sowie Kundinnen und Kunden stets einwandfrei.",
        3: "[NAME] verhielt sich gegenüber Vorgesetzten, Kolleginnen und Kollegen "
        "sowie Kundinnen und Kunden einwandfrei.",
        4: "[NAME] verhielt sich gegenüber Vorgesetzten, Kolleginnen und Kollegen "
        "sowie Kundinnen und Kunden korrekt; es gab keinen Anlass zu "
        "Beanstandungen.",
    },
}

#: Reihenfolge der Leistungs-Dimensionen (Sozialverhalten hat einen eigenen
#: Abschnitt, Führung nur bei Führungskräften).
_LEISTUNG_DIMS = (
    "fachwissen",
    "auffassungsgabe",
    "arbeitsweise",
    "belastbarkeit",
    "arbeitserfolg",
    "fuehrung",
)


def _d(d: date | None) -> str | None:
    return d.strftime("%d.%m.%Y") if d else None


def _runde(note: float) -> int:
    return min(4, max(1, round(note)))


def _dativ(geschlecht: str | None) -> str:
    """Dativ-Pronomen (für „wir danken …", „wünschen …")."""
    return {"m": "ihm", "w": "ihr"}.get((geschlecht or "").lower(), "ihm bzw. ihr")


def _liste(text: str | None) -> list[str]:
    """Freitext-Aufzählung in Einzelpunkte zerlegen."""
    if not text or not text.strip():
        return []
    return [
        z.strip(" \t-•*")
        for z in text.replace(";", "\n").splitlines()
        if z.strip(" \t-•*")
    ]


def _geb(geburtsdatum: date | None) -> str:
    d = _d(geburtsdatum)
    return f", geboren am {d}," if d else ""


def _einleitung(*, art, geburtsdatum, taetigkeit, abteilung, eintritt, austritt) -> str:
    tk = taetigkeit or "Mitarbeiter/in"
    abt = f" in der Abteilung {abteilung}" if abteilung else ""
    geb = _geb(geburtsdatum)
    ein, aus = _d(eintritt), _d(austritt)
    if art == "zwischenzeugnis":
        seit = f"seit dem {ein} " if ein else ""
        return f"[NAME]{geb} ist {seit}{abt.strip()} als {tk} in unserem Unternehmen tätig.".replace("  ", " ")
    if art == "ausbildungszeugnis":
        zeitraum = f"vom {ein} bis zum {aus} " if ein and aus else ""
        return f"[NAME]{geb} absolvierte {zeitraum}in unserem Unternehmen eine Ausbildung zum/zur {tk}."
    if art == "praktikumszeugnis":
        bereich = abteilung or tk
        zeitraum = f"vom {ein} bis zum {aus} " if ein and aus else ""
        return f"[NAME]{geb} absolvierte {zeitraum}in unserem Unternehmen ein Praktikum im Bereich {bereich}."
    # qualifiziert / einfach
    if ein and aus:
        zeit = f"vom {ein} bis zum {aus}"
    elif ein:
        zeit = f"seit dem {ein}"
    else:
        zeit = ""
    return f"[NAME]{geb} war {zeit}{abt} als {tk} in unserem Unternehmen tätig.".replace("  ", " ")


def _taetigkeit(*, taetigkeit, stichpunkte) -> str:
    """Lead-in + Aufgaben als Zeilenliste (das Dokument rendert sie als Aufzählung)."""
    tk = taetigkeit or "Mitarbeiter/in"
    punkte = _liste(stichpunkte)
    if not punkte:
        return f"[NAME] war als {tk} mit vielfältigen Aufgaben betraut."
    lead = f"Als {tk} war [NAME] insbesondere für folgende Aufgaben zuständig:"
    return lead + "\n" + "\n".join(punkte)


def _leistung(*, noten, schnitt, kompetenzen, erfolge, fuehrungskraft) -> str:
    saetze: list[str] = []
    komp = _liste(kompetenzen)
    if komp:
        saetze.append(
            "[NAME] brachte fundierte Kenntnisse in folgenden Bereichen ein: "
            + "; ".join(komp) + "."
        )
    for dim in _LEISTUNG_DIMS:
        if dim == "fuehrung" and not fuehrungskraft:
            continue
        note = noten.get(dim)
        if note:
            saetze.append(_BAUSTEINE[dim][note])
    erf = (erfolge or "").strip()
    if erf:
        if erf[-1] not in ".!?":
            erf += "."
        saetze.append(f"Besonders hervorzuheben ist: {erf}")
    if schnitt is not None:
        saetze.append(
            f"Insgesamt erledigte [NAME] die übertragenen Aufgaben "
            f"{_ZUFRIEDENHEIT[_runde(schnitt)]}."
        )
    return " ".join(saetze)


def _sozial(*, noten, schnitt) -> str:
    note = noten.get("sozialverhalten") or (_runde(schnitt) if schnitt is not None else 2)
    return _BAUSTEINE["sozialverhalten"][note]


def _schluss(*, art, geschlecht, schnitt, austritt, anlass) -> str:
    aus = _d(austritt)
    dat = _dativ(geschlecht)
    gut = schnitt is not None and _runde(schnitt) <= 2
    if art == "zwischenzeugnis":
        grund = (anlass or "").strip() or "auf eigenen Wunsch"
        return f"Dieses Zwischenzeugnis wird {grund} ausgestellt."
    if art == "einfach":
        return f"Das Arbeitsverhältnis endete zum {aus}." if aus else \
            "Das Arbeitsverhältnis wurde ordnungsgemäß beendet."
    if art == "ausbildungszeugnis":
        ende = f"Die Ausbildung endete zum {aus}. " if aus else ""
        return (
            f"{ende}Wir danken [NAME] für die Mitarbeit während der Ausbildung "
            f"und wünschen {dat} für den weiteren Berufs- und Lebensweg alles Gute."
        )
    if art == "praktikumszeugnis":
        return (
            "Wir danken [NAME] für das gezeigte Engagement während des Praktikums "
            f"und wünschen {dat} für die Zukunft alles Gute."
        )
    # qualifiziert
    grund = f" {anlass.strip()}" if (anlass or "").strip() else " im besten gegenseitigen Einvernehmen"
    verlaesst = f"[NAME] verlässt unser Unternehmen zum {aus}{grund}. " if aus else ""
    if gut:
        return (
            f"{verlaesst}Wir bedauern dies sehr, denn wir verlieren mit {dat} eine "
            "geschätzte Fachkraft. Wir bedanken uns für die stets sehr guten "
            f"Leistungen und wünschen {dat} für die berufliche und persönliche "
            "Zukunft weiterhin viel Erfolg und alles Gute."
        )
    return (
        f"{verlaesst}Wir danken für die Zusammenarbeit und wünschen {dat} für die "
        "Zukunft alles Gute."
    )


def baue_abschnitte(
    *,
    geschlecht: str | None,
    geburtsdatum: date | None,
    taetigkeit: str | None,
    abteilung: str | None,
    eintritt: date | None,
    austritt: date | None,
    art: str,
    anlass: str | None,
    fuehrungskraft: bool,
    noten: dict[str, int],
    schnitt: float | None,
    stichpunkte: str | None,
    kompetenzen: str | None,
    erfolge: str | None,
) -> dict[str, str]:
    """Baut die fünf Abschnitte deterministisch aus Textbausteinen.

    ``einfach`` lässt Leistungs- und Verhaltensbeurteilung bewusst leer. Die
    Tätigkeitsbeschreibung enthält bei vorhandenen Stichpunkten je Aufgabe eine
    eigene Zeile — das Dokument rendert sie als Aufzählung.
    Rückgabe: ``{schluessel: text}`` für alle ``ZEUGNIS_ABSCHNITTE``.
    """
    einfach = art == "einfach"
    daten = {
        "einleitung": _einleitung(
            art=art, geburtsdatum=geburtsdatum, taetigkeit=taetigkeit,
            abteilung=abteilung, eintritt=eintritt, austritt=austritt,
        ),
        "taetigkeitsbeschreibung": _taetigkeit(
            taetigkeit=taetigkeit, stichpunkte=stichpunkte,
        ),
        "leistungsbeurteilung": "" if einfach else _leistung(
            noten=noten, schnitt=schnitt, kompetenzen=kompetenzen,
            erfolge=erfolge, fuehrungskraft=fuehrungskraft,
        ),
        "sozialverhalten": "" if einfach else _sozial(noten=noten, schnitt=schnitt),
        "schlussformel": _schluss(
            art=art, geschlecht=geschlecht, schnitt=schnitt,
            austritt=austritt, anlass=anlass,
        ),
    }
    return {k: daten.get(k, "") for k in ZEUGNIS_ABSCHNITTE}
