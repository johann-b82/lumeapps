"""KI-Textgenerierung für Arbeitszeugnisse (v1.110).

Übersetzt die vergebenen Einzelnoten und die HR-Freitexte in wohlwollende,
rechtssichere deutsche Zeugnissprache — gegliedert in die Abschnitte aus
:data:`app.models.zeugnis.ZEUGNIS_ABSCHNITTE`.

**Datensparsamkeit (bewusste Entscheidung):** An die Anthropic-API gehen nur
Anrede/Geschlecht, Rolle, Abteilung, Beschäftigungsdauer, Noten und die
HR-Freitexte. **Name, Geburtsdatum und Personalnummer verlassen den Server
nicht** — die KI setzt den Platzhalter ``[NAME]``, den der Aufrufer lokal durch
„Herr/Frau Nachname" ersetzt.

``anthropic`` wird lazy importiert: Ohne installiertes Paket oder ohne
``ANTHROPIC_API_KEY`` bleibt das Feature inert (der Aufrufer bekommt einen
sprechenden Fehler und mappt ihn auf HTTP 503).
"""
from __future__ import annotations

import json
import logging
from datetime import date

from app.config import settings
from app.models.zeugnis import ZEUGNIS_ABSCHNITTE

log = logging.getLogger(__name__)

#: Note (1–4) → Wortlaut (Schulnotenprinzip).
_NOTE_WORT = {1: "sehr gut", 2: "gut", 3: "befriedigend", 4: "ausreichend"}

#: Anzeigename je Dimension für den Prompt.
_DIM_LABEL = {
    "fachwissen": "Fachwissen / Fachkönnen",
    "auffassungsgabe": "Auffassungsgabe",
    "arbeitsweise": "Arbeitsweise",
    "belastbarkeit": "Belastbarkeit",
    "arbeitserfolg": "Arbeitserfolg / Arbeitsqualität",
    "sozialverhalten": "Sozialverhalten (Vorgesetzte, Kollegen, Kunden)",
    "fuehrung": "Führungsleistung",
}

#: Art-spezifische Anweisung (ergänzt den Prompt je Zeugnisart).
_ART_HINWEIS = {
    "qualifiziert": (
        "Erstelle ein VOLLES qualifiziertes Arbeitszeugnis mit Tätigkeits-, "
        "Leistungs- und Verhaltensbeurteilung sowie Dank-/Bedauern-Schlussformel."
    ),
    "einfach": (
        "Erstelle ein EINFACHES Zeugnis: nur Tätigkeitsbeschreibung, "
        "Beschäftigungsdauer und eine knappe, neutrale Schlussformel. KEINE "
        "Leistungs- oder Verhaltensbewertung — lass 'leistungsbeurteilung' und "
        "'sozialverhalten' leer."
    ),
    "zwischenzeugnis": (
        "Erstelle ein ZWISCHENZEUGNIS im PRÄSENS (das Arbeitsverhältnis besteht "
        "fort). Die Schlussformel nennt den Anlass der Ausstellung und enthält "
        "KEINE Abschieds-/Bedauern-Formel."
    ),
    "ausbildungszeugnis": (
        "Erstelle ein AUSBILDUNGSZEUGNIS: Bezeichne die Person als "
        "Auszubildende:n, nenne Ausbildungsberuf/-bereich und Ausbildungsdauer, "
        "beschreibe die vermittelten Ausbildungsinhalte/Kenntnisse und die "
        "Bewährung während der Ausbildung."
    ),
    "praktikumszeugnis": (
        "Erstelle ein PRAKTIKUMSZEUGNIS: Bezeichne die Person als Praktikant:in, "
        "nenne Praktikumsdauer und Einsatzbereich; halte es kürzer und bewerte "
        "Einsatz und Verhalten passend zum Praktikumskontext."
    ),
}

_SYSTEM = (
    "Du bist erfahrene:r Personalreferent:in in Deutschland und formulierst "
    "Arbeits-, Ausbildungs- und Praktikumszeugnisse. Beachte strikt:\n"
    "- Wohlwollende, verkehrsübliche Zeugnissprache; die Gesamtaussage muss der "
    "genannten Note entsprechen (Zufriedenheitsskala: Note 1 = 'stets zu unserer "
    "vollsten Zufriedenheit', 2 = 'stets zu unserer vollen Zufriedenheit', "
    "3 = 'zu unserer vollen Zufriedenheit', 4 = 'zu unserer Zufriedenheit').\n"
    "- Klar, sachlich, keine widersprüchlichen Aussagen, keine unzulässigen "
    "Geheimcodes, keine Angaben zu Gesundheit, Religion, Herkunft, "
    "Gewerkschafts-/Betriebsratstätigkeit.\n"
    "- Die Person wird ausschließlich als Platzhalter '[NAME]' bezeichnet "
    "(steht für 'Herr/Frau Nachname'). Verwende sonst korrekte Anrede und "
    "grammatische Formen gemäß dem angegebenen Geschlecht.\n"
    "- Nutze die HR-Freitexte (Aufgaben, besondere Kompetenzen, Erfolge), sofern "
    "vorhanden.\n"
    "Antworte AUSSCHLIESSLICH mit einem JSON-Objekt mit genau diesen Schlüsseln: "
    + ", ".join(ZEUGNIS_ABSCHNITTE)
    + ". Jeder Wert ist der fertige deutsche Fließtext dieses Abschnitts (keine "
    "Aufzählungszeichen außer in der Tätigkeitsbeschreibung, wo eine kurze "
    "Aufgabenliste als Fließtext oder mit Semikolon getrennt zulässig ist)."
)


class ZeugnisKIError(RuntimeError):
    """KI nicht verfügbar oder Antwort unbrauchbar — vom Router auf 503 gemappt."""


def _anrede(geschlecht: str | None) -> str:
    return {"w": "Frau", "m": "Herr"}.get((geschlecht or "").lower(), "Herr/Frau")


def _jahre(eintritt: date | None, austritt: date | None) -> str | None:
    if not eintritt:
        return None
    ende = austritt or date.today()
    monate = (ende.year - eintritt.year) * 12 + (ende.month - eintritt.month)
    if monate < 12:
        return f"rund {max(monate, 1)} Monate"
    jahre = monate // 12
    return f"rund {jahre} Jahr{'e' if jahre != 1 else ''}"


def _eingaben(
    *,
    geschlecht: str | None,
    taetigkeit: str | None,
    abteilung: str | None,
    eintritt: date | None,
    austritt: date | None,
    art: str,
    fuehrungskraft: bool,
    noten: dict[str, int],
    stichpunkte: str | None,
    kompetenzen: str | None,
    erfolge: str | None,
) -> dict:
    """Der pseudonymisierte Payload — ohne Name/Geburtsdatum/Personalnummer."""
    return {
        "anrede": _anrede(geschlecht),
        "geschlecht": geschlecht or "unbekannt",
        "position": taetigkeit or "—",
        "abteilung": abteilung or "—",
        "beschaeftigungsdauer": _jahre(eintritt, austritt) or "—",
        "eintritt": eintritt.isoformat() if eintritt else None,
        "austritt": austritt.isoformat() if austritt else None,
        "zeugnisart": art,
        "fuehrungskraft": fuehrungskraft,
        "bewertung": [
            {
                "dimension": _DIM_LABEL.get(dim, dim),
                "note": note,
                "note_wort": _NOTE_WORT.get(note, str(note)),
            }
            for dim, note in noten.items()
        ],
        "aufgaben_stichpunkte": (stichpunkte or "").strip() or None,
        "besondere_kompetenzen": (kompetenzen or "").strip() or None,
        "besondere_erfolge": (erfolge or "").strip() or None,
    }


def _parse_json(text: str) -> dict:
    roh = text.strip()
    if roh.startswith("```"):
        # ```json … ``` entkernen
        roh = roh.split("```", 2)[1]
        if roh.lstrip().lower().startswith("json"):
            roh = roh.lstrip()[4:]
    roh = roh.strip().strip("`").strip()
    return json.loads(roh)


async def generiere_abschnitte(
    *,
    geschlecht: str | None,
    taetigkeit: str | None,
    abteilung: str | None,
    eintritt: date | None,
    austritt: date | None,
    art: str,
    fuehrungskraft: bool,
    noten: dict[str, int],
    stichpunkte: str | None,
    kompetenzen: str | None,
    erfolge: str | None,
) -> dict[str, str]:
    """Ruft Claude und liefert die Zeugnis-Abschnitte als ``{schluessel: text}``.

    Raises:
        ZeugnisKIError: Paket fehlt, kein Key, oder unbrauchbare Antwort.
    """
    if not settings.ANTHROPIC_API_KEY:
        raise ZeugnisKIError(
            "Kein ANTHROPIC_API_KEY konfiguriert — KI-Generierung ist inaktiv."
        )
    try:
        import anthropic  # lazy: Paket ist erst nach Image-Rebuild vorhanden
    except ImportError as exc:  # pragma: no cover
        raise ZeugnisKIError(
            "Python-Paket 'anthropic' ist im Image nicht installiert "
            "(requirements.txt + Rebuild nötig)."
        ) from exc

    eingaben = _eingaben(
        geschlecht=geschlecht,
        taetigkeit=taetigkeit,
        abteilung=abteilung,
        eintritt=eintritt,
        austritt=austritt,
        art=art,
        fuehrungskraft=fuehrungskraft,
        noten=noten,
        stichpunkte=stichpunkte,
        kompetenzen=kompetenzen,
        erfolge=erfolge,
    )

    client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
    try:
        antwort = await client.messages.create(
            model=settings.ZEUGNIS_MODEL,
            max_tokens=4000,
            thinking={"type": "adaptive"},
            system=_SYSTEM,
            messages=[
                {
                    "role": "user",
                    "content": (
                        "Zeugnisart-Hinweis: "
                        + _ART_HINWEIS.get(art, _ART_HINWEIS["qualifiziert"])
                        + "\n\nErstelle den Zeugnistext aus diesen Angaben (JSON):\n\n"
                        + json.dumps(eingaben, ensure_ascii=False, indent=2)
                    ),
                }
            ],
        )
    except anthropic.APIError as exc:
        raise ZeugnisKIError(f"Anthropic-API-Fehler: {exc}") from exc

    if antwort.stop_reason == "refusal":
        raise ZeugnisKIError("Die KI hat die Anfrage abgelehnt (Sicherheitsfilter).")

    text = "".join(b.text for b in antwort.content if b.type == "text").strip()
    try:
        daten = _parse_json(text)
    except (json.JSONDecodeError, IndexError) as exc:
        log.warning("Zeugnis-KI: JSON nicht parsebar: %s", text[:200])
        raise ZeugnisKIError("KI-Antwort war kein gültiges JSON.") from exc

    return {k: str(daten.get(k, "")).strip() for k in ZEUGNIS_ABSCHNITTE}
