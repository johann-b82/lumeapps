# Digital Signage

## Überblick

Digital Signage verwandelt jeden Raspberry Pi mit HDMI-Display in einen verwalteten Kiosk, der eine Schleife aus Medieninhalten abspielt — Bilder, Videos, PDFs, konvertierte PPTX-Präsentationen, Live-URLs oder HTML-Snippets. Das KPI-Dashboard ist die Steuerungszentrale: du lädst Medien hoch, baust Playlists und weist diese über Tags den Geräten zu. Auf jedem Pi läuft ein leichtgewichtiger Sidecar, der die zuletzt bekannte Playlist und alle Mediendateien lokal zwischenspeichert — so läuft die Wiedergabe auch bei WLAN-Ausfällen unterbrechungsfrei weiter.

**Unterstützte Medienformate:**

| Format | Details |
|--------|---------|
| Bild | JPEG, PNG, GIF, WEBP |
| Video | MP4, WEBM |
| PDF | Wird als Foliensequenz gerendert |
| PPTX | Server-seitige Konvertierung in Folienbilder — siehe [PPTX Best Practices](#pptx-best-practices) |
| URL | Live-Webseite im Vollbild |
| HTML | HTML-Snippet, vollbildschirmfüllend gerendert |

## Voraussetzungen

- **Admin-Rolle** im KPI-Dashboard. Viewer haben keinen Zugriff auf die Signage-Verwaltungsseiten.
- **Raspberry Pi 4 oder Pi 5** empfohlen (Pi 3B wird mit Einschränkungen unterstützt — siehe [Operator-Runbook](../../../../../../../docs/operator-runbook.md)).
- **≥ 16 GB microSD-Karte**, ≥ 1 GB RAM.
- **HDMI-Display**, angeschlossen am Pi.
- **Netzwerkzugang** vom Pi zum KPI-Dashboard-API-Host. Eine Internetverbindung wird nur beim initialen Provisioning benötigt (um das Repo zu klonen und Pakete zu installieren).
- Die KPI-Dashboard-API muss vom Pi aus erreichbar sein: `curl http://<api-host>/api/health` sollte `{"status":"ok"}` zurückgeben.

## Einen Pi einrichten

### Schritt 1: Raspberry Pi OS Bookworm Lite 64-bit flashen

1. Lade den **Raspberry Pi Imager** von [raspberrypi.com/software](https://www.raspberrypi.com/software/) herunter.
2. Wähle **Raspberry Pi OS Lite (64-bit)** — Bookworm-Release.
3. Öffne **OS-Anpassung** (Zahnrad-Symbol) vor dem Schreiben:
   - Lege einen Hostnamen fest (z. B. `signage-lobby`).
   - Aktiviere SSH und vergib Zugangsdaten.
   - Trage WLAN-SSID und -Passwort ein.
4. Schreibe das Image auf die microSD-Karte und stecke sie in den Pi.
5. Schalte den Pi ein und warte auf den Boot (erster Start dauert 1–2 Minuten).
6. Prüfe, ob der Pi erreichbar ist: `ssh <user>@<pi-hostname>`.

### Schritt 2: Provision-Skript ausführen

Melde dich per SSH am Pi an und führe folgendes aus:

```bash
# Repo klonen
sudo git clone https://github.com/<org>/kpi-dashboard /opt/signage

# Provisioning (ersetze mit deinem API-Host)
sudo SIGNAGE_API_URL=<api-host:port> /opt/signage/scripts/provision-pi.sh
```

Das Skript installiert alle benötigten Pakete, legt den `signage`-Benutzer an, richtet den Offline-Cache-Sidecar ein und aktiviert den Kiosk-Dienst. Bei Erfolg endet es mit Exit-Code 0.

Nach Abschluss des Skripts **Pi neu starten**:

```bash
sudo reboot
```

Die vollständige Skript-Dokumentation mit Exit-Codes und Idempotenz-Garantien findest du in `scripts/README-pi.md` im Repo.

> **Tipp:** Das Provision-Skript ist idempotent. Du kannst es nach einer Konfigurationsänderung (z. B. neuer API-Host) bedenkenlos erneut ausführen — es aktualisiert die laufenden Dienste.

### Schritt 3: Gerät beanspruchen

Nach dem Neustart zeigt der Kiosk innerhalb von 30 Sekunden einen **6-stelligen Pairing-Code** auf dem Bildschirm an.

1. Öffne im KPI-Dashboard **Signage → Gerät koppeln** (oder `/signage/pair`).
2. Gib den 6-stelligen Code ein.
3. Vergib einen Gerätenamen (z. B. „Lobby-Bildschirm").
4. Weise dem Gerät einen oder mehrere **Tags** zu (z. B. `lobby`, `etage-1`).
5. Klicke auf **Beanspruchen**.

Der Kiosk beginnt innerhalb weniger Sekunden mit der Wiedergabe.

### Schritt 4: Playlist über Tags zuweisen

Playlists werden Geräten über **Tags** zugeordnet. Eine Playlist läuft auf einem Gerät, wenn mindestens ein Tag des Geräts mit einem Tag der Playlist übereinstimmt.

1. Erstelle oder bearbeite eine Playlist unter **Signage → Playlists**.
2. Füge Ziel-Tags zur Playlist hinzu (z. B. `lobby`).
3. Jedes beanspruchte Gerät mit einem passenden Tag nimmt die Playlist sofort an.

## Medien hochladen

Öffne **Signage → Medien**, um Medien-Assets zu verwalten.

### Bilder und Videos hochladen

Ziehe Dateien per Drag-and-drop in den Upload-Bereich oder klicke auf **Datei hochladen**. Unterstützte Formate: JPEG, PNG, GIF, WEBP (Bilder), MP4, WEBM (Videos).

Dateien werden auf dem Server gespeichert. Nach dem Upload steht das Asset in jeder Playlist zur Verfügung.

### URL registrieren

Klicke auf **URL registrieren** und füge eine Webadresse ein (z. B. `https://www.example.com/status`). Der Kiosk lädt die URL vollbildschirmfüllend. Die Seite muss vom Pi-Netzwerk aus erreichbar sein.

### HTML registrieren

Klicke auf **HTML registrieren** und füge ein HTML-Snippet ein. Nützlich für benutzerdefinierte Statusseiten oder gestaltete Texteinblendungen.

### PPTX-Präsentation hochladen

1. Klicke auf **Datei hochladen** und wähle eine `.pptx`-Datei aus.
2. Der Server konvertiert die Präsentation in eine Folienbildsequenz. Beobachte den **Konvertierungsstatus**:
   - **Ausstehend** — in der Warteschlange, wartet auf einen Konvertierungs-Slot.
   - **In Bearbeitung** — Konvertierung läuft.
   - **Fertig** — Folien sind bereit; das Asset kann zu Playlists hinzugefügt werden.
   - **Fehlgeschlagen** — Konvertierungsfehler. Lade die Datei herunter und prüfe, ob sie sich fehlerfrei in PowerPoint oder LibreOffice Impress öffnen lässt.
3. Nach Abschluss steht das Asset als Folienbildsequenz im Playlist-Builder zur Verfügung.

Tipps zur Vorbereitung von Präsentationen findest du unter [PPTX Best Practices](#pptx-best-practices).

## Playlists erstellen

Öffne **Signage → Playlists** und klicke auf **Neue Playlist** oder öffne eine bestehende.

### Elemente hinzufügen

Klicke auf **Element hinzufügen** und wähle ein Medien-Asset aus der Bibliothek. Du kannst mehrere Elemente hintereinander hinzufügen.

### Reihenfolge ändern

Ziehe Elemente per Drag-and-drop, um sie umzusortieren. Der Kiosk spielt die Elemente in der angezeigten Reihenfolge ab.

### Einstellungen pro Element

| Einstellung | Beschreibung |
|-------------|-------------|
| Dauer | Wie lange das Element angezeigt wird (in Sekunden). Videos spielen standardmäßig in ihrer natürlichen Länge, es sei denn, du überschreibst sie. |
| Übergang | Visueller Übergang zwischen Elementen (Überblendung, Schnitt usw.). |

### Tag-Zuordnung

Weise der Playlist **Ziel-Tags** zu. Geräte mit mindestens einem passenden Tag erhalten diese Playlist. Ein Gerät spielt immer nur eine Playlist ab — bei mehreren Treffern gewinnt die Playlist mit den meisten übereinstimmenden Tags.

### Veröffentlichen

Änderungen werden innerhalb von **30 Sekunden** nach dem Speichern auf dem Kiosk wirksam (über das Polling-Intervall des Sidecars).

## Offline-Verhalten

Auf jedem Pi läuft ein lokaler **Signage-Sidecar**, der die Playlist und alle Mediendateien zwischenspeichert. Fällt die WLAN- oder Netzwerkverbindung des Pi aus:

- Der Kiosk **spielt weiter** die zuletzt bekannte Playlist in einer Schleife.
- Alle Medien werden aus dem lokalen Cache unter `/var/lib/signage/` ausgeliefert.
- Der Offline-Indikator (`Offline`-Chip) erscheint in der Kiosk-Oberfläche.
- Der Sidecar ist darauf ausgelegt, mindestens **5 Minuten** Offline-Wiedergabe ohne Einschränkungen zu bewältigen.

Wird die Verbindung wiederhergestellt:

- Der Sidecar verbindet sich innerhalb von **30 Sekunden** wieder mit dem Backend.
- Playlist-Änderungen, die während des Ausfalls vorgenommen wurden, werden automatisch übernommen.

> **Hinweis:** Mediendateien, die der Playlist nach der letzten Synchronisierung hinzugefügt wurden, stehen erst offline zur Verfügung, nachdem der Sidecar sie heruntergeladen hat. Neue Medienelemente werden im Hintergrund vorabgerufen, sobald die Verbindung wiederhergestellt ist.

## Fehlerbehebung

### WLAN-Konnektivität

Geht der Kiosk unerwartet offline, gehe so vor:

1. Melde dich per SSH am Pi an und prüfe den Netzwerkstatus:
   ```bash
   nmcli device status
   nmcli connection show --active
   ```
2. Ist das WLAN getrennt, verbinde es erneut:
   ```bash
   nmcli device connect wlan0
   ```
3. Prüfe, ob der API-Host vom Pi erreichbar ist:
   ```bash
   curl http://<api-host>/api/health
   ```
4. Prüfe den Sidecar-Health-Endpunkt:
   ```bash
   curl http://localhost:8080/health
   ```
   Erwartete Antwort bei Online-Betrieb: `{"ready": true, "online": true, "cached_items": N}`

### Pairing-Code erscheint nicht

Erscheint nach dem Neustart kein Pairing-Code auf dem Bildschirm:

1. Prüfe, ob das Provision-Skript erfolgreich abgeschlossen wurde (Exit-Code 0).
2. Sieh dir die Logs des Kiosk-Dienstes an:
   ```bash
   sudo -u signage journalctl --user -u signage-player -n 50
   ```
3. Prüfe, ob der API-Host erreichbar und der Pfad `/player/` zugänglich ist:
   ```bash
   curl http://<api-host>/player/
   ```
4. Prüfe, ob der Sidecar läuft:
   ```bash
   sudo -u signage journalctl --user -u signage-sidecar -n 20
   ```

Schritt-für-Schritt-Wiederherstellungsverfahren findest du im [Operator-Runbook](../../../../../../../docs/operator-runbook.md).

### Schwarzer Bildschirm / Kein Inhalt

Ein schwarzer Bildschirm nach dem Pairing bedeutet meistens, dass das Gerät keine passende Playlist hat:

1. Prüfe, ob dem Gerät mindestens ein Tag zugewiesen ist (unter **Signage → Geräte**).
2. Prüfe, ob eine Playlist mit einem passenden Tag existiert und aktiviert ist.
3. Prüfe den Sidecar:
   ```bash
   curl http://localhost:8080/health
   ```
   Ist `cached_items` gleich 0, wurde die Playlist noch nicht empfangen. Warte 30 Sekunden und versuche es erneut.

### PPTX-Rendering-Probleme

Zeigt ein PPTX-Asset den Status „Fehlgeschlagen" oder sehen Folien falsch aus:

- Öffne die Datei in **PowerPoint** oder **LibreOffice Impress** und prüfe, ob sie lokal korrekt gerendert wird.
- Sieh dir die Konvertierungs-Logs im Admin-Bereich an.
- Beachte die [PPTX Best Practices](#pptx-best-practices) für häufige Fallstricke.

## PPTX Best Practices

PPTX-Dateien werden auf dem Server mit LibreOffice konvertiert. Um eine zuverlässige Konvertierung sicherzustellen:

**Empfohlen:**
- **Alle Schriften einbetten**, bevor du die Datei hochlädst. In PowerPoint: Datei → Optionen → Speichern → „Schriftarten in der Datei einbetten" aktivieren. In LibreOffice: Extras → Optionen → LibreOffice Writer → Schriften → „Schriften in Dokument einbetten" aktivieren.
- Verwende Standardschriften (Calibri, Cambria, Arial, Times New Roman). Der Server hat Carlito (Calibri-kompatibel) und Caladea (Cambria-kompatibel) installiert.
- Halte Folienlayouts einfach — einfarbige Hintergründe und Standardformen werden am zuverlässigsten gerendert.
- Speichere als `.pptx` (nicht `.ppt` oder `.odp`).

**Zu vermeiden:**
- **OLE-Objekte** (eingebettete Tabellenkalkulationen, mit Excel verknüpfte Diagramme) — diese werden von LibreOffice im Server-Modus nicht gerendert.
- **Eingebettete Videos** in der PPTX — der Server extrahiert Folien als statische Bilder; eingebettete Videos gehen verloren. Lade das Video als separates Medien-Asset hoch.
- **Externe Links** (Hyperlinks, verlinkte Bilder) — der Server hat während der Konvertierung keinen Internetzugang.
- **Nicht-Standardschriften oder benutzerdefinierte Schriften**, die nicht eingebettet sind — Text fällt auf eine Ersatzschrift zurück und Layouts können verschoben werden.
- **Animationen und Übergänge** — diese werden bei der Folienbildkonvertierung ignoriert.

> **Bester Ansatz:** Konvertiere die Präsentation zuerst in PowerPoint als PDF und prüfe, ob das PDF korrekt aussieht. Wenn das PDF stimmt, erzielt die PPTX-Konvertierung auf dem Server ein ähnliches Ergebnis.

## Verwandte Artikel

- [Systemeinrichtung](/docs/admin-guide/system-setup) — Docker-Compose-Überblick
- [Architektur](/docs/admin-guide/architecture) — Systemarchitektur-Überblick
- [Operator-Runbook](/docs/operator-runbook) — Technisches Pi-Referenzhandbuch (systemd-Units, journalctl, Wiederherstellungsverfahren)

## Zeitpläne

Zeitpläne spielen bestimmte Playlists zu bestimmten Zeiten und an bestimmten Tagen. Nutze sie, wenn ein Gerät tagsüber eine andere Playlist zeigen soll als abends - zum Beispiel eine Menütafel, die von Frühstück auf Mittag wechselt. Wenn kein Zeitplan zur aktuellen Zeit passt, fällt das Gerät auf die immer aktive Tag-basierte Playlist zurück.

### Felder

| Feld | Beschreibung | Pflicht | Hinweise |
|------|--------------|---------|----------|
| Playlist | Welche Playlist dieser Zeitplan abspielt. | Ja | Wähle aus den vorhandenen Playlists. Lege bei Bedarf zuerst eine im Playlists-Tab an. |
| Tage | An welchen Wochentagen der Zeitplan aktiv ist. | Ja (>=1) | Die Schnellauswahl Wochentags, Wochenende und Täglich überschreibt die Checkboxen. |
| Startzeit | Wann der Zeitplan aktiviert (einschliesslich). | Ja | Format HH:MM. |
| Endzeit | Wann der Zeitplan deaktiviert (ausschliesslich). | Ja | Format HH:MM. Muss strikt nach der Startzeit liegen. |
| Priorität | Entscheidet bei Überschneidungen. | Nein (Standard 0) | Höherer Wert gewinnt. Bei Gleichstand gewinnt der zuletzt aktualisierte. |
| Aktiv | Ob der Zeitplan in Kraft ist. | Nein (Standard an) | Lässt sich in der Liste direkt umschalten, ohne den Editor zu öffnen. |

### Regeln

- Die Startzeit muss strikt vor der Endzeit liegen. 11:00 bis 11:00 wird abgelehnt.
- Zeiträume über Mitternacht (z.B. 22:00 bis 02:00) sind in einem einzelnen Zeitplan nicht erlaubt. Teile sie in zwei Einträge auf.
- Die interne Wochentag-Bitreihenfolge (Montag = Bit 0 ... Sonntag = Bit 6) ist ein Implementierungsdetail. Der Editor zeigt dir immer eine Mo-So-Checkbox-Reihe.

### Beispiel

1. Lege Zeitplan A an: Mo-Fr, 07:00 bis 11:00, Playlist X, Priorität 10, aktiv.
2. Lege Zeitplan B an: jeden Tag (Mo-So), 11:00 bis 14:00, Playlist Y, Priorität 5, aktiv.
3. Am Mittwoch um 08:30 spielt das Gerät Playlist X - Zeitplan A passt.
4. Am Mittwoch um 12:00 spielt das Gerät Playlist Y - Zeitplan B passt; A nicht, weil 11:00 ausschliesslich ist.
5. Am Mittwoch um 15:00 passt kein Zeitplan - das Gerät fällt auf die immer aktive Tag-basierte Playlist zurück.

### Playlist löschen, die in einem Zeitplan verwendet wird

Eine Playlist kann nicht gelöscht werden, solange ein Zeitplan darauf verweist. Der Löschversuch zeigt dir eine Fehlermeldung mit den blockierenden Zeitplänen; klicke dort auf "Zeitpläne", um direkt zum Zeitplan-Tab zu springen, wo die betroffenen Zeilen hervorgehoben sind. Entferne oder weise sie dort neu zu und versuche dann die Playlist erneut zu löschen.

## Analyse

Der Tab "Geräte" zeigt pro Zeile zwei Badges, die aus den Heartbeats der letzten 24 Stunden berechnet werden.

- **Betriebszeit 24 h** - Anteil der Ein-Minuten-Fenster der letzten 24 Stunden, in denen mindestens ein Heartbeat eingegangen ist.
- **Ausfälle 24 h** - Anzahl der Ein-Minuten-Fenster ohne Heartbeat in den letzten 24 Stunden.

### Farbskala

- Grün - Betriebszeit >= 95 %. Gerät läuft stabil.
- Gelb - Betriebszeit 80 % - 95 %. Sporadische Aussetzer; prüfe das Netzwerk des Geräts.
- Rot - Betriebszeit < 80 %. Anhaltende Störung; prüfe Stromversorgung und Netzwerk.
- Neutral (-) - Noch keine Heartbeats vorhanden (gerade eingerichtet oder nie verbunden).

### Wie es berechnet wird

Jeder erfolgreiche Heartbeat wird in einer Append-only-Tabelle protokolliert. Einmal pro Minute entfernt ein Sweeper Heartbeat-Zeilen, die älter als 25 Stunden sind. Das Betriebszeit-Badge zählt die eindeutigen Ein-Minuten-Fenster mit mindestens einem Heartbeat und teilt durch den Nenner.

Für ein frisch eingerichtetes Gerät, das z. B. erst 30 Minuten online ist, beträgt der Nenner 30 (nicht 1440), damit du vom ersten Tag an ein ehrliches Signal siehst. Bewege den Mauszeiger über das Badge, um den exakten Zähler/Nenner und die Fensterlänge zu sehen.

### Aktualisierung

Die Tabelle lädt alle 30 Sekunden neu und aktualisiert sich automatisch, wenn du zum Browser-Tab zurückkehrst.
