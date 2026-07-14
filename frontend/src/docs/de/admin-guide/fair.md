# FAIR – Erstmusterprüfung / Zeichnungs-Ballooning

FAIR ist das Werkzeug für die Erstmusterprüfung (First Article Inspection Report): Du lädst eine technische Zeichnung hoch, markierst darauf die zu prüfenden Merkmale (Maße, Toleranzen, Angaben) und FAIR nummeriert sie automatisch durch – klassisches „Ballooning". Jedes markierte Merkmal wird per OCR ausgelesen, in einer fortlaufenden Werteliste gesammelt und lässt sich am Ende als ballooniertes PDF sowie als Werteliste (CSV/Excel) exportieren. Die Texterkennung läuft mit Tesseract.js komplett im Browser – die Sprachdaten (Deutsch + Englisch) sind lokal mitausgeliefert, es geht also nichts an externe Dienste.

## Zugang

FAIR ist **ausschließlich für Admins**. Die Kachel „FAIR" (türkis-grün, Lineal-Symbol) erscheint im Launcher nur für Admin-Konten; die Routen `/fair` und `/fair/:id` sowie sämtliche `/api/fair/*`-Endpunkte sind admin-gesperrt. Viewer sehen weder Kachel noch Seite.

## 1. Zeichnung hochladen

Auf der FAIR-Startseite ziehst du eine Datei per Drag-and-drop in die Ablagefläche oder wählst sie über **Datei auswählen** aus. Unterstützt werden **PDF, PNG und JPG**. Die Datei wird in Directus gespeichert, ein Projekt angelegt und du landest direkt im Editor.

Bereits vorhandene Projekte stehen darunter, **nach Kunde gruppiert** (Gruppen sind einklappbar und standardmäßig zugeklappt). Über das Suchfeld filterst du live nach Name, Teilenummer, Kunde oder Artikelnummer.

## 2. Projekt-Kopfdaten

Im Editor-Kopf trägst du **Kunde**, **Artikelnummer** und **Teilenummer** ein. Die Felder speichern beim Verlassen bzw. mit Enter. Die Teilenummer wird später als Dateiname des Export-PDFs verwendet.

## 3. Merkmale markieren und ballooniren

Der Editor zeigt die Zeichnung (PDF-Seite oder Bild) mit Zoom, Verschieben (Pan, auch per rechter Maustaste), Drehen und – bei mehrseitigen PDFs – Seitennavigation. Die Ballon-Größe lässt sich global anpassen; Drehung und Ballon-Größe werden gespeichert.

Ablauf im Werkzeug **Hinzufügen**:

1. Ziehe mit gedrückter Maustaste ein Rechteck über das Merkmal.
2. Beim Loslassen startet die **OCR**. Der Ausschnitt wird in allen vier Ausrichtungen erkannt (die Zugrichtung wird bevorzugt) und das beste Ergebnis übernommen.
3. Der erkannte Wert erscheint in einem Eingabefeld und ist **frei editierbar**. Über die Umschalter kannst du gezielt als **Maß** (nur Ziffern/Dimensionszeichen) oder als **Text** neu erkennen lassen.
4. Ein **Klick auf die Zeichnung** setzt die Pfeilspitze (Leader) und bestätigt zugleich den Wert – der Ballon wird gespeichert und vom Server fortlaufend nummeriert.

Mit **Escape** brichst du eine laufende Markierung ab. Ballons lassen sich später per Ziehen an ihrer Spitze verschieben.

## 4. Werteliste prüfen und pflegen

Rechts neben der Zeichnung führt FAIR eine Tabelle aller Ballons (Nr., Wert; neueste oben):

- **Wert inline bearbeiten** – Klick ins Feld, Enter/Verlassen speichert.
- **Erneut erkennen** (Aktualisieren-Symbol) – lässt die OCR für den gespeicherten Bereich der Zeile erneut laufen.
- **Löschen** – entfernt den Ballon; die verbleibenden werden serverseitig neu von 1..n nummeriert.
- **Reihenfolge per Drag-and-drop** – Neusortieren nummeriert alle Ballons neu durch (auch auf der Zeichnung sichtbar).
- **Kopieren** legt die Liste als TSV in die Zwischenablage (direkt in Excel einfügbar); **CSV** lädt eine Datei mit Semikolon und BOM für deutsches Excel herunter.

## 5. Ballonisiertes PDF exportieren

Über **Exportieren** in der Werkzeugleiste erzeugt FAIR ein PDF mit eingebrannten Ballons (bei mehrseitigen PDFs seitengetreu). Der Dateiname folgt der Teilenummer bzw. dem Projektnamen: `<Teilenummer>_ballooned.pdf`.

**Hinweis:** Die OCR ist eine Hilfe, kein Automatismus – bei ungünstigen Zeichnungen kann sie leer bleiben oder danebenliegen. Die manuelle Korrektur ist an jeder Stelle möglich, und du prüfst jeden Wert selbst.
