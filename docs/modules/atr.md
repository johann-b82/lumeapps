# ATR-Modul (Lieferschein → ATR-Dokument)

Automatisiert das Erstellen von **ATR-Dokumenten** aus Diehl-**Lieferscheinen**:
Ein Lieferschein-PDF wird eingelesen, seine Positionen werden gegen den
**Teilekatalog** gematcht, und daraus werden die drei Ausgabedateien erzeugt
(ATR-Excel, ATR-PDF, Container-Etikett) — optional vollautomatisch von einem
Netzlaufwerk.

Ablauf:

```
Lieferschein-PDF ─► Parsen ─► Matchen (Teilekatalog) ─► Entwurf (draft)
     ─► Review/Freigabe ─► Generieren (xlsx + pdf + docx)
     ─► [Scan-Herkunft] in Output schreiben + Quelle ins Archiv verschieben
```

Zwei Einstiegswege:

- **Automatischer Scan** eines SMB-Eingangsordners (Scheduler-Job), Standard
  im **Review-Modus** (legt Entwürfe an, wartet auf Freigabe) oder optional
  **Auto-Modus** (generiert + liefert ohne Rückfrage).
- **Manueller Upload** eines PDFs im Frontend, bzw. „Aus Eingangsordner
  verarbeiten".

---

## Frontend / Bedienung

Alles admin-only. Der Umschalter zwischen den beiden ATR-Ansichten liegt als
**Dropdown im SubHeader** (die fixe Leiste unter dem Logo), URL-gesteuert:

| Route | Ansicht |
|---|---|
| `/atr` | **Lieferungen** (Liste, Standard) |
| `/atr/teilekatalog` | **Teilekatalog** (Referenzteile, inline editierbar) |
| `/atr/deliveries/:id` | **Review** einer Lieferung (Kopfdaten + Positionen, Generieren) |
| `/atr/import` | Referenzdatei(en) importieren (Vorschau → Commit) |
| `/atr/template` | Struktur-Vorlage & Kopfdaten der ATR |

Auf der **Review-Seite** werden die Kopffelder (ATR-Nr., Container-Nr., …)
bearbeitet und pro Position **Gewicht** und **PO Pos** editiert; nicht
zugeordnete Positionen sind rot markiert. „Generieren" erzeugt die Dateien und
bietet sie zum Download an.

In der **Lieferungen-Liste** lassen sich mehrere Lieferungen per Checkbox
markieren; „Containerbeschriftung erstellen" fragt eine Containernummer ab
(vorbelegt, wenn alle markierten schon dieselbe tragen), schreibt sie in alle
markierten Lieferungen und lädt eine **gemeinsame Containerbeschriftung** für
den ganzen Container herunter. Die Spalte **Containernummer** zeigt die
Zuordnung. Ein Container ist die Menge aller Lieferungen mit derselben Nummer;
die Sammelbeschriftung wird bei jedem Abruf live daraus gebaut (nicht
gespeichert) und lässt sich jederzeit über Auswahl + Button neu ziehen. Die
Containernummer ändert man ebenso: neu markieren, Button, andere Nummer.

Alle Listen nutzen die gemeinsame [`DataTable`](../../frontend/src/components/DataTable.tsx)
(Card + Suche + sortierbare Spalten + Pagination, 25/Seite).

---

## Automatischer Scan (Scheduler)

Job `_run_atr_scan` in [`app/scheduler.py`](../../backend/app/scheduler.py),
Intervall `atr_scan_interval_s` (0 = aus). Pro Lauf:

1. Neue PDFs im SMB-Eingangsordner auflisten.
2. **Dedup:** Ein Dateiname wird nur übersprungen, solange dazu noch eine
   **offene `draft`-Lieferung** existiert (verhindert Entwurf-Spam alle paar
   Sekunden, solange die Datei auf Review wartet). Sobald eine Lieferung über
   `draft` hinaus ist (`generated`/`delivered`), gilt eine wieder auftauchende
   gleichnamige Datei als bewusstes erneutes Ablegen und wird **neu
   verarbeitet** — ein Dateiname wird also **nicht** für immer ignoriert.
3. Parsen → Matchen → Entwurf anlegen (`origin = "scan"`).
4. Bei `atr_auto_mode = true`: sofort generieren, in Output schreiben und die
   Quelldatei ins Archiv verschieben. Schlägt das fehl, wird der Entwurf
   gelöscht und beim nächsten Scan erneut versucht.

> Deployment-Invariante: Der API-Container läuft mit `--workers 1`
> (`docker-compose.yml`), damit der Scan nicht mehrfach parallel feuert.

---

## Parsen & Matchen

**Text-Extraktion** via `pdftotext -layout`
([`atr_lieferschein.py`](../../backend/app/services/atr_lieferschein.py)).
Pro Lieferschein-Position werden u. a. gelesen:

| Feld | Quelle im Lieferschein |
|---|---|
| Pos / Artikel / Menge | Positionszeile `1 6060 1 STK` |
| `part_number` | `Ihre Nr. VR11S1010016000` |
| `ba_auftrag` | `Auftrag Nr. 1024738 / 5` → **1024738** |
| **`po_pos`** | `Auftrag Nr. 1024738 / 5` → **5** (die Positionsnummer) |
| `po_base` + Konfiguration (Programm, Compartment, MSN, Bett) | `Bestelldaten 4501119979/A350/CCRC/MSN830/6-Bett` |

**PO Pos kommt aus dem Lieferschein**, nicht aus dem Katalog: Der Matcher
([`atr_match.py`](../../backend/app/services/atr_match.py)) übernimmt `po_pos`
für gematchte **und** ungematchte Positionen aus der geparsten Zeile und
überschreibt damit den Katalog-Standard (die reale Position variiert pro
Lieferung).

**Matching:** `part_number` wird normalisiert und gegen den Teilekatalog
(`atr_part`) gesucht. Treffer übernehmen Bezeichnung, Zeichnung/Index, Gewicht
und Kategorie aus dem Katalog; ohne Treffer bleibt die Position `unmatched`
(rot in der Review).

---

## Generieren

[`atr_deliver.py`](../../backend/app/services/atr_deliver.py) → `generate_and_deliver`:

- **ATR-Excel** aus der Struktur-Vorlage (`atr_template.structure_xlsx`) via
  [`atr_generate_xlsx.py`](../../backend/app/services/atr_generate_xlsx.py).
- **ATR-PDF** aus dem Excel via LibreOffice (`convert_xlsx_to_pdf`). Schlägt die
  Konvertierung fehl, bleiben xlsx + docx nutzbar (Warnung).
- **Container-Etikett (docx)** via
  [`atr_generate_docx.py`](../../backend/app/services/atr_generate_docx.py)
  (`build_containerbeschriftung`, eine Lieferung). Dieselbe Datei liefert
  `build_container_label` für die **Sammelbeschriftung** eines Containers
  (`GET /api/atr/deliveries/container-label?nr=…`): Überschrift „Container …",
  darunter ein Block BA/PO/Pos/MSN je Lieferung auf einer Querseite; ab drei
  Lieferungen mit kleinerer Schrift, ab fünf skaliert (bis acht Lieferungen
  bleibt es eine Seite).
- **Kopf:** Titel + Doc-No/Datum/Seite werden im PDF-Schritt via LibreOffice UNO
  gesetzt ([`atr_uno_header.py`](../../backend/app/services/atr_uno_header.py)),
  da openpyxl den Druckkopf verstümmelt. Das **Logo** (App-Logo aus
  `AppSettings.logo_data`) kommt als **Header-Hintergrundgrafik** (`LEFT_TOP`)
  in den Kopf — die Excel-`&G`-Grafik rendert LibreOffice beim PDF-Export nicht,
  Floating-Shapes werden am Kopfrand abgeschnitten.
- Für **Scan-Herkunft** und konfiguriertes SMB: Dateien in den Output schreiben,
  bei Erfolg Status `delivered` setzen, committen und **dann** die Quelldatei
  ins Archiv verschieben. Schlägt der Share-Schreibvorgang fehl, bleibt der
  Status `generated` und die Quelle wird **nicht** archiviert.

---

## HTTP-Endpunkte (admin-only)

Prefix `/api/atr` ([`atr.py`](../../backend/app/routers/atr.py)) und
`/api/atr/deliveries` ([`atr_delivery.py`](../../backend/app/routers/atr_delivery.py)).

| Methode | Pfad | Zweck |
|---|---|---|
| `GET/POST/PATCH/DELETE` | `/api/atr/parts[/{id}]` | Teilekatalog (CRUD) |
| `GET/PATCH` | `/api/atr/template` | ATR-Kopfdaten |
| `POST` | `/api/atr/template/structure` | Struktur-Arbeitsmappe hochladen |
| `POST` | `/api/atr/import/preview` · `/commit` | Referenzdatei(en) einlesen |
| `POST` | `/api/atr/deliveries/upload` | Lieferschein-PDF hochladen → Entwurf |
| `GET` | `/api/atr/deliveries/input-files` | PDFs im SMB-Eingang auflisten |
| `POST` | `/api/atr/deliveries/input-files/process` | Eine Eingangsdatei manuell verarbeiten |
| `GET` | `/api/atr/deliveries` · `/{id}` | Lieferungen listen / Detail |
| `PATCH` | `/api/atr/deliveries/{id}` · `/{id}/items/{item_id}` | Kopf- / Positionsdaten ändern |
| `POST` | `/api/atr/deliveries/{id}/generate` | Dokumente erzeugen (+ ggf. liefern) |
| `GET` | `/api/atr/deliveries/{id}/files/{kind}` | `atr_xlsx` · `atr_pdf` · `label_docx` herunterladen |

---

## Konfiguration & Datenmodell

Zentral auf der `AppSettings`-Singleton-Zeile, gepflegt im Admin-Reiter
**Einstellungen → ATR** ([`AtrSettingsPage.tsx`](../../frontend/src/pages/AtrSettingsPage.tsx)):

| Feld | Zweck |
|---|---|
| `atr_smb_host` · `atr_smb_share` · `atr_smb_domain` · `atr_smb_user` · `atr_smb_password_enc` | SMB-Zugang (Servicekonto; Passwort Fernet-verschlüsselt) |
| `atr_input_path` · `atr_output_path` · `atr_archive_path` | Eingang / Ausgabe / Archiv auf dem Share |
| `atr_scan_interval_s` | Scan-Intervall in Sekunden (0 = aus) |
| `atr_auto_mode` | `false` = Review, `true` = automatisch generieren + liefern |

Tabellen: `atr_part` (Teilekatalog), `atr_template` (Struktur-Vorlage + Kopfdaten),
`atr_delivery` + `atr_delivery_item` (Lieferungen/Positionen). Migrationen
`v1_63_atr_reference`, `v1_64_atr_delivery`, `v1_65_atr_fileserver`.

---

## Beteiligte Dateien

| Datei | Rolle |
|---|---|
| `backend/app/services/atr_lieferschein.py` | Lieferschein-PDF → Header + Positionen (inkl. `po_pos`) |
| `backend/app/services/atr_match.py` | Positionen gegen den Teilekatalog matchen |
| `backend/app/services/atr_deliver.py` | Generieren + (Scan) in Output schreiben & archivieren |
| `backend/app/services/atr_generate_xlsx.py` · `atr_generate_docx.py` | ATR-Excel/PDF bzw. Container-Etikett bauen |
| `backend/app/services/atr_fileserver.py` | SMB-Zugriff (auflisten, lesen, schreiben, archivieren) |
| `backend/app/scheduler.py` (`_run_atr_scan`) | Scan-Job + Dedup + Auto-Modus |
| `backend/app/routers/atr.py` · `atr_delivery.py` | HTTP-Endpunkte |
| `frontend/src/pages/AtrPartsPage.tsx` | ATR-Seite: URL-gesteuerte Ansicht (Lieferungen/Teilekatalog) |
| `frontend/src/pages/AtrDeliveriesPage.tsx` · `AtrDeliveryReviewPage.tsx` · `AtrImportPage.tsx` · `AtrTemplatePage.tsx` | Lieferungen-Liste · Review · Import · Vorlage |
| `frontend/src/components/SubHeader.tsx` | ATR-Umschalter im SubHeader |
| `frontend/src/components/DataTable.tsx` | Gemeinsame Tabellen-Komponente |
