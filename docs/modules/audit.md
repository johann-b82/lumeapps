# Audit-Modul (v1.84)

Auditplanung und Phasen-Checkliste für interne und externe Audits (EN 9100 /
EN 9110, EASA Part 21 Subpart G/J, Part 145).

**Status: Phase 1 — Kern-Workflow.** Was gebaut ist, ist vollständig und
getestet. Was fehlt, steht unten unter *Nicht implementiert* — bitte lies das,
bevor du das Modul als audit-sicher gegenüber einer Behörde darstellst.

---

## Was implementiert ist

| Bereich | Umfang |
|---|---|
| Audits | Anlegen, bearbeiten, filtern (Status/Art/Kategorie/Jahr); Audit-Nr. eindeutig |
| Phasen-Checkliste | Aus Vorlage instanziiert; Status, Verantwortlicher, Soll-/Ist-Termin, Kommentar je Phase |
| Phasen-Vorlagen | Standard-Ablauf mit 10 Phasen (§3 der Anforderung) wird per Migration angelegt; weitere Vorlagen pro Auditkategorie anlegbar |
| Fortschritt | `x / y Phasen`, Prozentbalken, Ampel; abgeleitet, nicht gespeichert |
| Überfälligkeit | Abgeleitet aus Soll-Terminen und `planned_end` |
| Statusmodell | 8 Audit-Status, 4 Phasen-Status; Übergänge nur explizit und protokolliert |
| Normmatrix | Editierbare Stammdaten (Regelwerk, Revision, Kapitel, Kurztext, Gültigkeit, `verified`) |
| Änderungshistorie | Append-only Trail, eine Zeile je geändertem Feld (wer/wann/was/alt→neu) |

### Datenmodell

Sieben Tabellen, alle in `backend/app/models/audit.py`, Migration
`v1_84_audit` (chained auf `v1_83_email_office365`):

`audit_norm_references`, `audit_phase_templates`, `audit_phase_template_steps`,
`audits`, `audit_norm_links`, `audit_phases`, `audit_trail_entries`.

### API

`backend/app/routers/audit.py`, Prefix `/api/audit`, Router-Level Admin-Gate.
Vollständige Routenliste im Modul-Docstring.

Es gibt bewusst **kein DELETE** für Audits, Phasen oder Trail-Einträge. Ein
Audit, das nicht hätte existieren sollen, wird auf `abgesagt` gesetzt, nicht
gelöscht — sonst verlöre der Trail seinen Bezugspunkt. Norm-Referenzen werden
deaktiviert (`active = false`), nicht gelöscht; der FK ist `ON DELETE RESTRICT`.

### Frontend

Erreichbar über die **Qualität-Kachel** auf der Hauptseite → `/quality/home`
(Hub, analog zum Produktion-Hub). Der Hub enthält zwei Kacheln: *Audits* und
eine Verknüpfung auf das bestehende Qualitäts-KPI-Dashboard.

- `/quality/home` — Qualität-Hub (admin-only)
- `/quality/audit` — Auditübersicht (admin-only)
- `/quality/audit/:id` — Detail mit Phasen-Checkliste, Norm-Bezug und Historie
- `/quality` — Qualitäts-KPI-Dashboard, unverändert und weiterhin auch über den
  KPI-Dashboard-Hub erreichbar (eigene, viewer-taugliche Gating-Regel)

Deutsch und Englisch vollständig gepflegt (`de.json` / `en.json`, Parität
CI-geprüft).

---

## Bewusste Design-Entscheidungen

**„Überfällig" ist kein gespeicherter Status.** Die Anforderung listet es als
Sonderstatus, aber es ist eine reine Funktion aus Soll-Termin und heutigem
Datum. Gespeichert wäre der Wert falsch, sobald eine Frist verstreicht, ohne
dass jemand den Datensatz anfasst. Berechnet wird er in
`backend/app/services/audit_status.py`. `status` enthält ausschließlich Werte,
die ein Mensch gesetzt hat.

**Der Audit-Status wird nicht aus den Phasen abgeleitet.** Auch bei 100 %
erledigter Checkliste bleibt das Audit stehen, wo der Mensch es gelassen hat —
„keine automatische Schließung ohne menschliche Freigabe". Der Phasenfortschritt
speist nur die Fortschrittsanzeige. Das Schließen ist eine eigene Aktion und
verlangt eine Begründung.

**Phasen werden kopiert, nicht referenziert.** Beim Anlegen eines Audits werden
die Schritte der Vorlage in eigene `audit_phases`-Zeilen kopiert. Wird die
Vorlage später geändert, bleiben laufende Audits unverändert — sonst würde eine
Stammdatenpflege rückwirkend die Historie eines bereits durchgeführten Audits
verändern.

**Pflichtphasen brauchen eine Begründung.** Eine Pflichtphase auf „nicht
zutreffend" zu setzen, verlangt einen nicht-leeren `skip_reason`. Erzwungen an
drei Stellen (Pydantic-Validator, Re-Check im PATCH-Handler, DB-CheckConstraint)
und als eigener Trail-Eintrag `phase_skip` mit Begründung protokolliert.

**Der Trail speichert die Directus-User-UUID, sonst nichts zur Person.** Siehe
den nächsten Abschnitt.

---

## Nicht implementiert — bekannte Lücken

Diese Punkte aus Abschnitt 8 der Anforderung sind **offen**. Sie sind keine
Nachlässigkeit, sondern hängen an Voraussetzungen außerhalb dieses Moduls.

### 1. Rollenmodell: nur Admin/Viewer

`backend/app/security/roles.py` kennt genau zwei Rollen. Die geforderte
Trennung *Auditor / Lead-Auditor / Auditierter / QM-Leitung / Leseansicht* ist
damit nicht abbildbar. Folgen:

- **Das Vier-Augen-Prinzip beim Auditabschluss ist NICHT implementiert.** Mit
  austauschbaren Admins gibt es kein „Ersteller ≠ Freigeber", das man prüfen
  könnte. Der Abschluss verlangt derzeit nur eine Begründung.
- **Die Unabhängigkeitsprüfung der Auditoren ist NICHT implementiert.** Das
  System kennt den Verantwortungsbereich eines Auditors nicht und kann daher
  nicht warnen, wenn jemand den eigenen Bereich auditiert (21.A.139 /
  21.A.239 / 145.A.200).
- Das gesamte Modul ist admin-gated; ein Viewer sieht es nicht.

Voraussetzung: eine modul-eigene `audit_members`-Tabelle (fachliche Rolle +
Verantwortungsbereich), aufgesetzt auf die Directus-Identität.

### 2. Benutzeridentität ist unvollständig

Das Directus-JWT trägt nur `id` und `role`. `CurrentUser.email` ist ein
synthetischer Platzhalter (`{uuid}@directus.example.com`, siehe das
`TODO(Phase 28+)` in `backend/app/security/directus_auth.py`). Der Trail
speichert deshalb **nur die UUID und die Rolle** — einen erfundenen Namen in ein
revisionssicheres Protokoll zu schreiben wäre schlechter als gar keiner. Für
ALCOA+ *attributable* und für jede Form elektronischer Signatur muss zuerst der
echte Benutzerdatensatz aus Directus geholt werden. Bis dahin zeigt die
Historie UUIDs, keine Klarnamen.

### 3. Revisionssicherheit gilt auf Applikationsebene

Der Trail ist append-only, *weil der Code keinen anderen Pfad anbietet*: kein
UPDATE, kein DELETE, keine Route. Die Datenbankrolle der Anwendung besitzt aber
weiterhin UPDATE/DELETE-Rechte auf `audit_trail_entries` — eine direkte
SQL-Sitzung könnte Einträge ändern. Das zu schließen (Rechte entziehen oder
Rule/Trigger) ist offen.

### 4. Normmatrix ist ungeprüft

Die per Migration eingespielten Kapitelangaben stammen aus dem
Anforderungsdokument und sind **nicht** gegen die geltende konsolidierte
Fassung (EASA Easy Access Rules) verifiziert. Alle Seed-Zeilen tragen deshalb
`verified = false`. Das Feld ist genau dafür da: ein Mensch prüft und setzt es.
Kein Anwendungscode verzweigt über Normwerte — sie sind Etiketten, keine Logik.

### 5. Noch nicht gebaut

Findings/CAPA (Klassifizierung Major/Minor/Beobachtung/OFI, Ursachenanalyse,
Wirksamkeitsprüfung), Auditprogramm-/Jahresplanung mit Gantt, Dashboard-KPIs,
Lieferanten-/Abteilungs-Stammdaten (derzeit ist `scope_label` Freitext),
Datei-Anhänge je Phase, PDF-/Excel-Export, Fristen-Erinnerungen und Eskalation,
Aufbewahrungsfristen.

---

## Tests

`backend/tests/test_audit_router.py` — 23 Tests, Schwerpunkt auf den
compliance-relevanten Invarianten: Pflichtphasen-Skip nur mit Begründung,
Trail-Vollständigkeit und alt→neu, kein Auto-Close, Fortschritt abgeleitet,
Vorlagenänderung ohne Rückwirkung, kein DELETE-Pfad.

Ausführen (**niemals gegen `acm_kpi`** — siehe `docs/operator-runbook.md`):

```bash
docker compose run --rm --no-deps -e POSTGRES_DB=acm_kpi_test migrate alembic upgrade head
docker compose run --rm --no-deps -e POSTGRES_DB=acm_kpi_test api pytest tests/test_audit_router.py -q
```
