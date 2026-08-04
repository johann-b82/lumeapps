# Projektstatus — LumeApps

_Stand: 2026-08-04 · Prod-DB: `v1_101` (79 Migrationen) · 28 Router-Module_

> Momentaufnahme des Umsetzungsstands. Kernprodukt läuft produktiv; der aktuelle
> Schwerpunkt ist der HR-Ausbau (Onboarding / Qualifizierung / Schulungen).

**Deploy-Hinweis:** Prod läuft über den Deploy-via-Feature-Branch-Workflow
(einzelner Prod-Checkout) aktuell auf **`feat/schulungsbericht-upload`** —
**10 Commits vor `origin/main`**. Der frühere Kompetenz-Branch (PR #38) ist
inzwischen nach `main` gemergt; die seither dazugekommene Arbeit ist live, aber
noch **nicht nach `main` gemergt** (vier offene PRs, siehe Offene Punkte).

Legende: ✅ live · 🟡 gebaut, aber nicht scharf (Daten/Freigabe fehlt) · 🔴 offen/blockiert · ⚪ Rauschen

## Module

| Bereich | Stand | Anmerkung |
|---|---|---|
| **Kernplattform** (Docker/Caddy, Postgres, Directus-Auth, Upload→Parsing, RBAC) | ✅ Live | Directus = Shape / FastAPI = Compute; same-origin, keine CORS |
| **KPI-Dashboards** (Sales, HR, Quality, Finance, Procurement, Production) | ✅ Live | unter der KPI-Dashboard-Kachel gruppiert |
| **Signage** (Kiosk-Player, Pairing, Offline-Service-Worker) | ✅ Live | Offline-Fix deployt; Player wird gebaut via FastAPI ausgeliefert |
| **ATR** (Teilekatalog, PDF via LibreOffice/UNO) | 🟡 Gebaut | Katalog-Daten teils leer; Logo/Daten-Phase offen |
| **Produktion – Wartung** (Maschinen-Wartung, PDF) | ✅ Live | Phase 1 (DB v1_82) |
| **Produktion – Verzug-KPI** | ✅ Live | Serien-Filter (Pos-Typ-2) default aus — echter Fachcode fehlt |
| **Qualität – Audit** (Planung, Phasen-Checkliste, append-only Trail) | ✅ Live | Vier-Augen-Prinzip + Klarnamen bewusst offen |
| **Qualität – Inspektion** | ✅ Live | — |
| **E-Mail-Modul** (Office365/Graph, shared) | 🟡 Gebaut | inert bis Azure-App-Registration |
| **HR – Organigramm** (aus Personio) | ✅ Live | Standort-Filterchips (Vorlage für Schulungen) |
| **HR – Onboarding** | ✅ Live | inkl. Externe; „neu"-Markierung an Paket-Download gekoppelt |
| **HR – Kompetenzen** | ✅ Live | Matrizen synchron; Kategorien pflegbar |
| **HR – Einarbeitung** (Katalog + Abteilungs-Matrix) | ✅ Live | Ansprechpartner je Name mit Schulungen geteilt |
| **HR – Schulungen** (Katalog, Zuweisen, Stand, Bericht-Upload, Gesamtübersicht) | ✅ Live | aktueller Schwerpunkt — siehe unten |

## HR-Schulungen — jüngster Ausbau

Drei Tabs: **Bearbeiten / Zuweisen / Stand der Mitarbeiter**.

**Katalog (Bearbeiten)**
- Entdoppelter Katalog (jede Schulung nur einmal); Beschreibung + Unterlagen je
  Schulung; Turnus, Frist, Verantwortlicher je Name überall geteilt.
- **Schulungen manuell anlegen und entfernen** (Löschen mit Bestätigung; warnt bei
  betroffenen Nachweisen).

**Zuweisen**
- Einzelzuweisung + Anforderungsmatrix (Pflicht je Abteilung); Verantwortlicher
  auch für Externe frei eintragbar.
- **Standort-Filter** (Hamburg/Memmingen …, wie im Organigramm).

**Stand der Mitarbeiter**
- Stand-Liste aus **einer** Quelle (ganze aktive Belegschaft + Externe), Standort-Filter.
- „Durchgeführt eintragen" (per Person + Sammel-Termin) — Stand aktualisiert sofort.
- **Schulungsbericht-PDF-Upload** (Formblatt 68 Schulungsnachweis + Formblatt 71
  Schulungsübersicht): Text via `pdftotext`, **editierbare Vorschau** (Mitarbeiter-
  Dropdown, Schulung Dropdown+Text, Datum, Zeilen löschen) → schreibt Durchführungs-
  daten fort; fehlende Schulungen werden angelegt.
- **Gesamtübersicht (Matrix)** — alle Mitarbeiter × Schulungen; **verbindet Zuweisen
  und Absolvierung**: ✓ aktuell · ! bald fällig · X überfällig · ☐ offen (zugewiesen).
  Standort-Filter.

**Datenanbindung**
- **Personio-Sync repariert** (V1-Attendances-422 hatte den Sync ~4 Wochen still
  lahmgelegt) und auf **täglich zu fester Uhrzeit** (02:00 UTC, restart-resistent)
  umgestellt.

## Offene Punkte / technische Schuld

- 🔴 **Vier offene PRs mergen & Prod zurück auf `main`** — wichtigster Aufräumpunkt.
  Empfohlene Reihenfolge: **#36** (conftest-Riegel), **#37** (HR-Status-Doku),
  **#39** (täglicher Sync), **#40** (Stand-Tab: Bericht-Upload + Matrix + Katalog-
  Pflege). Danach Prod-Checkout zurück auf `main`. Merge erfolgt durch den
  Eigentümer (Classifier blockt den Assistenten).
- 🟡 **Personio-Attendances auf API V2** — V1 ist für mehrtägige Anwesenheitsperioden
  abgekündigt (422); Sync läuft seitdem „partial", die **Überstunden-KPI** bleibt
  veraltet, bis der Abruf auf V2 migriert ist. (HR-Org-Daten sind nicht betroffen.)
- 🟡 **HR-Datenpflege auf Prod** — Anforderungs-/Onboarding-Matrizen + Logo befüllen,
  sonst bleibt die Automatik inert.
- 🟡 **HR-Automatisierung Phase 2–4** — extern blockiert (Personio-Schreibzugriff,
  Identity, Azure).
- 🟡 **Audit: Vier-Augen-Prinzip + Klarnamen** — bewusst offen (braucht echte
  Rollen + Ersatz der Platzhalter-E-Mail in der Auth).
- ⚪ **CI auf `main` dauerrot** — Altlast (Paperless-Container), kein Code-Blocker.

## Kurzfassung

Das Produkt ist produktiv und wird täglich genutzt; die Kern-Features stehen. Der
Schwerpunkt HR-Onboarding/-Qualifizierung ist funktional weitgehend fertig —
Onboarding, Kompetenzen, Einarbeitung und Schulungen (Katalog inkl. Anlegen/Löschen,
Zuweisen, Stand, Bericht-Upload, Gesamtübersicht mit Zuweisen-Verbindung) stehen.
Was bleibt, ist überwiegend **Zusammenführen der Branches nach `main`, Datenpflege
und externe Freigaben (Azure / Personio-Schreibzugriff)** — keine große
Kernentwicklung.
