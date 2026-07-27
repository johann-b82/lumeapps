# HR-Onboarding- & Qualifizierungs-Automatisierung — Umsetzungsstand

**Stand:** 2026-07-27 · **Prod-DB-Head:** `v1_94_schulung_verantwortlicher` · **Sprache:** DE

Automatisiert das Onboarding und die Qualifizierungs-Nachverfolgung neuer und
bestehender Mitarbeiter auf Basis der aus Personio synchronisierten Stammdaten
(EN 9100 / EASA Part 21/145 Kontext). Grundprinzip: **Personio = Datenquelle
(read-only)**, LumeApps rechnet, pflegt die Matrizen und erzeugt die Formblätter.

---

## Kurzfassung

| Phase | Inhalt | Status |
|-------|--------|--------|
| **0 — Fundament** | Schulungskatalog, Teilnahmen, Import, Anforderungs-/Kompetenzmatrix | ✅ **fertig & live** |
| **1 — MVP** | Onboarding-Cockpit, Fälligkeiten, alle Formblätter (68/71), Einarbeitungsplan, Fristen, Verantwortliche | ✅ **fertig & live** |
| **2 — E-Mail-Automatik** | Erinnerungen/Eskalation an Vorgesetzte per Mail | ⛔ extern blockiert (Azure) |
| **3 — Rückschreiben & Cockpit** | Dokumente nach Personio, Vorgesetzten-Login & -Cockpit | ⛔ extern blockiert (Personio-Schreibzugriff, Identity-Mapping) |
| **4 — OCR / KI** | Automatische Nachweis-Erfassung aus Scans | ⛔ nicht begonnen |

**Code-seitig sind Phase 0 und 1 vollständig abgeschlossen und produktiv.** Die
Automatik läuft, ist aber bis zur **Datenpflege auf Prod** (Matrizen befüllen)
weitgehend inert — sie erzeugt erst dann sinnvolle Soll-Schulungen. Das Logo ist
bereits hochgeladen; die Matrizen füllt der Fachbereich später.

---

## Phase 0 — Fundament ✅

| Baustein | Umsetzung | Wo |
|----------|-----------|-----|
| Schulungskatalog | Bereiche betrieblich / Produktion / Verwaltung; Turnus + abgeleitete Periode | `schulung_katalog`, v1_86 |
| Teilnahmen | Stand je Person (Initial / aktuell / nächste Fälligkeit); Identität über Personalnummer **oder** Personio-ID | `schulung_teilnahme`, v1_89 |
| Excel-Import | Preview → Commit (idempotent), wie ATR-Muster | `schulung_import.py`, `/api/hr/schulungen/import/*` |
| Anforderungsmatrix | Pflicht-Schulung je Abteilung, zwei Ebenen (feine Excel-Kürzel + grobe Personio-Abteilung) | `schulung_pflicht`, v1_87 |
| Positions-Zuordnung | Personio-Position → Abteilungskürzel (Brücke für Neueintritte) | `schulung_rolle`, v1_88 |
| Kompetenz-/Qualifikationsmatrix | **editierbar**: Zelle setzen, Person/Qualifikation hinzufügen & entfernen, Personensuche | `kompetenzen.py`, v1_90 |

> Der Import-Bereich der Kompetenzmatrix wurde auf Wunsch aus der Oberfläche
> entfernt (Endpunkte bleiben bestehen, nur nicht mehr verlinkt).

---

## Phase 1 — MVP ✅

### Onboarding-Cockpit (`onboarding.py`, `OnboardingPage.tsx`)
- **Neueintritte** aus Personio gelistet, je Mitarbeiter der Soll-Schulungsplan.
- **Kürzel-Zuordnung** je Mitarbeiter als Dropdown (inkl. Zurücksetzen auf „noch nicht ausgewählt").
- **Positions-Rollen** pflegbar (GET/PUT/DELETE).
- **Breadcrumb** Apps › HR › Onboarding.

### Fälligkeits-Logik
- **Frist je Schulung** (Tage nach Eintritt/Zuweisung), pflegbar in der Oberfläche.
- Effektive Fälligkeit = Turnus-Fälligkeit falls absolviert, sonst Eintrittsdatum + Frist falls offen.
- Beispiel-Fristen für die betrieblichen Schulungen eingespielt.
- **Verantwortlicher/Trainer** je Schulung (Freitext, Externe erlaubt) — füllt das Trainer-Feld im Nachweis vor.
- Übersicht „offene / überfällige" Schulungen, dringendstes zuerst.
- **Einzelzuweisung**: bestimmte Schulung an bestimmte Person (offen, ohne Datum), rücknehmbar solange kein Nachweis existiert.

### Formblätter / PDF-Erzeugung
Alle über openpyxl → LibreOffice-headless, A4, mit **Logo aus den Einstellungen**.

| Dokument | Formblatt | Auslösung | Service |
|----------|-----------|-----------|---------|
| Schulungsübersicht | Fbl. 71 | **automatisch** bei neuem Personio-Mitarbeiter (nach Abteilung + Position) **und** manuell | `schulungsuebersicht_pdf.py` |
| Schulungsnachweis intern | Fbl. 68 | manuell je Schulung (Trainer vorbefüllt) | `schulungsprotokoll_pdf.py` |
| Einarbeitungsplan | — | manuell je Abteilung/Mitarbeiter; Ansprechpartner als Such-Dropdown, Inhalt aus Schulungskatalog | `einarbeitung_pdf.py`, v1_92 |
| Onboarding-Paket | 71 + Einarbeitung | manuell, kombiniert beide in **ein** mehrseitiges PDF | `onboarding_paket_pdf.py` |

### Automatik (bei Personio-Sync)
`hr_sync.run_sync` → `onboarding_dokumente.uebersichten_erzeugen`: neuer
Mitarbeiter ⇒ Schulungsübersicht wird erzeugt, per `plan_signatur` (SHA-256 über
die Soll-Menge) versioniert und in Directus abgelegt. Ändert sich Matrix oder
Positions-Zuordnung, weicht die Signatur ab → Neuerzeugung beim nächsten Abgleich.

---

## Deployment-Stand

- **Live** auf Prod, DB-Head `v1_94`. Migrationen v1_86–v1_94 angewandt.
- **Logo** auf Prod hochgeladen (erscheint in allen erzeugten PDFs). ✅
- **Anforderungs- und Einarbeitungsmatrix** auf Prod **noch nicht befüllt** —
  bis dahin erzeugt die Automatik leere/dünne Soll-Pläne. Befüllung durch den
  Fachbereich vorgesehen. ⏳
- Zugehöriger Test-Schutz: conftest-Riegel gegen Tests auf Nicht-Test-DB
  (PR #36) verhindert versehentliches Löschen von Prod-Daten durch pytest.

---

## Was noch offen ist (extern blockiert)

| Thema | Blocker |
|-------|---------|
| **Vorgesetzter pflegt Fristen selbst** | Es gibt nur Rollen **Admin** und **Viewer**; kein Identity-Mapping Login ↔ Personio. Aktuell ist die Fristpflege **Admin-gated** — ein Vorgesetzter kann sich nicht als solcher anmelden. |
| **Phase 2 — E-Mail-Erinnerungen/Eskalation** | E-Mail-Modul ist gebaut, aber inert bis zur **Azure-App-Registrierung** (Office365/Graph). |
| **Phase 3 — Dokumente nach Personio zurückschreiben** | Personio-API ist **read-only**; kein Dokument-Upload-Endpunkt. |
| **Phase 3 — Vorgesetzten-Cockpit** | Braucht Identity-Mapping (siehe oben). |
| **Phase 4 — OCR / KI-Nachweiserfassung** | Nicht begonnen. |
| **Audit-Trail der Matrixänderungen (Konzept Kap. 8)** | Bewusst offen. |

---

## Code-Landkarte

- **Migrationen:** `backend/alembic/versions/v1_86_schulungen` … `v1_94_schulung_verantwortlicher`
- **Router:** `onboarding.py`, `schulungen.py`, `einarbeitung.py`, `kompetenzen.py` (Prefix `/api/hr/*`, Viewer-read / Mutationen admin-gated)
- **Services:** `schulung_import.py`, `kompetenz_import.py`, `onboarding_dokumente.py`, `schulungsuebersicht_pdf.py`, `schulungsprotokoll_pdf.py`, `einarbeitung_pdf.py`, `onboarding_paket_pdf.py`, `pdf_logo.py`
- **Frontend:** `OnboardingPage.tsx`, `SchulungenPage.tsx`, `KompetenzenPage.tsx` (+ `HrHomePage`, `HrSettingsPage`)
- **Einstieg:** Hauptseite → HR-Kachel → Onboarding / Schulungen / Kompetenzen
