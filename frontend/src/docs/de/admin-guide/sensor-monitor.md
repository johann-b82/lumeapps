# Sensor Monitor

## Überblick

Der Sensor Monitor fragt Umgebungs-SNMP-Sensoren (Temperatur + Luftfeuchtigkeit) aus dem gemeinsamen Docker-Netzwerk ab, speichert die Messwerte in PostgreSQL und zeigt sie im admin-exklusiven `/sensors`-Dashboard an. Die Einrichtung erfolgt vollständig über die UI -- du brauchst keinen YAML- oder SQL-Zugriff.

Die gesamte Sensor-Konfiguration findest du unter **Einstellungen → Sensoren** — wähle **Sensoren** aus dem Abschnitts-Dropdown oben auf der Einstellungs-Seite. Sensoren ist eine vollwertige eigene Seite, kein Overlay. Nur Administratoren sehen diese Seite.

## Voraussetzungen

1. Der `api`-Container muss den Sensor-Host über SNMP/UDP 161 erreichen können. Prüfe das mit:

   ```bash
   docker compose exec api snmpget -v2c -c public 192.9.201.27 1.3.6.1.4.1.21796.4.9.3.1.5.2
   ```

   Eine numerische Antwort heißt: alles gut. Ein Timeout heißt: die Docker-Bridge kann das Sensor-Subnetz nicht erreichen -- siehe [Fehlerbehebung → Host-Modus-Fallback](#host-mode-fallback) weiter unten.
2. Admin-Rolle im KPI-Dashboard. Viewer-Konten können die Sensoren-Einstellungs-Seite nicht öffnen.
3. Der Sensor-Host muss eingeschaltet sein und auf SNMPv2c über UDP 161 antworten. SNMPv3 mit Auth/Priv wird in diesem Release nicht unterstützt.

> **Hinweis:** Der Smoke-Test nutzt bewusst `snmpget` aus dem `api`-Container heraus -- Erreichbarkeit von deinem Laptop oder dem Docker-Host reicht nicht. Der Scheduler läuft im Container, also muss dort das Routing funktionieren.

## Einen Sensor einrichten

Öffne **Einstellungen → Sensoren** — wähle **Sensoren** aus dem Abschnitts-Dropdown oben auf der Einstellungs-Seite.

### Schritt 1: OIDs mit SNMP-Walk finden

1. Klappe **SNMP-Walk (OID-Finder)** auf.
2. Trage Sensor-Host, Port (Standard 161), Community-String und eine Basis-OID ein (für Kirchhoff-Sensoren starte mit `.1.3.6.1.4.1.21796.4.9.3.1`).
3. Klicke **Walk starten**. Die Ergebnisse erscheinen in einer scrollbaren Tabelle mit OID, Typ, Wert.
4. Identifiziere die Temperatur- und Luftfeuchte-OIDs (typischerweise enden sie bei Kirchhoff auf `.5.1` und `.6.1`).

### Schritt 2: Sensor-Zeile hinzufügen

1. Klicke **+ Sensor hinzufügen**.
2. Fülle Name, Host, Port, Community und die Skalierungsfaktoren aus (1.0 für Rohwerte; 10.0 falls der Sensor Ganzzahl-Dezi-°C liefert).
3. Klicke im Walk-Ergebnis auf **Zuweisen** bei der Temperatur-OID → wähle die neue Zeile → **Temp-OID**. Wiederhole das für die Luftfeuchte.

| Feld               | Pflicht | Hinweise                                                                 |
|--------------------|---------|--------------------------------------------------------------------------|
| Name               | Ja      | Eindeutig über alle Sensoren hinweg                                      |
| Host               | Ja      | IP oder DNS-Name, erreichbar aus dem `api`-Container                     |
| Port               | Ja      | Standard 161                                                             |
| Community          | Nein    | Schreibgeschütztes Secret, verschlüsselt gespeichert. Optional — leer lassen, wenn das Gerät SNMPv2c ohne Authentifizierung akzeptiert. |
| Temperatur-OID     | Nein    | Leer lassen, um Temperatur für diesen Sensor zu überspringen             |
| Temperatur-Skalierung | Ja   | Positive Zahl; typisch 1.0 oder 10.0                                     |
| Luftfeuchte-OID    | Nein    | Leer lassen, um Luftfeuchte für diesen Sensor zu überspringen            |
| Luftfeuchte-Skalierung | Ja  | Positive Zahl; typisch 1.0 oder 10.0                                     |
| Diagrammfarbe      | Nein    | Hex-Farbe (`#RRGGBB`) für die Linie dieses Sensors im Sensoren-Dashboard. Leer = nächste Farbe aus der Standard-Palette. |
| Aktiviert          | Ja      | Deaktivieren stoppt die Abfrage, ohne die Zeile zu löschen               |

### Schritt 3: Prüfen

1. Klicke **Probe** in der Sensor-Zeile. Bei Erfolg erscheinen Temperatur + Luftfeuchte direkt in der Zeile.
2. Schlägt die Prüfung fehl: prüfe Host-Erreichbarkeit, Community und OID-Gültigkeit.

### Schritt 4: Speichern

Klicke **Speichern**. Der Sensor wird persistiert; der Scheduler übernimmt ihn beim nächsten Tick. Wechsle zu `/sensors`, um zu bestätigen, dass die neue Karte mit Live-Messwerten erscheint.

## Schwellenwerte

Globale Schwellenwerte gelten für alle Sensoren. Setze sie in der Karte **Globale Schwellenwerte**:

- Temperatur min / max (°C)
- Luftfeuchte min / max (%)

Fällt ein Messwert außerhalb des Bereichs, zeigt die KPI-Karte den Wert in Destructive-Rot mit der Bildunterschrift "Außerhalb des Bereichs". Diagramme zeichnen gestrichelte Referenzlinien an jedem Schwellenwert.

> **Bekannte Einschränkung:** Ein leeres Schwellen-Feld bedeutet "nicht ändern". Um einen bereits gesetzten Schwellwert zu entfernen, wende dich an den Operator, oder warte auf ein zukünftiges Release mit einer expliziten Reset-Aktion.

Pro-Sensor-Überschreibungen der Schwellenwerte werden in diesem Release nicht unterstützt.

## Abfrage-Intervall

Die Karte **Abfrage-Kadenz** setzt ein einzelnes Intervall (5–86400 Sekunden) für alle aktivierten Sensoren. Speichern löst einen Live-Reschedule aus -- kein API-Neustart nötig.

Empfehlungen:

- 60 s (Standard): typisches produktives Umgebungs-Monitoring
- 30 s: für enges Schwellen-Alerting (geplantes zukünftiges Feature)
- 300+ s: für niederfrequentes Baseline-Monitoring

| Intervall | Abfragen pro Tag & Sensor | Typischer Einsatz                  |
|-----------|---------------------------|------------------------------------|
| 30 s      | 2 880                     | Enges Monitoring / Alerting-Vorbereitung |
| 60 s      | 1 440                     | Standard-Produktion                |
| 300 s     | 288                       | Baseline-Monitoring                |
| 3 600 s   | 24                        | Nur stündliche Zusammenfassungen   |

## Fehlerbehebung

### Sensor zeigt "Offline"

Der Health-Chip auf `/sensors` zeigt **Offline seit Xm**, wenn drei aufeinanderfolgende Abfragen fehlschlagen. Wahrscheinliche Ursachen:

1. **Docker-zu-Sensor-Erreichbarkeit unterbrochen** -- führe den Smoke-Test aus den Voraussetzungen aus.
2. **Community-String passt nicht** -- der Sensor hat Credentials rotiert. Bearbeite die Zeile, trage die neue Community ein (leer lassen, um die bestehende zu behalten), speichere.
3. **OID-Drift** -- die Sensor-Firmware hat das OID-Mapping geändert. Führe SNMP-Walk erneut aus, um sie neu zu finden.

### <a id="host-mode-fallback"></a>Host-Modus-Fallback

Läuft `docker compose exec api snmpget ...` in einen Timeout, derselbe Befehl auf dem Host-Rechner funktioniert aber: dann kann die Docker-Bridge das Sensor-Subnetz nicht erreichen. Zwei Fallback-Optionen:

**Option A -- `network_mode: host` auf dem `api`-Service (einfacher, invasiver):**

```yaml
services:
  api:
    network_mode: host
    # NOTE: incompatible with `ports:` + breaks internal Docker DNS (api → db).
    # All internal service references must switch to `localhost:<port>`.
    # Also requires removing the `networks:` stanza for this service.
```

Trade-offs:

- Bricht Service-Discovery per Name -- ändere `DATABASE_URL` von `db:5432` auf `localhost:5432` und passe jede interne Referenz an.
- Legt die API direkt auf dem Host-Interface offen (umgeht Dockers Netzwerk-Isolation).
- `ports:`-Deklarationen auf `api` werden ungültig und müssen entfernt werden.

**Option B -- `macvlan`-Netzwerk (weniger invasiv, mehr Konfiguration):**

```yaml
networks:
  sensor_lan:
    driver: macvlan
    driver_opts:
      parent: eth0
    ipam:
      config:
        - subnet: 192.9.201.0/24
          gateway: 192.9.201.1
          ip_range: 192.9.201.240/28

services:
  api:
    networks:
      default:
      sensor_lan:
        ipv4_address: 192.9.201.241
```

Hänge den `api`-Service an ein macvlan-Netz, das die L2-Domäne des Hosts mit dem Sensor-Subnetz teilt. Das bewahrt Docker-DNS und Service-Isolation, erfordert aber einen dedizierten Subnetz-Bereich und IP-Reservierung außerhalb des DHCP-Pools. Nur empfohlen, wenn die Trade-offs von Option A nicht akzeptabel sind.

**Bevorzugte Reihenfolge:** erst auf der Standard-Bridge bleiben → Option B (macvlan) → Option A (Host-Modus) nur als letzter Ausweg.

### Abfrage läuft, aber keine Messwerte

Prüfe die Logs:

```bash
docker compose logs api --tail=100 | grep -i sensor
```

Suche nach `PollResult`-Einträgen. Leere Ergebnisse ohne Fehler bedeuten meist, dass die OID `noSuchObject` zurückgegeben hat -- führe SNMP-Walk erneut aus.

### Scheduler übernimmt die neue Kadenz nicht

Die Eingabe für das Abfrage-Intervall löst beim Speichern einen In-Prozess-Reschedule aus. Bleibt das alte Intervall aktiv:

1. Lade die Sensoren-Einstellungs-Seite neu und bestätige, dass der Wert gespeichert wurde.
2. Ist der Wert korrekt, das Verhalten aber nicht: starte den `api`-Container neu: `docker compose restart api`.

## Sicherheit

> **Community ist optional.** Manche SNMP-Geräte (z. B. einige Hutermann-Modelle) akzeptieren Anfragen ohne Community-String — lass das Feld dann leer. Wenn dein Gerät einen Community-String erwartet, **verwende in Produktion niemals den Default `public`**: ändere ihn am Gerät auf ein deployment-spezifisches Secret, bevor du den Monitor exponierst.

> **Community-Strings werden verschlüsselt gespeichert** mit dem Fernet-Key der Anwendung (derselbe Key wie für Personio-Credentials). Sie werden niemals in API-Antworten entschlüsselt und niemals geloggt. Das Admin-Formular behandelt Community als schreibgeschützt: leer lassen beim Bearbeiten behält den gespeicherten Wert, ein neuer String überschreibt ihn.

Weitere Hinweise:

- Rotiere Community-Strings am Sensor-Gerät, wenn ein Admin das Team verlässt; aktualisiere danach die Zeile auf der Sensoren-Einstellungs-Seite (leer = behalten).
- Beschränke SNMP auf dem Sensor-Host auf die Quell-IP des Docker-Hosts, falls die Geräte-Firmware das erlaubt.
- Halte das Sensor-Subnetz aus dem öffentlichen Internet heraus.

## Verwandte Artikel

- [Systemeinrichtung](/docs/admin-guide/system-setup) -- Docker-Compose-Überblick
- [Architektur](/docs/admin-guide/architecture) -- wie der Scheduler integriert ist
- [Personio-Integration](/docs/admin-guide/personio) -- verwandte Admin-Integration
