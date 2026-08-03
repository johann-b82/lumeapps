# Projektstatus — LumeApps

_Stand: 2026-08-03 · Prod-DB: `v1_101` (79 Migrationen) · 28 Router-Module_

> Momentaufnahme des Umsetzungsstands. Kernprodukt läuft produktiv; der aktuelle
> Schwerpunkt ist der HR-Ausbau (Onboarding / Qualifizierung / Schulungen).

**Deploy-Hinweis:** Prod läuft seit 2026-07-27 auf dem Feature-Branch
`fix/kompetenz-neue-kategorie` — aktuell **28 Commits vor `origin/main`** (0 dahinter).
Die gesamte jüngere HR-Arbeit ist live, aber noch **nicht nach `main` gemergt**
(siehe Offene Punkte).

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
| **HR – Schulungen** (Katalog, Zuweisen, Stand, Einarbeitung) | ✅ Live | aktueller Schwerpunkt — siehe unten |

## HR-Schulungen — jüngster Ausbau

- 3-Tab-Struktur: **Bearbeiten / Zuweisen / Stand der Mitarbeiter**
- Entdoppelter Schulungskatalog (jede Schulung nur einmal)
- Beschreibung + Unterlagen je Schulung; Turnus & Frist je Name geteilt
- Verantwortlicher/Ansprechpartner je Name überall gleich (Bereiche + Einarbeitung)
- „Durchgeführt eintragen" (per Person + Sammel-Termin) — Stand aktualisiert sofort
- Nicht-Personio-Mitarbeiter (Externe) voll integriert
- Stand-Liste aus **einer** Quelle (ganze aktive Belegschaft, nicht nur mit Schulung)
- **Personio-Sync repariert** (war ~4 Wochen still kaputt, siehe Offene Punkte)
- **Standort-Filter wie im Organigramm** (Zuweisen + Stand)

## Offene Punkte / technische Schuld

- 🔴 **PR #38 mergen & Prod zurück auf `main`** — 28 Commits ungemergt; wichtigster
  Aufräumpunkt. Merge erfolgt durch den Eigentümer.
- 🟡 **Personio-Attendances auf API V2** — V1 ist für mehrtägige Anwesenheitsperioden
  abgekündigt (422); Sync läuft seitdem „partial", die **Überstunden-KPI** bleibt
  veraltet, bis der Abruf auf V2 migriert ist.
- 🟡 **HR-Datenpflege auf Prod** — Onboarding-/Schulungs-Matrizen + Logo befüllen,
  sonst bleibt die Automatik inert.
- 🟡 **HR-Automatisierung Phase 2–4** — extern blockiert (Personio-Schreibzugriff,
  Identity, Azure).
- 🟡 **Audit: Vier-Augen-Prinzip + Klarnamen** — bewusst offen (braucht echte
  Rollen + Ersatz der Platzhalter-E-Mail in der Auth).
- ⚪ **CI auf `main` dauerrot** — Altlast (Paperless-Container), kein Code-Blocker.

## Kurzfassung

Das Produkt ist produktiv und wird täglich genutzt; die Kern-Features stehen. Der
aktuelle Schwerpunkt HR-Onboarding/-Qualifizierung ist funktional weitgehend fertig.
Was noch fehlt, ist überwiegend **Datenpflege, externe Freigaben (Azure /
Personio-Schreibzugriff) und das Zusammenführen des Feature-Branches nach `main`** —
keine neue Kernentwicklung.
