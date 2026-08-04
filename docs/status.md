# Projektstatus — LumeApps

_Stand: 2026-08-04 · Prod-DB: `v1_102` (80 Migrationen) · 28 Router-Module_

> Momentaufnahme des Umsetzungsstands. Kernprodukt läuft produktiv; der aktuelle
> Schwerpunkt ist der HR-Ausbau (Onboarding / Qualifizierung / Schulungen).

**Deploy-Hinweis:** Prod steht wieder sauber auf **`main`** — die gesamte
Session-Arbeit (PRs #36–#41) ist gemergt, **keine offenen PRs**, Prod-Checkout
konsolidiert (`git checkout main`, `api` neu gestartet).

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
| **HR – Personio-Rückschreiben** (Nachweis-PDF ins Personio-Profil) | 🟡 Gebaut | **inert** (Default aus); scharf erst mit Personio-Schreib-Scopes + Kategorie |

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
  Standort-Filter. **Per Zellklick korrigierbar** (Datum ändern · auf „offen"
  zurücksetzen · ganz entfernen) — für falsch bestätigte Schulungen.

**Datenanbindung**
- **Personio-Sync repariert** (V1-Attendances-422 hatte den Sync ~4 Wochen still
  lahmgelegt) und auf **täglich zu fester Uhrzeit** (02:00 UTC, restart-resistent)
  umgestellt.
- **Personio-Rückschreiben** (v1_102): nach jedem Schulungs-/Kompetenz-Update wird
  ein Nachweis-PDF in die Personio-Dokumente des Mitarbeiters hochgeladen — **inert**
  bis Freischaltung, inkl. Test-Upload-Button + Checkliste
  (`docs/modules/personio-writeback.md`).

## Offene Punkte / technische Schuld

- 🟡 **Personio-Rückschreiben scharfschalten** — braucht **Schreib-Scopes für
  Dokumente** in der Personio-App (aktuelle Credentials read-only → Test liefert
  `403`) + eine Dokumentenkategorie. Dann Test-Upload grün → Schalter an.
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
Schwerpunkt HR-Onboarding/-Qualifizierung ist funktional **fertig** — Onboarding,
Kompetenzen, Einarbeitung und Schulungen (Katalog inkl. Anlegen/Löschen, Zuweisen,
Stand, Bericht-Upload, korrigierbare Gesamtübersicht) stehen und sind auf `main`
konsolidiert. Was bleibt, ist **kein offener Deploy-Rest**, sondern **externe
Freigaben** (Personio-Schreibrechte fürs Rückschreiben, Attendances V2, Azure) und
**Datenpflege** (Matrizen + Logo) — keine große Kernentwicklung.
