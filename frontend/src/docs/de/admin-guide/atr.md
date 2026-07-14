# ATR

ATR ist ein Admin-Werkzeug, das zwei Dinge verbindet: einen **Teilekatalog** (Stammdaten zu Teilenummern, Namen, Zeichnungen, Gewichten) und die Erzeugung von **ATR-Lieferdokumenten**. Du importierst den Katalog aus Excel-Dateien, lädst einen Lieferschein hoch, gleichst dessen Positionen gegen den Katalog ab, prüfst die Kopf- und Positionsdaten und erzeugst daraus die fertigen Ausgabedateien (ATR als XLSX und PDF sowie eine Containerbeschriftung als DOCX).

## Zugang

ATR ist ausschließlich für die **Admin-Rolle**. Alle `/api/atr/*`-Endpunkte sind auf Router-Ebene admin-gesichert; Viewer sehen die ATR-Kachel im Launcher nicht und haben keinen Zugriff auf die Seiten unter `/atr`.

## Teilekatalog importieren

Öffne **ATR → Import** (`/atr/import`).

1. Wähle eine oder mehrere `.xlsx`-Dateien aus und klicke auf **Vorschau**. Es wird nichts gespeichert — du siehst pro Datei eine Auswertung mit den Zählern **Neu**, **Aktualisiert** und **Unverändert** sowie eventuelle **Warnungen**. Jede Teilezeile ist entsprechend ihrem Status eingefärbt.
2. Prüfe die Vorschau. Optional kannst du zwei Häkchen setzen:
   - **Vorlage aktualisieren** — übernimmt die Kopfdaten der Datei in die ATR-Vorlage (siehe Einstellungen).
   - **Struktur setzen** — speichert die hochgeladene Datei als Struktur-Vorlage.
3. Klicke auf **Übernehmen**. Erst jetzt wird geschrieben; die Erfolgsmeldung nennt die Zahl der angelegten und aktualisierten Teile (`+neu / ~aktualisiert`).

Der Abgleich läuft über eine normalisierte Teilenummer. Bestehende Teile werden anhand ihrer Wertfelder (Name, Zeichnung, Gewicht, Menge, Kategorie usw.) als „aktualisiert" oder „unverändert" erkannt.

## Teile verwalten

Unter **ATR → Teile** (`/atr`) durchsuchst du den Katalog (Teilenummer, Name, Lieferanten-Artikelcode) und siehst die Spalten Teilenummer, Name, Kategorie, Zeichnung, Gewicht, PO-Pos und Quelldatei. Über **Bearbeiten** änderst du Name, Zeichnungsnummer, Gewicht und PO-Pos direkt in der Zeile; **Löschen** entfernt ein Teil. Die Quelle zeigt, aus welcher Import-Datei ein Teil stammt (bzw. `(manual)`).

## Lieferungen

Unter **ATR → Lieferungen** (`/atr/deliveries`) startest du eine neue Lieferung auf zwei Wegen:

- **Lieferschein hochladen** — wähle ein `.pdf`. Die Positionen werden ausgelesen und gegen den Katalog abgeglichen; du landest direkt in der Prüfansicht.
- **Aus Ordner** — nur sichtbar, wenn der Fileserver konfiguriert ist. Wähle eine PDF aus dem Eingangsordner und klicke auf **Verarbeiten**.

Die Tabelle listet alle Lieferungen mit Quelldatei, BA-Auftrag, Status und Erstelldatum. Über **Öffnen** kommst du zur Prüfung.

### Prüfen und erzeugen

In der Prüfansicht (`/atr/deliveries/:id`) bearbeitest du die **Kopffelder** (ATR-Nummer, Containernummer, Set-Titel, PO-Nummer, Wiege- und Prüfdatum, QA-Unterzeichner, max. garantiertes Gewicht) und speicherst sie. Darunter stehen die **Positionen**: Zeilen ohne Katalogtreffer sind rot hinterlegt. Gewicht und PO-Pos je Position kannst du direkt eintragen (wird beim Verlassen des Feldes gespeichert).

Mit **Erzeugen** werden die Ausgabedateien gebaut. Warnungen erscheinen als Hinweis. Danach stehen die Downloads bereit: **ATR (XLSX)**, **ATR (PDF)** und **Containerbeschriftung (DOCX)**.

## Vorlage

Unter **ATR → Vorlage** (`/atr/template`) pflegst du die festen Kopfdaten, die in jedes ATR einfließen (Kunde, AC-Programm, Arbeitspaket, Spezifikationen, Lieferant, NSCM-Code, ATA-Kapitel, Wiegeausstattung usw.) sowie den **Standard-QA-Unterzeichner**, der neuen Lieferungen automatisch vorbelegt wird. Zusätzlich lädst du hier die **Struktur-Datei** (`.xlsx`) hoch, die als Layout-Vorlage dient.

## Einstellungen (Fileserver)

Unter **Einstellungen → ATR** (`/settings/atr`) hinterlegst du den SMB-Fileserver: Host, Freigabe, Domäne, Benutzer und Passwort sowie die Pfade für **Eingang**, **Ausgabe** und **Archiv**. Über **Verbindung testen** prüfst du die Zugangsdaten. Das **Scan-Intervall** und der **Automatikmodus** steuern die automatische Verarbeitung. Ist der Fileserver konfiguriert, erscheint bei den Lieferungen die Option „Aus Ordner", und die erzeugten Dateien werden in den Ausgabepfad abgelegt.
