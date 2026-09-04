# KPI-Rechenwege

Eine Notiz je Kennzahl: Was wird angezeigt, woher kommen die Daten, wie wird gerechnet, welche Filter und Sonderfälle gelten, und wo im Code steht es. Die Angaben sind aus dem Code abgeleitet (Stand `main` 9f1f6cc, 2026-09-04), nicht aus der Benutzer-Doku. Wo Code und Doku auseinanderlaufen, steht es im Abschnitt [Auffälligkeiten](#auffälligkeiten-aus-der-code-analyse).

Aufbau jeder Notiz:

- **Anzeige** – Bezeichnung im UI (deutsch) und Endpoint.
- **Daten** – Tabellen, Upload/Parser, Spalten.
- **Rechenweg** – Formel Schritt für Schritt.
- **Filter/Defaults** – Zeitraum, Ausschlüsse, Zielwerte.
- **Sonderfälle** – Division durch 0, fehlende Daten, Duplikate.
- **Code** – Datei und Funktion.

Inhalt: [Gemeinsame Mechanik](#gemeinsame-mechanik) · [Vertrieb](#vertrieb) · [HR](#hr) · [Qualität](#qualität) · [Finanzen](#finanzen) · [Einkauf](#einkauf) · [Produktion](#produktion) · [Auffälligkeiten](#auffälligkeiten-aus-der-code-analyse)

---

## Gemeinsame Mechanik

Diese Regeln gelten für alle Dashboards, sofern die KPI-Notiz nichts anderes sagt.

### Zeitraum

- Der Dashboard-Filter (Preset) liefert `date_from`/`date_to`. Default-Preset ist **„Dieses Jahr"** (1. Januar bis heute) – `frontend/src/contexts/DateRangeContext.tsx`.
- Presets: `thisMonth` = Monatsanfang bis heute, `thisQuarter` = Quartalsanfang bis heute, `thisYear` = Jahresanfang bis heute, `allTime` = keine Datumsparameter, `custom` = frei – `frontend/src/lib/dateUtils.ts`.
- Backend-Default ohne Datumsparameter: **laufender Kalendermonat** (`_month_bounds` in `backend/app/services/hr_kpi_aggregation.py`). Ausnahme Vertrieb: dort bedeutet „keine Parameter" = alles (KPI-Kacheln) bzw. „letzte 12 ISO-Wochen" (Vertriebsaktivität).
- Nur eine Grenze gesetzt oder `date_from > date_to` → HTTP 400 (`_validate_range` in `backend/app/routers/hr_kpis.py`).
- Alle Datumsvergleiche sind inklusiv (`>= first AND <= last`).

### Vergleichsperioden (Delta-Badges)

- **Vorperiode**: gleich langes Fenster, das am Tag vor `date_from` endet (`prior_window_same_length`, `hr_kpi_aggregation.py`). Für Vertrieb rechnet das Frontend die Vorperiode selbst (`frontend/src/lib/prevBounds.ts`): Vormonat/Vorquartal bis zum gleichen Tages-Offset.
- **Vorjahr**: Fenster minus **365 Tage**, kein kalendarischer Jahrestag. Schaltjahr-Drift ist bewusst akzeptiert (`same_window_prior_year`).
- **Delta** = `(aktuell − vorher) / vorher`, also relativ, nicht in Prozentpunkten. Ist `vorher` null oder 0, wird kein Delta gezeigt („—") – `frontend/src/lib/delta.ts`.
- Beim Preset „Dieses Jahr" gibt es nur das Vorjahres-Delta (der Vorperioden-Slot wird ausgeblendet). Bei `allTime` und `custom` werden alle Badges ausgeblendet.
- Die Badge-Farbe folgt dem Vorzeichen, nicht der fachlichen Polarität. Bei Kennzahlen, wo „niedriger = besser" gilt (Verzugsquote, Reklamationsquote), rechnet das Frontend vor dem Delta ins Komplement um (`1 − Quote`), damit Grün eine Verbesserung bedeutet.

### Verlaufsdiagramme (Buckets)

`_bucket_windows` in `backend/app/routers/hr_kpis.py`, automatisch nach Fensterlänge:

| Fensterlänge | Granularität | Label |
|---|---|---|
| ≤ 31 Tage | täglich | `YYYY-MM-DD` |
| ≤ 91 Tage | wöchentlich (ISO, Mo–So) | `YYYY-Www` |
| ≤ 731 Tage | monatlich | `YYYY-MM` |
| darüber | quartalsweise | `YYYY-Qn` |

Übersteuerbar per `granularity=daily|weekly|monthly|quarterly|yearly`. Bucket-Ränder werden auf das Fenster geklemmt. Pro Bucket wird exakt dieselbe Formel wie für die Kachel gerechnet.

### Zielwerte

Zielwerte stehen in `app_settings` (`backend/app/models/_base.py`) und werden über `PATCH /api/settings` gepflegt. Quoten sind als **Bruch** gespeichert (0.02 = 2 %), das Settings-UI zeigt und nimmt Prozent. Der PATCH-Handler überspringt `None`-Werte, ein Zielwert lässt sich über diesen Weg **nicht auf leer zurücksetzen** (siehe Auffälligkeiten).

### Rundung

Das Backend rundet Quoten grundsätzlich nicht. Formatierung passiert im Frontend per `Intl.NumberFormat` (Prozent meist 1 Nachkommastelle, EUR 0 oder 2 Nachkommastellen, je Kachel angegeben).

---

## Vertrieb

Dashboard `/dashboard`, Router `backend/app/routers/kpis.py` und `sales_kpis.py`, Services `backend/app/services/kpi_aggregation.py` und `sales_kpi_aggregation.py`.

### Datenquellen Vertrieb

| Tabelle | Quelldatei / Parser | Upload | Kernspalten |
|---|---|---|---|
| `revenues` | `AswKpf_RG.txt` (RG + GS), `revenue_parser.py` | `POST /api/admin/upload-umsatz` | `vorgang_nr` (PK), `datum`, `wert_eur` (GS negativ) |
| `auftraege` | `AswKpf_AUF.txt`, `auftraege_parser.py` | `POST /api/admin/upload-auftraege` | `vorgang_nr` (PK), `datum`, `wert_eur`, `erfasser`, `customer_name` |
| `offers` | `AswKpf_ANG.txt`, `angebote_parser.py` | `POST /api/admin/upload-angebote` | `vorgang_nr`, `datum`, `wert_eur`, `erfasser` |
| `interessenten` | `dev_excel_INT.txt`, `interessenten_parser.py` | `POST /api/admin/upload-interessenten` | `adress_nr` (PK), `datum_save` |
| `sales_contacts` | Kontakte-Dump (8 oder 16 Spalten), `kontakte_parser.py` | `POST /api/admin/upload-contacts` | `contact_date`, `employee_token`, `contact_type`, `status` |
| `sales_records` | 60-Spalten-Legacy-Export | `POST /api/upload` | nur noch für die Auftragstabelle, seit v1.54 nicht mehr für KPIs |

Deutsches Zahlenformat wird beim Parsen umgewandelt (`.` Tausender weg, `,` → `.`). Uploads sind Upserts auf den PK; der Kontakte-Upload ersetzt dagegen alle Kontakte im Datumsbereich der Datei.

### Umsatz

- **Anzeige**: Kachel „Umsatz". `GET /api/kpis` → `total_revenue`. Registry-Key `sales.revenue`.
- **Daten**: `revenues.wert_eur`, `revenues.datum`.
- **Rechenweg**: `SUM(wert_eur)` über alle Zeilen mit `datum` im Fenster. Gutschriften (GS) sind negativ gespeichert, die Summe ist damit der Netto-Umsatz. Kein Typ-Filter, kein `> 0`-Filter.
- **Filter/Defaults**: Ohne Datumsparameter wird über alle Daten summiert.
- **Sonderfälle**: Keine Zeilen im Fenster → `None` → Router liefert 0 €. Delta gegen 0 oder fehlende Vorperiode → „—".
- **Code**: `aggregate_revenue_summary` in `kpi_aggregation.py`; Router `kpis.py` (`get_kpis`).

### Durchschnittlicher Auftragswert

- **Anzeige**: Kachel „Durchschnittlicher Auftragswert". `GET /api/kpis` → `avg_order_value`.
- **Daten**: `auftraege.wert_eur`, `auftraege.datum` (seit v1.54, vorher `sales_records`).
- **Rechenweg**: `AVG(wert_eur)` über `wert_eur > 0` und `datum` im Fenster. Arithmetisches Mittel je Auftragszeile.
- **Wichtig**: Zähler und Nenner stammen aus `auftraege`, die Kachel „Umsatz" aus `revenues`. Deshalb gilt **nicht** Umsatz ÷ Aufträge gesamt = Ø Auftragswert.
- **Filter/Defaults**: `wert_eur > 0` schließt 0-€- und Storno-Zeilen aus.
- **Sonderfälle**: keine Aufträge → 0.
- **Code**: `aggregate_kpi_summary` in `kpi_aggregation.py`.

### Aufträge gesamt

- **Anzeige**: Kachel „Aufträge gesamt". `GET /api/kpis` → `total_orders`.
- **Daten**: `auftraege.vorgang_nr`.
- **Rechenweg**: `COUNT(vorgang_nr)` mit `wert_eur > 0` und `datum` im Fenster.
- **Sonderfälle**: wie oben, 0 bei leerem Fenster.
- **Code**: `aggregate_kpi_summary` in `kpi_aggregation.py`.

### Umsatzwachstum (Verlaufsdiagramm)

- **Anzeige**: Chart „Umsatzwachstum", Serien „Auftragswert Monat/Quartal/Jahr". `GET /api/kpis/chart`.
- **Daten**: `revenues` (RG + GS).
- **Rechenweg**:
  1. Bucket = `date_trunc(month, datum)` (das Frontend schickt immer `monthly`).
  2. `SUM(wert_eur)` je Bucket, sortiert.
  3. Vergleichsserie nur bei `comparison != none` und gesetzter Vorperiode. Vergleichsmodus je Preset: Monat/Quartal → Vorperiode, Jahr → Vorjahr, sonst keiner (`frontend/src/lib/chartComparisonMode.ts`).
  4. Vergleichsbuckets werden **positional** auf die aktuellen Buckets gelegt (i-tes auf i-tes); fehlende Buckets werden als Lücke (`null`) geführt, überzählige verworfen.
  5. Frontend füllt fehlende Monate mit einer dichten Monatsachse auf (`RevenueChart.tsx`).
- **Sonderfälle**: `null`-Werte bleiben Lücken, werden nicht zu 0. Die KW-Beschriftung beim Monats-Preset ist eine eigene Formel, keine ISO-KW.
- **Code**: `get_kpi_chart` in `kpis.py`; `frontend/src/components/dashboard/RevenueChart.tsx`.

### Kundenanteil (Aufträge) / Kundenanteil (Rechnungen)

- **Anzeige**: zwei Wasserfall-Karten „Kundenanteil (Aufträge)" und „Kundenanteil (Rechnungen)". `GET /api/data/sales/customer-share?source=auftraege|revenues&top_n=14`.
- **Daten**: je nach `source` `auftraege` oder `revenues`: `customer_name`, `wert_eur`, `datum`.
- **Rechenweg**:
  1. `SUM(wert_eur)` je `customer_name` im Fenster, absteigend sortiert.
  2. `total` = Summe aller Kunden.
  3. `top` = erste `top_n` Kunden; `top_share_pct = round(top_sum / total × 100, 2)`; `remaining_share_pct = 100 − top_share_pct`.
  4. Je Kunde `share_pct = round(wert / total × 100, 2)`.
  5. Frontend zeigt standardmäßig Top 3, per Umschalter bis 14; das Restsegment wird im Frontend neu gerechnet als `(total − sichtbare Summe) / total`.
- **Filter/Defaults**: **kein** `> 0`-Filter, Gutschriften gehen bei `revenues` negativ ein.
- **Sonderfälle**: keine Zeilen oder `total <= 0` → alles 0 und leere Liste (verhindert Division durch 0). Kunden mit negativer Nettosumme können negative Anteile erzeugen (kein Guard).
- **Code**: `compute_customer_share` in `sales_kpi_aggregation.py`; `CustomerShareCard.tsx`.

### Vertriebsaktivität (5 Wochen-Balkendiagramme)

Gemeinsame Quelle: `GET /api/data/sales/contacts-weekly?from&to`, Service `compute_contacts_weekly` in `sales_kpi_aggregation.py`. Antwort je ISO-Woche: `interessenten` (global) und `per_employee{token → Werte}`.

Gemeinsame Regeln:

- Wochen-Bucket = ISO-Jahr/ISO-Woche (`date.isocalendar()` bzw. `extract(isoyear/week)`).
- Ohne `from`/`to`: letzte 12 ISO-Wochen bis Sonntag der laufenden Woche. Beim Preset `allTime` ist die Abfrage deaktiviert, die Karte bleibt leer.
- Balken = Summe über alle Vertriebler-Tokens der Woche; der Tooltip zeigt die Aufteilung je Vertriebler.
- Ziellinie je Chart aus `app_settings` mit Fallback, Beschriftung „Ziel n / Woche".

#### Erstkontakte

- **Daten**: `sales_contacts` mit `status = 1`, `contact_date` im Fenster, `employee_token` gesetzt.
- **Rechenweg**: je Woche und Token `COUNT` der Zeilen mit `contact_type = "ERS"`.
- **Ziel**: `target_sales_erstkontakte`, Fallback 50 / Woche.
- **Sonderfälle**: `status != 1` wird ignoriert. Zeilen ohne Token entfallen.

#### Interessenten

- **Daten**: Tabelle `interessenten`, Spalte `datum_save` (seit v1.51, vorher Kontakt-Typen ANFR/EPA).
- **Rechenweg**: `COUNT(*)` je ISO-Woche von `datum_save`. Globaler Wert, kein Vertriebler-Split (Quelldatei hat keine Vertriebler-Spalte).
- **Ziel**: `target_sales_interessenten`, Fallback 5 / Woche.
- **Sonderfälle**: Upsert auf `adress_nr`; wird ein Interessent erneut gespeichert, wandert er mit dem neuen `datum_save` rückwirkend in eine andere Woche.

#### Besuche (Vor Ort + Online, gestapelt)

- **Daten**: `sales_contacts` wie Erstkontakte.
- **Rechenweg**: `contact_type = "ORT"` → `visits`, `"ONL"` → `onl`; Balken = ORT + ONL gestapelt, Ziellinie auf der Stapelsumme.
- **Ziel**: `target_sales_besuche`, Fallback 3 / Woche.

#### Angebote (€)

- **Daten**: Tabelle `offers` (seit v1.52; vorher Heuristik „Kommentar beginnt mit ANGEBOT").
- **Rechenweg**: `SUM(wert_eur)` je ISO-Woche und `erfasser`; Balken = Summe über alle Erfasser. **Einheit EUR**, nicht Anzahl.
- **Ziel**: `target_sales_angebote_eur`, Fallback 25.000 € / Woche.
- **Sonderfälle**: Angebote ohne `erfasser` fallen aus dem Chart.

#### Auftrag / Wo. / VL (€)

- **Daten**: `auftraege` (`datum`, `wert_eur`, `erfasser`).
- **Rechenweg**: `SUM(wert_eur)` je ISO-Woche und `erfasser`; Balken = Wochensumme über alle Vertriebler. **Kein** `> 0`-Filter (anders als die Kacheln).
- **Ziel**: `target_sales_orders_per_rep_eur`, Fallback 50.000 €.
- **Code**: `SalesActivityCard.tsx` (`buildPerRepSeries`, `buildBesucheStackedSeries`).

### € / Woche / Vertriebler und Top-3-Kundenanteil (Endpoint ohne UI)

- **Anzeige**: Komponente `OrdersDistributionCard` existiert, wird aber auf keiner Seite gerendert (siehe Auffälligkeiten). `GET /api/data/sales/orders-distribution`.
- **Daten**: `auftraege` mit `wert_eur > 0`.
- **Rechenweg**: `rep_count` = Anzahl unterschiedlicher `erfasser`; `weeks = max(1, Kalendertage // 7 + 1)`; `orders_per_week_per_rep = round(Σ wert_eur / rep_count / weeks, 2)`. Top 3 = Kundensummen absteigend, `top3_share_pct = round(top3 / total × 100, 2)`.
- **Sonderfälle**: `rep_count = 0` → 0; `total` fällt auf 1.0 zurück (Division-Schutz).
- **Code**: `compute_orders_distribution` in `sales_kpi_aggregation.py`.

### Zielwerte Vertrieb

`target_sales_erstkontakte`, `target_sales_interessenten`, `target_sales_besuche`, `target_sales_angebote_eur`, `target_sales_orders_per_rep_eur` in `app_settings`; UI `SalesTargetsCard.tsx`.

---

## HR

Dashboard `/hr`, Router `backend/app/routers/hr_kpis.py`, `hr_overtime.py`, `hr_weekly.py`, `hr_belegschaft.py`, Service `backend/app/services/hr_kpi_aggregation.py`.

### Datenquellen HR (Personio-Sync)

Kein Datei-Upload, sondern täglicher Sync (`backend/app/services/hr_sync.py`):

| Tabelle | Personio-Quelle | Kernspalten |
|---|---|---|
| `personio_employees` | `/company/employees` | `status`, `department`, `hire_date`, `termination_date`, `weekly_working_hours`, `raw_json` (kompletter Personio-Datensatz inkl. `work_schedule`, Gehalt, Geschlecht, Supervisor) |
| `personio_attendance` | `/v2/attendance-periods` (V2, seit v1.111) | `date`, `start_time`, `end_time`, `break_minutes`. Personio liefert je Segment eine Zeile; nur `WORK`-Segmente werden übernommen, `BREAK`-Segmente verworfen, daher `break_minutes = 0` |
| `personio_absences` | `/company/time-offs` (Krankheit, Urlaub, tagesbasiert) und `/company/absence-periods` (Freizeitausgleich, stundenbasiert) | `absence_type_id`, `start_date`, `end_date`, `time_unit`, `hours` |

Bei tagesbasierten Abwesenheiten wird `hours = Tage × Tagesarbeitszeit` mit Tagesarbeitszeit = `weekly_working_hours / 5`, Fallback 8 h. Offene Abwesenheiten ohne Ende bekommen `end_date = start_date`.

`app_settings`: `personio_sick_leave_type_id` (Liste der Krank-Typ-IDs), `personio_production_dept` (Produktionsabteilungen), `personio_skill_attr_key` (Kompetenz-Attribute); Zielwerte `target_overtime_ratio`, `target_sick_leave_ratio`, `target_fluctuation`, `target_revenue_per_employee`.

### Überstunden-Quote

- **Anzeige**: Kachel „Überstunden-Quote", Untertitel „Überstunden / Gesamtarbeitsstunden aktiver Mitarbeiter". `GET /api/hr/kpis` → `overtime_ratio`. Verlauf `GET /api/hr/kpis/history`.
- **Daten**: `personio_attendance` join `personio_employees.weekly_working_hours`.
- **Rechenweg** je Anwesenheitszeile im Fenster:
  1. Zeilen ohne `start_time` oder `end_time` überspringen.
  2. `worked = (end − start − break_minutes) / 60` in Stunden; `worked <= 0` überspringen.
  3. `total_hours += worked`.
  4. Wenn `weekly_working_hours` gesetzt: `daily_quota = weekly_working_hours / 5`; `overtime += max(0, worked − daily_quota)`.
  5. Quote = `overtime / total_hours`.
- **Filter/Defaults**: Zeitraum aus dem Dashboard-Filter. Keine Feiertags- oder Wochenendlogik; `is_holiday` wird gespeichert, aber nirgends ausgewertet.
- **Sonderfälle**: `total_hours = 0` → `None`. Mitarbeiter ohne `weekly_working_hours` zählen im Nenner, nie im Zähler. Die Rechnung läuft **je Zeile**, nicht je Tag: bei mehreren Segmenten pro Tag wird das Tagessoll mehrfach abgezogen (Überstunden werden untertrieben, siehe Auffälligkeiten).
- **Code**: `_overtime_ratio` in `hr_kpi_aggregation.py`.

### Krankheitsquote

- **Anzeige**: Kachel „Krankheitsquote". `GET /api/hr/kpis` → `sick_leave_ratio`.
- **Daten**: `personio_absences` mit `absence_type_id` in `personio_sick_leave_type_id`; `personio_employees` für Sollstunden.
- **Rechenweg**:
  1. **Krankstunden**: alle Abwesenheiten, die das Fenster überlappen. `clipped_days` = Kalendertage der Überlappung (inkl. Wochenende). Bei `time_unit = "hours"` mit `hours`: anteilig `hours × clipped_days / Gesamttage`. Sonst `weekly_working_hours / 5 × clipped_days` (Fallback 8 h/Tag).
  2. **Sollstunden**: `weekdays` = Anzahl Mo–Fr im Fenster; aktive Mitarbeiter am Fensterende (`hire_date <= last` und `termination_date` leer oder `> last`); `Σ (weekly_working_hours / 5 × weekdays)`, Fallback 40 h/Woche.
  3. Quote = Krankstunden / Sollstunden.
- **Filter/Defaults**: Ohne konfigurierte Krank-Typ-IDs → `is_configured = false`, Kachel zeigt „—" mit Link zu den Einstellungen.
- **Sonderfälle**: `weekdays = 0`, keine aktiven Mitarbeiter oder Soll = 0 → `None`. Feiertage zählen als Solltage. Der Stunden-Zweig (`time_unit == "hours"`) greift für synchronisierte Daten nie, weil der Sync `"hour"`, `"day"` oder `"days"` schreibt (siehe Auffälligkeiten).
- **Code**: `_sick_leave_ratio` in `hr_kpi_aggregation.py`.

### Fluktuation

- **Anzeige**: Kachel „Fluktuation". `GET /api/hr/kpis` → `fluctuation`.
- **Daten**: `personio_employees.hire_date`, `.termination_date`.
- **Rechenweg**: Austritte = `COUNT` mit `termination_date` im Fenster. Nenner = **durchschnittlicher aktiver Personalbestand über alle Kalendertage** des Fensters (je Tag zählt, wer `hire_date <= Tag` und `termination_date` leer oder `> Tag` hat; Summe / Anzahl Tage). Quote = Austritte / Ø Bestand.
- **Filter/Defaults**: keine Abteilungsfilterung im KPI-Pfad.
- **Sonderfälle**: Ø Bestand = 0 → `None`. Der Wert ist **nicht annualisiert**: ein Monatsfenster ergibt die Monatsquote.
- **Code**: `_fluctuation`, `_avg_active_headcount_across_range` in `hr_kpi_aggregation.py`.

### Kompetenzentwicklung

- **Anzeige**: Kachel „Kompetenzentwicklung". `GET /api/hr/kpis` → `skill_development`. Nicht im Verlaufsdiagramm.
- **Daten**: `personio_employees.raw_json.attributes.<key>.value` für jeden Key in `personio_skill_attr_key`.
- **Rechenweg** (Stichtag = Fensterende, kein Zeitraum): Nenner = aktive Mitarbeiter am Stichtag. Zähler = davon jene, bei denen mindestens ein konfiguriertes Attribut nicht leer/`null` ist. Quote = Zähler / Nenner.
- **Filter/Defaults**: ohne konfigurierte Keys → `is_configured = false`.
- **Sonderfälle**: Nenner 0 → `None`. Vorperiode/Vorjahr sind Stichtagswerte (heutige Stammdaten), keine echten historischen Snapshots. Deshalb kein Verlauf.
- **Code**: `_skill_development`, `_headcount_at_eom` in `hr_kpi_aggregation.py`.

### Umsatz / Produktions-MA

- **Anzeige**: Kachel „Umsatz / Produktions-MA" (EUR, 0 Nachkommastellen). `GET /api/hr/kpis` → `revenue_per_production_employee`.
- **Daten**: Umsatz aus `auftraege` (`SUM(wert_eur)` mit `wert_eur > 0`, wie „Aufträge gesamt"); Kopfzahl aus `personio_employees` mit `department` in `personio_production_dept`.
- **Rechenweg**: `revenue / headcount`, Kopfzahl am Fensterende.
- **Sonderfälle**: Umsatz `None` oder `<= 0` → `None`; Kopfzahl 0 → `None`; ohne konfigurierte Abteilungen → `is_configured = false`.
- **Hinweis**: Zähler ist der **Auftragswert** (`auftraege`), nicht der Rechnungsumsatz (`revenues`), den die Personalkostenquote nutzt.
- **Code**: `_revenue_per_production_employee` in `hr_kpi_aggregation.py`.

### Mitarbeitertabelle: Ist-Std., Überstunden, ÜS %

- **Anzeige**: Tabelle „Mitarbeiter", Spalten „Ist-Std.", „Überstunden", „ÜS %". `GET /api/data/employees/overtime?date_from&date_to` (Pflichtparameter).
- **Daten**: wie Überstunden-Quote.
- **Rechenweg** je Mitarbeiter: `total_hours = Σ worked`; `daily_quota = weekly_working_hours / 5`, **Fallback 8 h** wenn nicht gesetzt (Unterschied zur Kachel); `overtime = Σ max(0, worked − daily_quota)`; `overtime_ratio = round(overtime / total, 4)` nur wenn `total > 0` und `overtime > 0`, sonst `None`.
- **Filter/Defaults**: Nur Mitarbeiter mit Anwesenheit im Fenster; Frontend füllt fehlende mit 0 auf. Tabellen-Default-Filter „Mit Überstunden", Sortierung Überstunden absteigend. `date_from > date_to` → HTTP 422.
- **Code**: `hr_overtime.py`; `EmployeeTable.tsx`.

### Weekly Report (nur Admin)

`GET /api/hr/weekly-report?year&week`, Router `hr_weekly.py`. Personenbezogene Leistungs- und Gesundheitsdaten, deshalb Admin-Gate und `<AdminOnly>` im Frontend.

Grundlagen:

- Woche = ISO-Woche, Montag bis Sonntag; Vorwoche = minus 7 Tage.
- **Tagessoll** je Mitarbeiter aus `raw_json.attributes.work_schedule.value.attributes` (`monday` … `sunday` als `HH:MM`, `08:45` → 8,75 h). Fehlt ein brauchbarer Schedule, gilt flach `weekly_working_hours / 5` an allen 7 Tagen, Fallback 8 h. `weekly_working_hours` ist **nicht** der Wochenwert (Vollzeit-40 h steht dort als „8"), deshalb der Schedule-Weg.
- Krank-Typ-IDs aus `personio_sick_leave_type_id`, Fallback-Set `{568234, 3270500}`.

#### Saldo Mehrarbeit (Std.)

- **Rechenweg**:
  1. Ist-Stunden erst je (Mitarbeiter, Tag) summieren (Personio liefert Vor-/Nachmittag getrennt), `worked = (end − start − break) / 60`, negativ → 0.
  2. Ist je Mitarbeiter nur über Tage mit Tagessoll > 0; `letzter_tag` = spätester gestempelter Tag der Woche.
  3. **Entschuldigte Stunden**: alle Abwesenheiten (Urlaub, Krank, FZA …), die die Woche überlappen. Die `hours` werden **proportional zum Tagessoll** auf die Solltage der gesamten Abwesenheitsspanne verteilt; nur Tage in der Woche werden gespeichert.
  4. **Effektives Wochensoll** = `Σ max(0, Tagessoll − entschuldigt)` über die Wochentage bis zur Grenze. **Laufende Woche** (Sonntag ≥ letztes Anwesenheitsdatum in der DB): Grenze = `letzter_tag` des Mitarbeiters, spätere Tage gelten als noch nicht erfasst. **Abgeschlossene Woche**: Grenze = Sonntag, fehlende Tage sind echte Fehlstunden.
  5. `netto = Ist − Soll_eff`; Kachel = `round(Σ netto über alle Mitarbeiter, 2)`.
- **Sonderfälle**: Nur Mitarbeiter mit mindestens einer Anwesenheitszeile in der Woche werden berücksichtigt. Feiertage ohne Personio-Abwesenheit erscheinen in abgeschlossenen Wochen als Fehlstunden. Leere Menge → `None`.
- **Code**: `_anwesenheit_woche`, `_entschuldigte_stunden`, `_tagessoll_aus_schedule` in `hr_weekly.py`.

#### Geleistete Überstunden (Std.), Top 5

Personen mit `max(0, netto) > 0.01`, absteigend, Top 5. Wer unter dem Wochensoll bleibt, erscheint nicht.

#### Krankheit (Tage) / Krankheit (Std.)

- **Rechenweg**: Abwesenheiten mit Krank-Typ, die die Woche überlappen. `spanne` = Kalendertage der Abwesenheit, `ueberlapp` = Kalendertage in der Woche. **Tage**: `days_count` aus `raw_json` (berücksichtigt halbe Tage), Fallback `hours / 8`; `Tage_Woche = days_count / spanne × ueberlapp`. **Stunden**: `hours / spanne × ueberlapp`. Kachel = `round(Σ, 2)`.
- **Umschalter** Tage/Stunden im Frontend; Top-5-Liste je Person wird bei „Std." neu sortiert.
- **Sonderfälle**: Verteilung über **Kalendertage**, während die entschuldigten Stunden über **Solltage** verteilt werden (siehe Auffälligkeiten).
- **Code**: `_krankheit_woche`, `_krank_tage_gesamt` in `hr_weekly.py`; `WeeklyReportSection.tsx`.

#### KW-Auswahl (Meta)

`GET /api/hr/weekly-report/meta`: verfügbare Wochen aus allen Anwesenheits- **und** Abwesenheitsdaten (Abwesenheiten sind aktueller), gefiltert auf ≤ aktuelle KW; erste = Default-Auswahl.

### Belegschafts-KPIs

`GET /api/hr/belegschaft-kpi?jahr&quartal`, Router `hr_belegschaft.py`, Funktion `aggregiere_belegschaft` (auch vom Newsletter-Snapshot genutzt). Viewer-lesbar, nur Aggregate.

- **Modus „Aktuell"** (ohne `jahr`): Grundmenge `status = 'active'`; „neu" = Eintritt seit Quartalsbeginn.
- **Modus Jahr/Quartal**: Stichtag = `min(Periodenende, heute)`. Kopfzahl über Ein-/Austritt: `hire_date <= Stichtag` und `termination_date` leer oder `> Stichtag`; `status` wird hier nicht ausgewertet. „neu" = `hire_date` zwischen Periodenstart und Stichtag.

| Kennzahl | Rechenweg |
|---|---|
| Gesamt | Anzahl der so ermittelten Mitarbeiter |
| Geschlecht | `raw_json.attributes.gender.value` → männlich/weiblich/divers, sonst „unbekannt". Anzeige in **Prozent**, ganzzahlig nach Größter-Rest-Methode (Summe exakt 100) |
| Beschäftigungsart | Kaskade: `employment_type = external` → extern; sonst Attribut mit Label „Art der Beschäftigung" (Substring geringf/teilzeit/vollzeit); sonst irgendein Attribut mit „geringfügig" → geringfügig; Rest → **vollzeit**. Anzeige absolut |
| Neu vs. Bestand | siehe Modus, absolut |
| Mitarbeiter je Abteilung | `department` oder „Sonstige", absteigend |

- **Sonderfälle**: Verteilungen (Geschlecht, Beschäftigungsart, Abteilung) nutzen immer die **heutigen** Stammdaten der damals Beschäftigten, Personio liefert keine Historie. Nur Kopfzahl und Neu/Bestand sind echt stichtagsbezogen. Quartal außerhalb 1–4 → HTTP 422.
- **Code**: `hr_belegschaft.py`; `BelegschaftKpiSection.tsx` (`prozente`).

### Personen-Feeds (keine Quoten)

- **Geburtstage diese Woche** (`GET /api/hr/birthdays/this-week`, Kiosk-Klon unter `/api/hr/embed/`): aktuelle ISO-Woche, aktiv = `status = active` und kein Austritt vor heute; Geburtsdatum per rekursiver Suche nach Label „Geburtsdatum" in `raw_json`; 29.02. → 28.02. in Nicht-Schaltjahren.
- **Neue Mitarbeitende** (`GET /api/hr/joiners/recent?weeks=2`): `hire_date` in den letzten `weeks × 7` Tagen, keine Zukunftseintritte; `days_with_company = heute − hire_date`.
- **Organigramm** (`GET /api/hr/org-chart`): nur aktive, `supervisor_id` aus `raw_json.attributes.supervisor.value.attributes.id.value`.

---

## Qualität

Dashboard `/quality`, Router `backend/app/routers/quality_kpis.py`, Services `quality_kpi_aggregation.py`, `complaint_rate_aggregation.py`, `inspection_aggregation.py`.

### Datenquellen Qualität

| Tabelle | Quelldatei / Parser | Upload | Kernspalten |
|---|---|---|---|
| `quality_records` | `8D.txt`, `quality_parser.py` | `POST /api/upload-quality` (Upsert auf `report_nr`) | `report_date` („Datum"), `art`, `level` (aus „Artikel"), `quantity` („Menge"), `accepted_quantity` („akzeptierte Menge") |
| `delivery_records` | `AswKpf_LS.xlsx`, `delivery_parser.py` (nur `Typ = LS`) | Lieferschein-Upload | `delivery_date`, `quantity`, `order_nr` |
| `goods_receipt_records` | `AswKpf_WE`, `goods_receipt_parser.py` (nur `Typ = WE`) | Wareneingang-Upload | `receipt_date`, `quantity`, `material_group` (WGR) |
| `inspection_records` | `AswQs2151.txt`, `inspection_parser.py` | `POST /api/upload-inspections` (Replace-by-Date-Range) | `pruef_datum`, `benutzer`, `buchungs_menge`, `ausschuss_menge`, `rsc`, `size_class`, `excluded` |

Level-Ableitung im Parser: Text enthält `Major … Level 1` → Level 1, `Minor … Level 2` → Level 2, sonst leer. Zeilen mit `gelöscht = J` werden verworfen.

### Audit-Findings Level 1 / Level 2

- **Anzeige**: Kacheln „Audit-Findings Level 1" und „Level 2", Chart „… nach Kategorie". `GET /api/quality/audit-findings` → `level_1`, `level_2`. Registry-Key `quality.audit_findings`.
- **Daten**: `quality_records` mit `art` in den Audit-Codes `BH AUD`, `EX AUD`, `IN AUD`, `KU AUD`.
- **Rechenweg**: `COUNT(*)` je `level` (1 oder 2) über `report_date` im Fenster und `art` im Filter. Reine Zeilenzahl, keine Mengen, keine Quote.
- **Filter/Defaults**: `audit_types` als Komma-Liste, Default alle vier; unbekannte Codes → HTTP 400. Verlauf zusätzlich je `art` aufgeschlüsselt, der Bucket-Gesamtwert ist die Summe der Aufschlüsselung.
- **Zielwerte**: `target_audit_findings_level1` (Fallback 0), `target_audit_findings_level2` (Fallback 5), als gestrichelte Linie.
- **Sonderfälle**: Zeilen ohne erkanntes Level zählen nicht, erscheinen aber in der Tabelle `/audit-findings/list` (Limit 500) als Diagnose. Keine Division.
- **Code**: `quality_kpi_aggregation.py`; `QualityKpiCardGrid.tsx`, `QualityKpiCharts.tsx`.

### On Quality (Kunde / intern / Material Lieferanten / Werkbänke)

- **Anzeige**: Kachel „On Quality (…)" mit Untertitel „Fehlerquote: x", Chart „On Quality (…) im Zeitverlauf", Kacheln „Gelieferte Stück" und „Reklamierte Stück" bzw. „Akzeptierte Reklamationsmenge". `GET /api/quality/complaint-rate?complaint_type=customer|internal|supplier|subcontractor&qty_mode=total|accepted`. Registry-Keys `quality.complaint_*`.
- **Daten**: Zähler aus `quality_records`, Nenner je Typ aus `delivery_records` oder `goods_receipt_records`.
- **Rechenweg**:
  1. Art-Codes je Typ: Kunde `KUNRE`/`KUN RE`, intern `INT RE`/`INRE`, Lieferant `LIE RE`/`LIERE`, Werkbänke `UA RE`/`UARE` (beide Schreibweisen bilden einen Bucket).
  2. Mengenspalte: `qty_mode = total` → `quantity`, `accepted` → `accepted_quantity`.
  3. Zähler = `SUM(Menge)` über `report_date` im Fenster und `art` im Set. Kein Level-, kein Statusfilter.
  4. Nenner: Kunde und intern = `SUM(delivery_records.quantity)` über `delivery_date` im Fenster (auch für interne Reklamationen bewusst die Kundenlieferungen). Lieferant = `SUM(goods_receipt_records.quantity)` mit `material_group` **nicht in** `{DIENST, SERVIC}` (oder leer). Werkbänke = `SUM` mit `material_group` **in** `{DIENST, SERVIC}`.
  5. `rate = Zähler / Nenner` (Bruch). **On Quality = 1 − rate** wird im Frontend gebildet; Deltas werden im On-Quality-Raum gerechnet.
- **Filter/Defaults**: `complaint_type` Default `customer`, `qty_mode` Default `total`.
- **Zielwerte** (als Fehlerquote gespeichert): `target_complaint_rate_customer` (Fallback 0.02), `_internal` (0.04), `_supplier` (0.02), `_subcontractor` (0.05). Soll-Linie = `1 − Ziel`.
- **Rundung**: On Quality 3 Nachkommastellen, Fehlerquote 2, Mengen 0. Kein ppm im Code.
- **Sonderfälle**: Nenner ≤ 0 → `rate = None` → „—", im Chart Lücke. `NULL`-Mengen zählen als 0. Zähler- und Nennerdatum sind verschiedene Felder (`report_date` vs. `delivery_date`), eine Reklamation kann in einem anderen Bucket liegen als die zugehörige Lieferung.
- **Code**: `complaint_rate_aggregation.py`; `ComplaintRateCardGrid.tsx`, `ComplaintRateChart.tsx`.

### Große Produkte (geprüft) / Kleine Produkte (geprüft)

- **Anzeige**: Kacheln „Große Produkte (geprüft)" und „Kleine Produkte (geprüft)", Einheit „Produkte/Tag/Mitarbeiter". `GET /api/quality/inspections` → `large_count`, `small_count`. Registry-Key `quality.inspections`.
- **Daten**: `inspection_records`. Klassifikation beim Parsen: Produktgruppe enthält `DIEHL` → klein; Bezeichnung enthält `LITERATURE POCKET`, `LIT POCKET`, `STRAP `, `STRAP,`, `LEDERRIEMEN`, `STOWAGE POUCH`, `AUFBEWAHRUNGSTASCHE` → klein; Regex `net|netz` als Wortanfang → klein; sonst groß. `Typ = WKZ` wird verworfen.
- **Rechenweg**:
  1. Filter: `pruef_datum` im Fenster, `rsc = '70000'` (echte Qualitätsprüfung), `excluded = false`.
  2. Zähler je Klasse = `SUM(buchungs_menge)`.
  3. **Gemeinsamer** Nenner über beide Klassen = `COUNT(DISTINCT benutzer) × COUNT(DISTINCT pruef_datum)`.
  4. `count = round(Zähler / Nenner)` (Python-`round`, Banker's Rounding, Integer).
- **Zielwerte**: `target_inspection_large` (Fallback 150), `target_inspection_small` (Fallback 400).
- **Sonderfälle**: Nenner ≤ 0 → **0**, nicht `None` (Kachel zeigt „0"). Per Admin-Häkchen ausgeschlossene Buchungen (`PATCH /api/quality/inspections/bookings/{id}`) fallen aus Zähler und Nenner. Re-Upload ersetzt alle Zeilen im Datumsbereich der Datei; dabei gehen gesetzte `excluded`-Häkchen im Bereich verloren.
- **Code**: `inspection_aggregation.py`, `inspection_parser.py`; `QualityInspectionCardGrid.tsx`, `QualityInspectionCharts.tsx`.

### Ausschussquote je Produkt (nur Tabelle)

`GET /api/quality/inspections/list`: je `(bezeichnung, size_class)` mit demselben Filter `scrap_rate = SUM(ausschuss_menge) / SUM(buchungs_menge)`, bei Summe ≤ 0 → `None`. Sortiert nach Buchungsmenge absteigend, kein Limit, kein Zielwert, keine Kachel.

---

## Finanzen

Dashboard `/finance`, Router `backend/app/routers/finance_kpis.py`, Services `material_cost_aggregation.py`, `personnel_cost_aggregation.py`.

### Materialkostenquote

- **Anzeige**: Kachel „Materialkostenquote" (Untertitel „Materialkosten / Umsatz"), Kacheln „Materialkosten", „Umsatz", „Ohne Preis"; Chart und Prüftabelle „Materialverbrauch je Artikel". `GET /api/finance/material-cost-ratio`, `/history`, `/list`. Registry-Key `finance.material_cost_ratio`.
- **Daten**: `material_movements` (`AswLagBew.txt`, `POST /api/upload-material-movements`, Replace-by-Date-Range), `material_prices` (`AswKpf_WE.txt`, `POST /api/upload-material-prices`, Upsert), `revenues`.
- **Rechenweg**:
  1. **Preisliste**: je `artnr` die **neueste** WE-Zeile mit `menge ≠ 0` und `pos_wert` gesetzt; `unit_price = pos_wert / menge`. Die Rohspalte `preis` wird bewusst nicht genutzt (kann je 100/1000 Stück sein). Die Preisliste ist **fensterunabhängig**.
  2. **Verbrauch** je Artikel im Fenster: `consumed = −SUM(bewegungsmenge)` über `buchtyp in (M, SM)` (Entnahme negativ, Storno positiv). Artikel mit Netto 0 entfallen.
  3. **Materialkosten** = `Σ consumed × unit_price` über Artikel **mit** Preis. Artikel ohne Preis werden nicht mit 0 bewertet, sondern ausgelassen und in `unmatched_articles` gezählt.
  4. **Umsatz** = `SUM(revenues.wert_eur)` im Fenster (Netto inkl. negativer Gutschriften).
  5. `ratio = Materialkosten / Umsatz` (Bruch).
- **Filter/Defaults**: Standardzeitraum wie in der gemeinsamen Mechanik. Vorperiode und Vorjahr nutzen dieselbe **heutige** Preisliste. Zielwert `target_material_cost_ratio` (Bruch, UI in Prozent), ohne Wert keine Ziellinie.
- **Rundung**: Kosten/Umsatz 2 Stellen, Quote ungerundet; Tabelle: Menge 3, Preis 4, Kosten 2 Stellen, Limit 500 Zeilen, ohne Preis ans Ende.
- **Sonderfälle**: Umsatz ≤ 0 → `None`. Negativer Nettoverbrauch (mehr Storno als Entnahme) ergibt negative Kosten (kein Guard). Bewegungs-Re-Upload derselben Datei ist ein No-Op.
- **Code**: `material_cost_aggregation.py`; `MaterialCostRatioCardGrid.tsx`, `MaterialCostRatioChart.tsx`, `MaterialCostRatioTable.tsx`.

### Personalkostenquote

- **Anzeige**: Kachel „Personalkostenquote" (Untertitel „Personalkosten / Umsatz"), Kacheln „Personalkosten", „Umsatz", „Mitarbeiter (mit Kosten im Zeitraum)"; Chart und Tabelle „Personalkosten je Abteilung". `GET /api/finance/personnel-cost-ratio`, `/history`, `/list`. Registry-Key `finance.personnel_cost_ratio`.
- **Daten**: `personio_employees.raw_json.attributes.fix_salary.value` bzw. `hourly_salary.value` (aktueller Snapshot, **keine Gehaltshistorie**), `personio_attendance`, `revenues`.
- **Rechenweg** je Mitarbeiter:
  1. Gehaltswerte mit deutscher/englischer Dezimal-Erkennung parsen.
  2. **Festgehalt** (`fix_salary > 0`, monatlich brutto): monatsweise tagesgenau anteilig über aktive Tage im Fenster (`max(Monatsanfang, first, hire_date)` bis `min(Monatsende, last, termination_date)`), voller Monat = ein Monatsgehalt.
  3. **Stundenlohn** (kein Fixgehalt, `hourly_salary > 0`): `hourly_salary × Ist-Stunden` aus `personio_attendance` im Fenster (`(end − start)/3600 − break/60`, negativ → 0).
  4. Wer beides nicht hat oder Kosten ≤ 0 → trägt nichts bei, zählt nicht im `headcount`.
  5. Umsatz = `SUM(revenues.wert_eur)` im Fenster; `ratio = Personalkosten / Umsatz`.
- **Filter/Defaults**: wie Materialkostenquote; Zielwert `target_personnel_cost_ratio`.
- **Sonderfälle**: Umsatz ≤ 0 → `None`. Brutto ohne Arbeitgeber-Overhead (bewusst). `break_minutes = NULL` lässt die betroffene Schicht still aus der Summe fallen. Einzelgehälter werden nie ausgegeben, die Tabelle zeigt nur Abteilung, Kopfzahl, Kosten; Abteilung leer → „—".
- **Code**: `personnel_cost_aggregation.py`; `PersonnelCostRatioCardGrid.tsx`, `PersonnelCostRatioTable.tsx`.

---

## Einkauf

Dashboard `/procurement`, Router `backend/app/routers/procurement_kpis.py`, Services `otd_aggregation.py`, `stock_order_aggregation.py`.

### Liefertermintreue / OTD-Quote

- **Anzeige**: Sektion „Liefertermintreue / OTD", Kachel „OTD-Quote" (Untertitel „Pünktliche Positionen / gesamt (Verzug ≤ 0)"), Kacheln „Pünktliche Positionen", „Gesamt-Positionen", „Ø Verzug (Tage)"; Chart und Tabelle „Lieferpositionen". `GET /api/procurement/otd`, `/history`, `/list`. Registry-Key `procurement.otd`.
- **Daten**: `delivery_reliability` aus `dev_excel_Liefertreue_Einkauf.txt` (`POST /api/upload-delivery-reliability`, Upsert auf Auftrag/Pos/UPos): `delivered_date` („geliefert"), `target_date` („Lieferdatum"), `verzug_tage` („Verzug (Tage)"), `supplier_name`, Artikel.
- **Rechenweg**:
  1. Fenster über das **Ist-Lieferdatum** `delivered_date`.
  2. Nenner = `COUNT` der Positionen im Fenster (je Position, nicht nach Menge).
  3. Zähler = `COUNT` mit `verzug_tage <= 0` (Toleranz 0 Tage, Konstante `PUNCTUAL_MAX_VERZUG`; frühe Lieferungen sind pünktlich).
  4. `rate = Zähler / Nenner` (Bruch).
  5. `avg_delay = SUM(verzug_tage) / COUNT(verzug_tage)` über alle Positionen (NULLs zählen nicht).
- **Filter/Defaults**: Standardzeitraum; keine Gruppierung nach Lieferant (Lieferant nur als Spalte/Suchfeld). Zielwert **fest 98 %** im Frontend (`OTD_TARGET` in `OtdChart.tsx`), kein Settings-Feld.
- **Rundung**: keine im Backend; Prozent 1 Nachkommastelle, Tage 1 Nachkommastelle mit Vorzeichen. Tabelle Limit 500.
- **Sonderfälle**: Nenner 0 → `rate = None`; keine Verzugswerte → `avg_delay = None`. `verzug_tage = NULL` zählt im Nenner, kann nie pünktlich sein und drückt die Quote. Keine Storno- oder Teillieferungslogik (kein Statusfeld im Export).
- **Code**: `otd_aggregation.py`; `OtdCardGrid.tsx`, `OtdChart.tsx`, `OtdTable.tsx`.

### Bestellung auf Lager – Top 20 Ladenhüter

- **Anzeige**: Umschalter „Bestellung auf Lager", Tabelle „Bestellung auf Lager – Top 20 Artikel des Jahres", Summenzeile „Gebundenes Kapital (Top 20)". `GET /api/procurement/stock-orders/top?limit=20&inactive_days=28`. Registry-Key `procurement.stock_orders`.
- **Daten**: `material_movements` (alle geladenen Bewegungen), `stock_article_prices` aus der AswLagBew-Preisliste (`POST /api/upload-stock-prices`, kompletter Snapshot-Replace): `unit_price = Wert / Preismenge`, erste Zeile je Artikel gewinnt.
- **Rechenweg** (eine SQL-Abfrage):
  1. Lagerartikel = `artikelnr LIKE 'L%'`.
  2. Je Artikel `stock_qty = SUM(bewegungsmenge)` über **alle** Bewegungen (kein Zeit-, kein Buchtyp-Filter) und `last_movement = MAX(buch_datum)`.
  3. INNER JOIN auf die Preisliste.
  4. Ladenhüter = `last_movement < heute − inactive_days` und `stock_qty > 0`.
  5. `value = stock_qty × unit_price`; `ORDER BY value DESC LIMIT 20`.
  6. „Gebundenes Kapital" = Summe der angezeigten Top 20 (clientseitig).
- **Filter/Defaults**: Der globale Dashboard-Zeitraum wird **ignoriert**, Stichtag ist immer heute; das Frontend sendet `inactive_days` nie (immer 28). Kein Zielwert.
- **Sonderfälle**: Artikel ohne Preiszeile fallen durch den INNER JOIN still heraus (kein Zähler wie bei der Materialkostenquote). `Preismenge` ≤ 0 → Divisor 1. Der „Bestand" ist nur so vollständig wie die hochgeladene Bewegungshistorie. Kein Backend-Test für diesen Service.
- **Code**: `stock_order_aggregation.py`, `stock_price_parser.py`; `StockOrderTopTable.tsx`.

---

## Produktion

Dashboard `/production` (KPI-Sicht), Router `backend/app/routers/production_kpis.py`, Service `production_kpi_aggregation.py`. Einzige registrierte KPI-Familie: `production.verzug`. Wartung (`maintenance.py`) und Sensoren (`sensors.py`) berechnen keine Kennzahlen.

### Datenquellen Produktion

| Tabelle | Quelldatei / Parser | Upload | Kernspalten |
|---|---|---|---|
| `auftrag_positionen` | `AswKpf_AUF.txt` (Positionsebene), `auftrag_positionen_parser.py` (nur `Typ = AUF`) | `POST /api/admin/upload-auftrag-positionen` (Upsert auf Vorgang/Pos/UPos) | `vorgang_nr`, `lieferdatum` (Zieltermin), `customer_name`, `customer_id`, `pos_typ_2` |
| `delivery_records` | `AswKpf_LS.xlsx`, `delivery_parser.py` | Lieferschein-Upload | `order_nr` („Auftrag"), `delivery_date` |

Join `auftrag_positionen.vorgang_nr = delivery_records.order_nr` (LEFT JOIN).

### Verzugsquote, Aufträge in Verzug, Aufträge gesamt, Ø Verzug

- **Anzeige**: Abschnitt „Aufträge in Verzug (Seriengeschäft)", Kacheln „Verzugsquote", „Aufträge in Verzug", „Aufträge gesamt", „Ø Verzug (Tage)". `GET /api/production/verzug` → `rate`, `in_verzug_count`, `total_count`, `avg_delay`.
- **Rechenweg**:
  1. **Zieltermin je Auftrag** = `MAX(lieferdatum)` über die Positionen (Positionen ohne Lieferdatum entfallen). `customer_name`/`adr_nr` = `MAX(...)` als repräsentativer Kunde.
  2. **Ist-Fertigstellung je Auftrag** = `MAX(delivery_date)` über alle Lieferscheinzeilen mit passendem `order_nr`.
  3. `effective = COALESCE(Ist, heute)`; `delay = effective − Ziel` in Tagen.
  4. **Gezählt** wird ein Auftrag nur, wenn sein Ausgang feststeht: `Ist vorhanden` **oder** `Ziel < heute`. Noch nicht fällige offene Aufträge sind weder im Zähler noch im Nenner.
  5. Fenster über den **Zieltermin**: `Ziel` zwischen `date_from` und `date_to`.
  6. `total_count = COUNT` der gezählten; `in_verzug_count = COUNT` mit `delay > 0` (zu spät geliefert **plus** überfällig offen); `rate = in_verzug / total`.
  7. `avg_delay = SUM(delay) / total` über **alle** gezählten Aufträge, pünktliche gehen negativ ein, der Wert kann negativ sein.
- **Filter/Defaults**: Standardzeitraum. Seriengeschäft-Filter über `pos_typ_2` ist vorbereitet, die Konstante `SERIENGESCHAEFT_POS_TYP_2` ist aber **leer**, es werden alle Aufträge gezählt. Beim Preset `allTime` fällt das Backend auf den laufenden Monat zurück. Zielwert `target_produktion_verzug` (Bruch, UI „Max. Verzugsquote" in Prozent) als Ziellinie im Verlauf.
- **Delta**: im Frontend über das Komplement `1 − rate` (Termintreue), damit sinkender Verzug grün ist.
- **Sonderfälle**: `total = 0` → `rate` und `avg_delay` `None`, die Zähler-Kachel zeigt 0. Überfällige offene Aufträge wachsen täglich (`heute − Ziel`), auch für abgeschlossene Zeiträume; der Nenner kann sich für Zeiträume, die die Gegenwart überlappen, nachträglich vergrößern. **Teillieferungen**: eine einzige frühe Teillieferung macht den Auftrag zu „geliefert", der Rest wird nie geprüft.
- **Code**: `_auf_subquery`, `_ls_subquery`, `_counts_for_window`, `compute_verzug` in `production_kpi_aggregation.py`; `ProductionVerzugCardGrid.tsx`.

### Verzugsquote im Zeitverlauf

`GET /api/production/verzug/history`: je Bucket dieselbe Rechnung mit einem globalen `heute`; Buckets ohne gezählte Aufträge → `rate = null` (Lücke). Y-Achse fest 0–100 %. Leeres Ergebnis → Chart-Karte wird nicht gerendert.

### Tabellen „Aufträge in Verzug" und „Überfällige offene Aufträge"

- **Aufträge in Verzug** (`/verzug/list`): INNER JOIN, `Ziel` im Fenster und `Ist > Ziel`; `verzug_tage = Ist − Ziel`; nur zu spät **gelieferte**, zeitstabil. Limit 500, Client-Pagination 50.
- **Überfällige offene Aufträge** (`/verzug/overdue`): LEFT JOIN, `Ziel` im Fenster, **kein** Lieferschein, `Ziel < heute`; `days_overdue = heute − Ziel`, wächst täglich. Limit 500.
- Beide zusammen ergeben `in_verzug_count`. Teilgelieferte Aufträge erscheinen in der Überfällig-Liste nie.

---

## Auffälligkeiten aus der Code-Analyse

Im Code belegte Punkte, die eine fachliche Entscheidung brauchen. Keine davon wurde in dieser Doku-Änderung angefasst.

**Rechenlogik**

1. **Krankheitsquote, Stundenzweig tot**: `_sick_leave_ratio` prüft `time_unit == "hours"`, der Sync schreibt `"hour"`, `"day"` oder `"days"`. Stundenbasierte Abwesenheiten werden daher immer über Kalendertage × Tagessatz gerechnet, auch über Wochenenden (`hr_kpi_aggregation.py`, `hr_sync.py`).
2. **Überstunden-Quote je Zeile statt je Tag**: Bei mehreren Personio-Segmenten pro Tag wird das Tagessoll mehrfach abgezogen. Der Weekly Report summiert dagegen erst je (Mitarbeiter, Tag). Zwei nicht ineinander überführbare Überstunden-Definitionen laufen parallel.
3. **Krankheit im Weekly Report** verteilt über Kalendertage, entschuldigte Stunden über Solltage.
4. **Zwei Umsatzbegriffe**: „Umsatz / Produktions-MA" und die Vertriebs-Kacheln nutzen `auftraege` (Auftragswert), Material- und Personalkostenquote nutzen `revenues` (Rechnungsumsatz).
5. **Uneinheitliche Null-Filter im Vertrieb**: `wert_eur > 0` gilt für Ø Auftragswert, Aufträge gesamt und `orders-distribution`, nicht für Umsatz, Kundenanteil und den Wochen-Balken „Auftrag / Wo. / VL".
6. **OTD-Positionen ohne Verzugswert** zählen im Nenner und nie im Zähler.
7. **Personalkostenquote** lässt Schichten mit `break_minutes = NULL` still weg.
8. **Verzug**: Seriengeschäft-Filter ist leer, obwohl der Abschnittstitel „(Seriengeschäft)" sagt; Teillieferungen gelten als geliefert; Ø Verzug ist ein Mittel über alle Aufträge, nicht nur über verspätete (die Benutzer-Doku sagt „durchschnittliche Verspätung").
9. **Ladenhüter**: Titel „des Jahres" hat keine Entsprechung im Code; der Dashboard-Zeitraum wird ignoriert; Artikel ohne Preis verschwinden ohne Hinweis.
10. **Materialkostenquote** bewertet Vorperiode und Vorjahr mit der heutigen Preisliste.

**UI und Doku**

11. **Zielwerte lassen sich nicht leeren**: `PATCH /api/settings` überspringt `None`, das Frontend sendet bei leerem Feld aber `null` (Qualität, Finanzen, Produktion). Die Produktions-Doku verspricht „leeres Feld blendet die Linie aus".
12. **`OrdersDistributionCard` ist nicht gemountet**: Endpoint `/api/data/sales/orders-distribution` und Komponente existieren, `DashboardPage.tsx` rendert sie nicht. Die Zahl „€ / Woche / Vertriebler" erscheint stattdessen als Wochen-Balken mit anderer Rechenlogik.
13. **Benutzer-Doku veraltet**: `sales-dashboard.md` (Kachelname, Default-Preset, Anzahl Diagramme, Interessenten- und Angebots-Definition), `hr-dashboard.md` (behauptet, es gebe keinen Zeitraumfilter; Weekly Report und Belegschaft fehlen), `production-dashboard.md` (Ø Verzug, Zielwert leeren).
14. **KPI-Registry-Lücken**: Für Ø Auftragswert, Aufträge gesamt, Umsatzwachstum und Kundenanteil gibt es keinen Registry-Key, an diese Kacheln können keine Bubbles/Maßnahmen gehängt werden.
15. **Toter Schalter** `SUPPLIER_USES_FMD_COMPLEMENT` in `complaint_rate_aggregation.py` wird nirgends gelesen; der Model-Docstring von `goods_receipt_records` beschreibt einen JOIN, der nicht mehr existiert; der Router-Docstring der Inspektionen nennt die Aggregation noch „STUB".
