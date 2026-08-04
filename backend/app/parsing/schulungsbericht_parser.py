"""Parser für hochgeladene Schulungsberichte (PDF) — zwei Formblätter.

Der „Stand der Mitarbeiter" lässt sich aus zwei QM-Formblättern fortschreiben:

* **Formblatt 68 — „Schulungsnachweis (intern)"**: EIN Schulungstermin mit einem
  Titel + Datum und einer Teilnehmerliste (Name, Vorname). Ergibt eine Zeile je
  Teilnehmer (dieselbe Schulung, dasselbe Datum).
* **Formblatt 71 — „Schulungsübersicht"**: EIN Mitarbeiter (Name) mit einer Tabelle
  absolvierter Maßnahmen (Zeitraum + Bezeichnung). Ergibt eine Zeile je Maßnahme
  (derselbe Mitarbeiter, Datum = Ende des Zeitraums).

Die PDFs sind digitale Formulare (kein Scan) — der Text wird mit ``pdftotext
-layout`` extrahiert (poppler ist im api-Image vorhanden). Der Parser ist bewusst
tolerant und rät nichts: Was er nicht sicher zuordnen kann, bleibt leer und wird
später in der Vorschau als „nicht zugeordnet" sichtbar, statt still geschrieben.
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import date

_DATE_RE = re.compile(r"(\d{2})\.(\d{2})\.(\d{4})")
_START_RE = re.compile(r"^\s*(\d{2})\s+(\d{2}\.\d{2}\.\d{4})\s*[-–]?\s*(.*)$")
#: Zeile, die MIT einem Datum beginnt (Enddatum des Zeitraums), optional gefolgt
#: von Bezeichnungs-Fortsetzung. Layout-abhängig steht dahinter Text oder nichts.
_LEADDATE_RE = re.compile(r"^\s*(\d{2}\.\d{2}\.\d{4})\s*(.*)$")
_FOOTER_RE = re.compile(
    r"aktualisiert am|freigegeben von|ausgabedatum|erstellt von", re.IGNORECASE
)


class SchulungsberichtError(Exception):
    """Datei ist kein lesbares/erkanntes Schulungsbericht-PDF."""


@dataclass
class BerichtZeile:
    """Eine extrahierte Teilnahme aus dem Bericht (roh, noch nicht zugeordnet)."""

    mitarbeiter_name: str
    schulung_name: str
    datum: date | None
    quelle: str  # "fbl68" | "fbl71"


def pdf_zu_text(daten: bytes) -> str:
    """PDF-Bytes → Layout-Text via ``pdftotext -layout -enc UTF-8``."""
    with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
        tmp.write(daten)
        tmp.flush()
        try:
            fertig = subprocess.run(
                ["pdftotext", "-layout", "-enc", "UTF-8", tmp.name, "-"],
                capture_output=True,
                timeout=30,
            )
        except FileNotFoundError as exc:  # pragma: no cover - Umgebungsfehler
            raise SchulungsberichtError("pdftotext ist nicht verfügbar.") from exc
        except subprocess.TimeoutExpired as exc:
            raise SchulungsberichtError("PDF-Auswertung hat zu lange gedauert.") from exc
    if fertig.returncode != 0:
        raise SchulungsberichtError("PDF konnte nicht gelesen werden.")
    return fertig.stdout.decode("utf-8", errors="replace")


def _datum(text: str | None) -> date | None:
    m = _DATE_RE.search(text or "")
    if not m:
        return None
    d, mo, y = (int(x) for x in m.groups())
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def _nach_doppelpunkt(zeile: str) -> str:
    return zeile.split(":", 1)[1].strip() if ":" in zeile else ""


def erkenne_format(text: str) -> str | None:
    """"fbl68" / "fbl71" / None anhand des Formblatt-Kopfes."""
    if "Formblatt 68" in text or "Schulungsnachweis" in text:
        return "fbl68"
    if "Formblatt 71" in text or "Schulungsübersicht" in text:
        return "fbl71"
    return None


def _parse_fbl68(zeilen: list[str]) -> list[BerichtZeile]:
    """1 Schulung × N Teilnehmer (Titel + Datum + nummerierte Teilnehmerliste)."""
    titel: str | None = None
    datum: date | None = None
    teilnehmer: list[str] = []
    in_liste = False
    for ln in zeilen:
        s = ln.strip().lower()
        if s.startswith("titel der lehrveranstaltung"):
            titel = _nach_doppelpunkt(ln)
        elif s.startswith("datum der lehrveranstaltung"):
            datum = _datum(ln)
        elif s.startswith("nr. teilnehmer"):
            in_liste = True
        elif s.startswith("durchführung"):
            in_liste = False
        elif in_liste:
            m = re.match(r"^\s*\d+\s+(.+?)\s*$", ln)
            if m and m.group(1).strip():
                teilnehmer.append(re.sub(r"\s{2,}", " ", m.group(1).strip()))
    if not titel:
        return []
    return [
        BerichtZeile(mitarbeiter_name=t, schulung_name=titel, datum=datum, quelle="fbl68")
        for t in teilnehmer
    ]


def _parse_fbl71(zeilen: list[str]) -> list[BerichtZeile]:
    """1 Mitarbeiter × N Maßnahmen (Name + Maßnahmen-Tabelle)."""
    name: str | None = None
    for ln in zeilen:
        if ln.strip().lower().startswith("name:"):
            name = _nach_doppelpunkt(ln)
            break
    if not name:
        return []

    eintraege: list[BerichtZeile] = []
    i = 0
    while i < len(zeilen):
        m = _START_RE.match(zeilen[i])
        if not m:
            i += 1
            continue
        startdatum = _datum(m.group(2))
        # IN/EX-Kreuz sitzt rechts außen — als "  X" am Zeilenende entfernen.
        bez = re.sub(r"\s+X\s*$", "", m.group(3)).strip()
        i += 1
        enddatum: date | None = None
        # Bis zur Enddatum-Zeile: Zeilen ohne führendes Datum sind Bezeichnungs-
        # Fortsetzung (Layout A). Die Enddatum-Zeile beginnt mit dem Datum und
        # kann dahinter noch Bezeichnungs-Text tragen (Layout B).
        while i < len(zeilen):
            zeile = zeilen[i]
            s = zeile.strip()
            if _START_RE.match(zeile) or _FOOTER_RE.search(s):
                break
            dm = _LEADDATE_RE.match(zeile)
            if dm:
                enddatum = _datum(dm.group(1))
                rest = re.sub(r"\s+X\s*$", "", dm.group(2)).strip()
                if rest:
                    bez += " " + rest
                i += 1
                break  # danach folgt der Anbieter-/Adressblock
            if s:  # Bezeichnungs-Fortsetzung vor dem Enddatum
                bez += " " + re.sub(r"\s+X\s*$", "", s).strip()
            i += 1
        # Anbieter-/Adressblock nach dem Enddatum überspringen.
        while (
            i < len(zeilen)
            and not _START_RE.match(zeilen[i])
            and not _FOOTER_RE.search(zeilen[i].strip())
        ):
            i += 1
        bez = re.sub(r"\s{2,}", " ", bez).strip()
        if bez:
            eintraege.append(
                BerichtZeile(
                    mitarbeiter_name=name,
                    schulung_name=bez,
                    datum=enddatum or startdatum,
                    quelle="fbl71",
                )
            )
    return eintraege


def parse_bericht(daten: bytes) -> tuple[str, list[BerichtZeile]]:
    """PDF-Bytes → (Format, Zeilen). Wirft :class:`SchulungsberichtError` bei Fehler."""
    text = pdf_zu_text(daten)
    fmt = erkenne_format(text)
    if fmt is None:
        raise SchulungsberichtError(
            "Unbekanntes Formular — erwartet Formblatt 68 (Schulungsnachweis) "
            "oder Formblatt 71 (Schulungsübersicht)."
        )
    zeilen = text.splitlines()
    rows = _parse_fbl68(zeilen) if fmt == "fbl68" else _parse_fbl71(zeilen)
    return fmt, rows
