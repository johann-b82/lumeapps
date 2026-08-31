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
        1: "Die Arbeitsergebnisse von [NAME] waren stets von hervorragender "
        "Qualität.",
        2: "Die Arbeitsergebnisse von [NAME] waren von sehr guter Qualität.",
        3: "Die Arbeitsergebnisse von [NAME] entsprachen stets den Erwartungen.",
        4: "Die Arbeitsergebnisse von [NAME] entsprachen den Erwartungen.",
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
        1: "Das Verhalten von [NAME] gegenüber Vorgesetzten, Kolleginnen und "
        "Kollegen sowie Kundinnen und Kunden war stets vorbildlich und von "
        "Respekt und Hilfsbereitschaft geprägt.",
        2: "Das Verhalten von [NAME] gegenüber Vorgesetzten, Kolleginnen und "
        "Kollegen sowie Kundinnen und Kunden war stets einwandfrei.",
        3: "Das Verhalten von [NAME] gegenüber Vorgesetzten, Kolleginnen und "
        "Kollegen sowie Kundinnen und Kunden war einwandfrei.",
        4: "Das Verhalten von [NAME] gegenüber Vorgesetzten, Kolleginnen und "
        "Kollegen sowie Kundinnen und Kunden gab keinen Anlass zu Beanstandungen.",
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


def _stichpunkte(text: str | None) -> str | None:
    """Freitext-Aufzählung zu einer Semikolon-Liste normalisieren."""
    if not text or not text.strip():
        return None
    teile = [
        z.strip(" \t-•*")
        for z in text.replace(";", "\n").splitlines()
        if z.strip(" \t-•*")
    ]
    return "; ".join(teile) if teile else None


def _satz(*teile: str | None) -> str:
    """Nicht-leere Teile zu einem Absatz verbinden."""
    return " ".join(t for t in teile if t)


def _einleitung(*, art, taetigkeit, abteilung, eintritt, austritt, firma) -> str:
    tk = taetigkeit or "Mitarbeiter/in"
    haus = f"bei {firma}" if firma else "in unserem Hause"
    ein, aus = _d(eintritt), _d(austritt)
    if art == "zwischenzeugnis":
        seit = f"seit dem {ein} " if ein else ""
        return f"[NAME] ist {seit}als {tk} {haus} tätig."
    if art == "ausbildungszeugnis":
        zeitraum = f"vom {ein} bis zum {aus} " if ein and aus else ""
        return f"[NAME] absolvierte {zeitraum}{haus} eine Ausbildung zum/zur {tk}."
    if art == "praktikumszeugnis":
        bereich = abteilung or tk
        zeitraum = f"vom {ein} bis zum {aus} " if ein and aus else ""
        return f"[NAME] absolvierte {zeitraum}{haus} ein Praktikum im Bereich {bereich}."
    # qualifiziert / einfach
    abt = f" in der Abteilung {abteilung}" if abteilung else ""
    if ein and aus:
        zeit = f"vom {ein} bis zum {aus}"
    elif ein:
        zeit = f"seit dem {ein}"
    else:
        zeit = "in unserem Unternehmen"
    return f"[NAME] war {zeit} als {tk}{abt} {haus} beschäftigt.".replace("  ", " ")


def _taetigkeit(*, taetigkeit, stichpunkte, kompetenzen, fuehrungskraft) -> str:
    tk = taetigkeit or "die übertragenen Aufgaben"
    liste = _stichpunkte(stichpunkte)
    if liste:
        kern = f"Zu den Aufgaben von [NAME] als {tk} gehörten insbesondere: {liste}."
    else:
        kern = f"[NAME] war mit den Aufgaben als {tk} betraut."
    fuehrung = (
        "Dabei trug [NAME] Verantwortung für die fachliche und disziplinarische "
        "Führung eines Teams." if fuehrungskraft else None
    )
    komp = _stichpunkte(kompetenzen)
    komp_satz = f"Besondere Stärken zeigte [NAME] in folgenden Bereichen: {komp}." if komp else None
    return _satz(kern, fuehrung, komp_satz)


def _leistung(*, noten, schnitt, erfolge, fuehrungskraft) -> str:
    saetze: list[str] = []
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


def _schluss(*, art, schnitt, austritt, anlass) -> str:
    aus = _d(austritt)
    gut = schnitt is not None and _runde(schnitt) <= 2
    if art == "zwischenzeugnis":
        grund = (anlass or "").strip() or "auf Wunsch von [NAME]"
        return f"Dieses Zwischenzeugnis wird {grund} ausgestellt."
    if art == "einfach":
        return f"Das Arbeitsverhältnis endete zum {aus}." if aus else \
            "Das Arbeitsverhältnis wurde ordnungsgemäß beendet."
    if art == "ausbildungszeugnis":
        ende = f"Die Ausbildung endete zum {aus}. " if aus else ""
        return (
            f"{ende}Wir danken [NAME] für die Mitarbeit während der Ausbildung "
            "und wünschen für den weiteren Berufs- und Lebensweg alles Gute."
        )
    if art == "praktikumszeugnis":
        return (
            "Wir danken [NAME] für das gezeigte Engagement während des Praktikums "
            "und wünschen für die Zukunft alles Gute."
        )
    # qualifiziert
    ende = f"Das Arbeitsverhältnis endet zum {aus} im besten gegenseitigen Einvernehmen. " if aus else ""
    if gut:
        return (
            "Wir danken [NAME] für die stets sehr guten Leistungen und die "
            f"überaus angenehme Zusammenarbeit. {ende}Wir bedauern das Ausscheiden "
            "von [NAME] und wünschen für die berufliche und persönliche Zukunft "
            "weiterhin viel Erfolg und alles Gute."
        )
    return (
        f"Wir danken [NAME] für die Zusammenarbeit. {ende}Für die Zukunft "
        "wünschen wir [NAME] alles Gute."
    )


def baue_abschnitte(
    *,
    geschlecht: str | None,
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
    firma: str | None,
) -> dict[str, str]:
    """Baut die fünf Abschnitte deterministisch aus Textbausteinen.

    ``einfach`` lässt Leistungs- und Verhaltensbeurteilung bewusst leer.
    Rückgabe: ``{schluessel: text}`` für alle ``ZEUGNIS_ABSCHNITTE``.
    """
    einfach = art == "einfach"
    daten = {
        "einleitung": _einleitung(
            art=art, taetigkeit=taetigkeit, abteilung=abteilung,
            eintritt=eintritt, austritt=austritt, firma=firma,
        ),
        "taetigkeitsbeschreibung": _taetigkeit(
            taetigkeit=taetigkeit, stichpunkte=stichpunkte,
            kompetenzen=kompetenzen, fuehrungskraft=fuehrungskraft,
        ),
        "leistungsbeurteilung": "" if einfach else _leistung(
            noten=noten, schnitt=schnitt, erfolge=erfolge, fuehrungskraft=fuehrungskraft,
        ),
        "sozialverhalten": "" if einfach else _sozial(noten=noten, schnitt=schnitt),
        "schlussformel": _schluss(
            art=art, schnitt=schnitt, austritt=austritt, anlass=anlass,
        ),
    }
    return {k: daten.get(k, "") for k in ZEUGNIS_ABSCHNITTE}
