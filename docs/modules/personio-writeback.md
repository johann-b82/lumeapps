# Personio-Rückschreiben (Schulungs-/Kompetenznachweise)

Nach jedem Schulungs- oder Kompetenz-Update wird ein Nachweis-PDF in die
**Personio-Dokumente** des Mitarbeiters hochgeladen. **Standardmäßig inaktiv**
(No-Op), bis alle Voraussetzungen erfüllt sind.

## Wie es funktioniert

1. **Auslöser:** Nach dem lokalen Speichern startet ein Hintergrund-Task
   (`asyncio.create_task`, blockiert die Antwort nicht):
   - Schulung durchgeführt (einzeln / Sammel / Bericht-Upload) → `nach_schulung_update`
   - Kompetenz-Zelle gesetzt → `nach_kompetenz_update`
2. **Gate:** läuft nur weiter, wenn Schalter an **und** Kategorie gesetzt **und**
   Credentials vorhanden. Sonst No-Op. Externe (negative ID) werden übersprungen.
3. **Push:** PDF erzeugen → `POST /auth` (Token) → `POST /company/documents`
   (multipart: `employee_id`, `document_category_id`, `title`, `file`).
4. **Fehler** werden nur geloggt, nie geworfen — das lokale Update bleibt unberührt.

Code: `backend/app/services/personio_writeback.py`, Hooks in `routers/schulungen.py`
+ `routers/kompetenzen.py`, Config in `app_settings` (Migration v1_102).

## Aktivierungs-Checkliste

- [ ] **Personio-App: Schreib-Scopes für Dokumente** freischalten (Dokumente
      lesen + schreiben). Die bisherigen Credentials sind nur `*:read` — ohne
      Schreibrecht → `403`.
- [ ] **Dokumentenkategorie** in Personio anlegen (z. B. „Schulungsnachweise") und
      deren **ID** notieren.
- [ ] In *Einstellungen → Personio*: die **Kategorie-ID** eintragen und **speichern**.
- [ ] **Test-Upload** (Admin-Button in derselben Karte): einen Mitarbeiter + Art
      wählen → *Test-Upload*. Umgeht den Schalter und meldet das echte Ergebnis:
  - `Erfolgreich` → Dokument liegt im Personio-Profil des Mitarbeiters.
  - `Fehlgeschlagen (personio)` mit HTTP-Status → typische Fälle:
    - `403` = Schreib-Scope fehlt noch.
    - `404`/`422` = Kategorie-ID falsch oder Feldname anzupassen.
- [ ] Erst wenn der Test **grün** ist: den **Schalter aktivieren** und speichern.
- [ ] Optional: Feldnamen/Endpoint in `_push()` gegen die reale Personio-API
      final bestätigen (aus der Doku übernommen, nie live getestet).

## Grenzen

- Der PDF-Inhalt ist bewusst schlicht (Liste der Schulungen bzw. Qualifikationen);
  Layout/Logo sind Feinschliff für später.
- Custom-Attribute (statt Dokument) wurden bewusst nicht gewählt (single-value,
  keine Historie). Bei Bedarf nachrüstbar (`personio:persons:write`).
