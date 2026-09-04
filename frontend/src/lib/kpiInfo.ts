/**
 * Calculation notes per KPI, shown by `KpiInfoButton` (the "i" next to a
 * KPI label). One markdown body per locale. Derived from the backend code;
 * the long-form reference with code locations is `docs/kpi-rechenwege.md`.
 *
 * Entries flagged `period: "range"` get the shared paragraph about the
 * dashboard date range and the delta badges appended automatically.
 */

export type KpiInfoKey =
  | "sales.revenue"
  | "sales.avg_order_value"
  | "sales.total_orders"
  | "sales.revenue_chart"
  | "sales.customer_share_auftraege"
  | "sales.customer_share_revenues"
  | "sales.erstkontakte"
  | "sales.interessenten"
  | "sales.besuche"
  | "sales.angebote"
  | "sales.orders_per_rep"
  | "hr.overtime_ratio"
  | "hr.sick_leave_ratio"
  | "hr.fluctuation"
  | "hr.skill_development"
  | "hr.revenue_per_employee"
  | "hr.employee_overtime"
  | "hr.weekly_saldo"
  | "hr.weekly_ueberstunden"
  | "hr.weekly_krankheit"
  | "hr.weekly_krankheit_personen"
  | "hr.belegschaft_geschlecht"
  | "hr.belegschaft_beschaeftigung"
  | "hr.belegschaft_eintritt"
  | "hr.belegschaft_abteilungen"
  | "quality.audit_findings_l1"
  | "quality.audit_findings_l2"
  | "quality.complaint_customer"
  | "quality.complaint_internal"
  | "quality.complaint_supplier"
  | "quality.complaint_subcontractor"
  | "quality.delivered_qty"
  | "quality.complaint_qty"
  | "quality.inspection_large"
  | "quality.inspection_small"
  | "finance.material_cost_ratio"
  | "finance.material_cost"
  | "finance.revenue"
  | "finance.unmatched"
  | "finance.personnel_cost_ratio"
  | "finance.personnel_cost"
  | "finance.headcount"
  | "procurement.otd"
  | "procurement.punctual_count"
  | "procurement.total_count"
  | "procurement.avg_delay"
  | "procurement.stock_orders"
  | "production.verzug"
  | "production.in_verzug_count"
  | "production.total_count"
  | "production.avg_delay";

interface KpiInfoEntry {
  de: string;
  en: string;
  /** "range" = follows the dashboard date filter (shared paragraph appended). */
  period: "range" | "none";
}

const COMMON_RANGE = {
  de: `

**Zeitraum & Vergleich**
- Zeitraum = Dashboard-Filter (Standard „Dieses Jahr" = 1. Januar bis heute). Beide Datumsgrenzen zählen mit.
- Vorperiode = gleich langes Fenster direkt davor. Vorjahr = Fenster minus 365 Tage.
- Delta = (aktuell − vorher) ÷ vorher, relativ. Ist „vorher" 0 oder unbekannt, wird „—" gezeigt.
- Bei „Dieses Jahr" gibt es nur das Vorjahres-Delta; bei „Gesamt" und freiem Zeitraum keine Deltas.`,
  en: `

**Period & comparison**
- Period = dashboard date filter (default "This year" = 1 January to today). Both bounds are inclusive.
- Previous period = a window of the same length directly before. Previous year = the window minus 365 days.
- Delta = (current − prior) ÷ prior, relative. If "prior" is 0 or unknown, "—" is shown.
- "This year" shows only the year-over-year delta; "All time" and custom ranges show no deltas.`,
};

const INFO: Record<KpiInfoKey, KpiInfoEntry> = {
  // ---------------------------------------------------------------- Vertrieb
  "sales.revenue": {
    period: "range",
    de: `**Formel**
Summe aller Rechnungsbeträge im Zeitraum: \`SUM(wert_eur)\`.

**Daten**
Tabelle \`revenues\` aus dem Upload \`AswKpf_RG.txt\` (Rechnungen RG und Gutschriften GS). Gutschriften sind negativ gespeichert, die Summe ist deshalb der Netto-Umsatz.

**Filter**
Kein Typ-Filter, kein Ausschluss von 0-€-Zeilen. Nur das Datum entscheidet.

**Sonderfälle**
Keine Rechnungen im Zeitraum → 0 €. Anders als „Ø Auftragswert" und „Aufträge gesamt" kommt dieser Wert aus den **Rechnungen**, nicht aus den Aufträgen; Umsatz ÷ Aufträge ist daher nicht der Ø Auftragswert.`,
    en: `**Formula**
Sum of all invoice amounts in the period: \`SUM(wert_eur)\`.

**Data**
Table \`revenues\` from the \`AswKpf_RG.txt\` upload (invoices RG and credit notes GS). Credit notes are stored negative, so the sum is net revenue.

**Filters**
No type filter, zero-value rows are not excluded. Only the date matters.

**Edge cases**
No invoices in the period → €0. Unlike "Average order value" and "Total orders", this value comes from **invoices**, not orders, so revenue ÷ orders is not the average order value.`,
  },
  "sales.avg_order_value": {
    period: "range",
    de: `**Formel**
Arithmetisches Mittel der Auftragswerte: \`AVG(wert_eur)\` über alle Aufträge mit Wert > 0 im Zeitraum.

**Daten**
Tabelle \`auftraege\` aus dem Upload \`AswKpf_AUF.txt\`.

**Filter**
Aufträge mit 0 € oder negativem Wert (Stornos) werden ausgeschlossen, damit sie den Mittelwert nicht verzerren.

**Sonderfälle**
Keine Aufträge im Zeitraum → 0 €.`,
    en: `**Formula**
Arithmetic mean of order values: \`AVG(wert_eur)\` over all orders with value > 0 in the period.

**Data**
Table \`auftraege\` from the \`AswKpf_AUF.txt\` upload.

**Filters**
Orders with €0 or negative value (cancellations) are excluded so they do not distort the mean.

**Edge cases**
No orders in the period → €0.`,
  },
  "sales.total_orders": {
    period: "range",
    de: `**Formel**
Anzahl der Aufträge: \`COUNT(vorgang_nr)\` über alle Aufträge mit Wert > 0 im Zeitraum.

**Daten**
Tabelle \`auftraege\` aus dem Upload \`AswKpf_AUF.txt\`. Jede Vorgangsnummer zählt einmal (Upsert beim Upload).

**Filter**
0-€- und Storno-Zeilen werden nicht mitgezählt.`,
    en: `**Formula**
Number of orders: \`COUNT(vorgang_nr)\` over all orders with value > 0 in the period.

**Data**
Table \`auftraege\` from the \`AswKpf_AUF.txt\` upload. Each order number counts once (upsert on upload).

**Filters**
Zero-value and cancellation rows are not counted.`,
  },
  "sales.revenue_chart": {
    period: "range",
    de: `**Formel**
Je Monat die Summe der Rechnungsbeträge: \`SUM(wert_eur)\` gruppiert nach \`date_trunc('month', datum)\`.

**Daten**
Tabelle \`revenues\` (RG + GS, Gutschriften negativ).

**Vergleichsserie**
Monat/Quartal-Preset → Vorperiode, Jahres-Preset → Vorjahr, sonst keine. Die Vergleichsmonate werden **positional** auf die aktuellen Monate gelegt (1. auf 1., 2. auf 2. …); fehlende Monate bleiben Lücken.

**Sonderfälle**
Fehlende Monate werden im Diagramm mit einer durchgehenden Monatsachse aufgefüllt. Die Wochenbeschriftung beim Monats-Preset ist keine ISO-Kalenderwoche.`,
    en: `**Formula**
Per month the sum of invoice amounts: \`SUM(wert_eur)\` grouped by \`date_trunc('month', datum)\`.

**Data**
Table \`revenues\` (RG + GS, credit notes negative).

**Comparison series**
Month/quarter preset → previous period, year preset → previous year, otherwise none. Comparison months are aligned **positionally** to the current months (1st to 1st, 2nd to 2nd …); missing months stay gaps.

**Edge cases**
Missing months are filled with a continuous month axis in the chart. The week labels on the month preset are not ISO calendar weeks.`,
  },
  "sales.customer_share_auftraege": {
    period: "range",
    de: `**Formel**
1. Je Kunde \`SUM(wert_eur)\` über die Aufträge im Zeitraum, absteigend sortiert.
2. Anteil je Kunde = Kundensumme ÷ Gesamtsumme × 100 (2 Nachkommastellen).
3. Top-Anteil = Summe der sichtbaren Top-Kunden ÷ Gesamtsumme; Rest = 100 − Top-Anteil.

**Daten**
Tabelle \`auftraege\` (\`customer_name\`, \`wert_eur\`).

**Filter**
Kein Ausschluss von 0-€-Zeilen. Standard-Ansicht Top 3, per Umschalter bis Top 14.

**Sonderfälle**
Keine Aufträge oder Gesamtsumme ≤ 0 → leere Karte. Kunden mit negativer Nettosumme können negative Anteile ergeben.`,
    en: `**Formula**
1. Per customer \`SUM(wert_eur)\` over orders in the period, sorted descending.
2. Share per customer = customer sum ÷ total × 100 (2 decimals).
3. Top share = sum of the visible top customers ÷ total; remainder = 100 − top share.

**Data**
Table \`auftraege\` (\`customer_name\`, \`wert_eur\`).

**Filters**
Zero-value rows are not excluded. Default view top 3, toggle up to top 14.

**Edge cases**
No orders or total ≤ 0 → empty card. Customers with a negative net sum can produce negative shares.`,
  },
  "sales.customer_share_revenues": {
    period: "range",
    de: `**Formel**
1. Je Kunde \`SUM(wert_eur)\` über die Rechnungen im Zeitraum, absteigend sortiert.
2. Anteil je Kunde = Kundensumme ÷ Gesamtsumme × 100 (2 Nachkommastellen).
3. Top-Anteil = Summe der sichtbaren Top-Kunden ÷ Gesamtsumme; Rest = 100 − Top-Anteil.

**Daten**
Tabelle \`revenues\` (RG + GS). Gutschriften gehen negativ ein.

**Filter**
Standard-Ansicht Top 3, per Umschalter bis Top 14.

**Sonderfälle**
Keine Rechnungen oder Gesamtsumme ≤ 0 → leere Karte. Kunden mit netto negativer Summe (mehr Gutschrift als Rechnung) können negative Anteile ergeben.`,
    en: `**Formula**
1. Per customer \`SUM(wert_eur)\` over invoices in the period, sorted descending.
2. Share per customer = customer sum ÷ total × 100 (2 decimals).
3. Top share = sum of the visible top customers ÷ total; remainder = 100 − top share.

**Data**
Table \`revenues\` (RG + GS). Credit notes enter negative.

**Filters**
Default view top 3, toggle up to top 14.

**Edge cases**
No invoices or total ≤ 0 → empty card. Customers with a negative net sum (more credit notes than invoices) can produce negative shares.`,
  },
  "sales.erstkontakte": {
    period: "range",
    de: `**Formel**
Je ISO-Kalenderwoche die Anzahl der Kontakte vom Typ \`ERS\`, summiert über alle Vertriebler. Der Tooltip zeigt die Aufteilung je Vertriebler.

**Daten**
Tabelle \`sales_contacts\` aus dem Kontakte-Upload (\`contact_date\`, \`employee_token\`, \`contact_type\`, \`status\`).

**Filter**
Nur Kontakte mit \`status = 1\` und gesetztem Vertriebler-Kürzel. Beim Preset „Gesamt" bleibt die Karte leer (kein Zeitraum).

**Ziel**
Ziellinie aus den Einstellungen (\`target_sales_erstkontakte\`), Standard 50 pro Woche.

**Sonderfälle**
Der Kontakte-Upload ersetzt alle Kontakte im Datumsbereich der hochgeladenen Datei.`,
    en: `**Formula**
Per ISO calendar week the number of contacts of type \`ERS\`, summed over all sales reps. The tooltip shows the split per rep.

**Data**
Table \`sales_contacts\` from the contacts upload (\`contact_date\`, \`employee_token\`, \`contact_type\`, \`status\`).

**Filters**
Only contacts with \`status = 1\` and a rep token. On the "All time" preset the card stays empty (no period).

**Target**
Target line from settings (\`target_sales_erstkontakte\`), default 50 per week.

**Edge cases**
The contacts upload replaces all contacts within the date range of the uploaded file.`,
  },
  "sales.interessenten": {
    period: "range",
    de: `**Formel**
Je ISO-Kalenderwoche \`COUNT(*)\` der Interessenten nach ihrem Speicherdatum \`datum_save\`. Ein globaler Wert ohne Vertriebler-Aufteilung, weil die Quelldatei keine Vertriebler-Spalte hat.

**Daten**
Tabelle \`interessenten\` aus dem Upload \`dev_excel_INT.txt\` (seit v1.51; vorher aus den Kontakt-Typen ANFR/EPA).

**Ziel**
\`target_sales_interessenten\`, Standard 5 pro Woche.

**Sonderfälle**
Upsert auf die Adressnummer: wird ein Interessent erneut gespeichert, wandert er mit dem neuen Datum rückwirkend in eine andere Woche.`,
    en: `**Formula**
Per ISO calendar week \`COUNT(*)\` of prospects by their save date \`datum_save\`. A global value without rep split, because the source file has no rep column.

**Data**
Table \`interessenten\` from the \`dev_excel_INT.txt\` upload (since v1.51; before that from contact types ANFR/EPA).

**Target**
\`target_sales_interessenten\`, default 5 per week.

**Edge cases**
Upsert on the address number: if a prospect is saved again, it moves retroactively to another week with the new date.`,
  },
  "sales.besuche": {
    period: "range",
    de: `**Formel**
Je ISO-Kalenderwoche die Anzahl der Kontakte vom Typ \`ORT\` (Vor Ort) und \`ONL\` (Online), gestapelt. Balken = ORT + ONL, die Ziellinie liegt auf der Stapelsumme.

**Daten**
Tabelle \`sales_contacts\` aus dem Kontakte-Upload.

**Filter**
Nur Kontakte mit \`status = 1\` und gesetztem Vertriebler-Kürzel.

**Ziel**
\`target_sales_besuche\`, Standard 3 pro Woche.`,
    en: `**Formula**
Per ISO calendar week the number of contacts of type \`ORT\` (on site) and \`ONL\` (online), stacked. Bar = ORT + ONL, the target line sits on the stacked total.

**Data**
Table \`sales_contacts\` from the contacts upload.

**Filters**
Only contacts with \`status = 1\` and a rep token.

**Target**
\`target_sales_besuche\`, default 3 per week.`,
  },
  "sales.angebote": {
    period: "range",
    de: `**Formel**
Je ISO-Kalenderwoche und Erfasser \`SUM(wert_eur)\` der Angebote; der Balken ist die Wochensumme über alle Erfasser. **Einheit EUR**, nicht Anzahl.

**Daten**
Tabelle \`offers\` aus dem Upload \`AswKpf_ANG.txt\` (seit v1.52; vorher Heuristik „Kommentar beginnt mit ANGEBOT").

**Ziel**
\`target_sales_angebote_eur\`, Standard 25.000 € pro Woche.

**Sonderfälle**
Angebote ohne Erfasser fallen aus dem Diagramm.`,
    en: `**Formula**
Per ISO calendar week and creator \`SUM(wert_eur)\` of offers; the bar is the weekly total over all creators. **Unit EUR**, not a count.

**Data**
Table \`offers\` from the \`AswKpf_ANG.txt\` upload (since v1.52; before that the heuristic "comment starts with ANGEBOT").

**Target**
\`target_sales_angebote_eur\`, default €25,000 per week.

**Edge cases**
Offers without a creator drop out of the chart.`,
  },
  "sales.orders_per_rep": {
    period: "range",
    de: `**Formel**
Je ISO-Kalenderwoche und Erfasser \`SUM(wert_eur)\` der Aufträge; der Balken ist die Wochensumme über alle Vertriebler, der Tooltip zeigt die Aufteilung je Vertriebler. **Einheit EUR.**

**Daten**
Tabelle \`auftraege\` (\`datum\`, \`wert_eur\`, \`erfasser\`).

**Filter**
Kein Ausschluss von 0-€- oder Storno-Zeilen (anders als die Kacheln oben).

**Ziel**
\`target_sales_orders_per_rep_eur\`, Standard 50.000 €.`,
    en: `**Formula**
Per ISO calendar week and creator \`SUM(wert_eur)\` of orders; the bar is the weekly total over all reps, the tooltip shows the split per rep. **Unit EUR.**

**Data**
Table \`auftraege\` (\`datum\`, \`wert_eur\`, \`erfasser\`).

**Filters**
Zero-value and cancellation rows are not excluded (unlike the tiles above).

**Target**
\`target_sales_orders_per_rep_eur\`, default €50,000.`,
  },

  // ---------------------------------------------------------------------- HR
  "hr.overtime_ratio": {
    period: "range",
    de: `**Formel**
Je Anwesenheitszeile im Zeitraum:
1. \`worked = (Ende − Start − Pause) ÷ 60\` in Stunden; Zeilen ohne Start/Ende oder mit worked ≤ 0 entfallen.
2. \`total_hours += worked\`.
3. Wenn \`weekly_working_hours\` gesetzt: \`daily_quota = weekly_working_hours ÷ 5\`; \`overtime += max(0, worked − daily_quota)\`.
4. Quote = \`overtime ÷ total_hours\`.

**Daten**
\`personio_attendance\` (Personio-Sync, V2 attendance-periods) und \`personio_employees.weekly_working_hours\`.

**Sonderfälle**
Keine Stunden → „—". Mitarbeiter ohne Wochenstunden zählen im Nenner, nie im Zähler. Gerechnet wird je Zeile, nicht je Tag: bei mehreren Segmenten pro Tag wird das Tagessoll mehrfach abgezogen. Keine Feiertagslogik.`,
    en: `**Formula**
Per attendance row in the period:
1. \`worked = (end − start − break) ÷ 60\` in hours; rows without start/end or with worked ≤ 0 are skipped.
2. \`total_hours += worked\`.
3. If \`weekly_working_hours\` is set: \`daily_quota = weekly_working_hours ÷ 5\`; \`overtime += max(0, worked − daily_quota)\`.
4. Ratio = \`overtime ÷ total_hours\`.

**Data**
\`personio_attendance\` (Personio sync, V2 attendance periods) and \`personio_employees.weekly_working_hours\`.

**Edge cases**
No hours → "—". Employees without weekly hours count in the denominator, never in the numerator. Computed per row, not per day: with several segments per day the daily quota is subtracted several times. No public-holiday logic.`,
  },
  "hr.sick_leave_ratio": {
    period: "range",
    de: `**Formel**
Krankstunden ÷ Sollstunden.
- **Krankstunden**: Abwesenheiten mit Krank-Typ, die den Zeitraum überlappen. Überlappende **Kalendertage** (inkl. Wochenende) × Tagessatz (\`weekly_working_hours ÷ 5\`, Fallback 8 h).
- **Sollstunden**: Anzahl Mo–Fr im Zeitraum × Tagessatz, summiert über alle am Zeitraumende aktiven Mitarbeiter (Fallback 40 h/Woche).

**Daten**
\`personio_absences\` (Personio \`/company/time-offs\`) mit \`absence_type_id\` aus der Einstellung „Krank-Typ-IDs"; \`personio_employees\`.

**Filter**
Ohne konfigurierte Krank-Typ-IDs zeigt die Kachel „—" mit Link zu den Einstellungen.

**Sonderfälle**
Keine Werktage, keine aktiven Mitarbeiter oder Soll = 0 → „—". Feiertage zählen als Solltage. Ein stundenbasierter Rechenzweig existiert, greift für synchronisierte Daten aber nie.`,
    en: `**Formula**
Sick hours ÷ scheduled hours.
- **Sick hours**: absences with a sick-leave type overlapping the period. Overlapping **calendar days** (incl. weekends) × daily rate (\`weekly_working_hours ÷ 5\`, fallback 8 h).
- **Scheduled hours**: number of Mon–Fri days in the period × daily rate, summed over all employees active at the end of the period (fallback 40 h/week).

**Data**
\`personio_absences\` (Personio \`/company/time-offs\`) with \`absence_type_id\` from the "sick leave type IDs" setting; \`personio_employees\`.

**Filters**
Without configured sick-leave type IDs the tile shows "—" with a link to settings.

**Edge cases**
No weekdays, no active employees or scheduled = 0 → "—". Public holidays count as scheduled days. An hour-based branch exists but never applies to synced data.`,
  },
  "hr.fluctuation": {
    period: "range",
    de: `**Formel**
Austritte ÷ durchschnittlicher Personalbestand.
- **Austritte** = Anzahl Mitarbeiter mit \`termination_date\` im Zeitraum.
- **Ø Bestand** = für jeden Kalendertag des Zeitraums die Zahl der aktiven Mitarbeiter (Eintritt ≤ Tag, kein Austritt ≤ Tag), Summe ÷ Anzahl Tage.

**Daten**
\`personio_employees\` (\`hire_date\`, \`termination_date\`).

**Sonderfälle**
Ø Bestand = 0 → „—". Der Wert ist **nicht annualisiert**: ein Monatsfenster ergibt die Monatsquote.`,
    en: `**Formula**
Leavers ÷ average headcount.
- **Leavers** = number of employees with \`termination_date\` in the period.
- **Average headcount** = for every calendar day in the period the number of active employees (hire ≤ day, no termination ≤ day), sum ÷ number of days.

**Data**
\`personio_employees\` (\`hire_date\`, \`termination_date\`).

**Edge cases**
Average headcount = 0 → "—". The value is **not annualised**: a one-month window yields the monthly rate.`,
  },
  "hr.skill_development": {
    period: "range",
    de: `**Formel**
Stichtag = Ende des Zeitraums. Anteil der aktiven Mitarbeiter, bei denen mindestens eines der konfigurierten Kompetenz-Attribute gefüllt ist: \`skilled ÷ headcount\`.

**Daten**
\`personio_employees.raw_json.attributes.<key>.value\` für jeden Key aus der Einstellung „Kompetenz-Attribute".

**Filter**
Ohne konfigurierte Keys zeigt die Kachel „—".

**Sonderfälle**
Keine aktiven Mitarbeiter → „—". Vorperiode/Vorjahr sind Stichtagswerte mit den **heutigen** Stammdaten (keine Historie), deshalb gibt es keinen Verlauf.`,
    en: `**Formula**
Reference date = end of the period. Share of active employees with at least one configured skill attribute filled: \`skilled ÷ headcount\`.

**Data**
\`personio_employees.raw_json.attributes.<key>.value\` for every key from the "skill attributes" setting.

**Filters**
Without configured keys the tile shows "—".

**Edge cases**
No active employees → "—". Previous period/year are point-in-time values using **today's** master data (no history), hence no trend chart.`,
  },
  "hr.revenue_per_employee": {
    period: "range",
    de: `**Formel**
Umsatz ÷ Kopfzahl Produktion.
- **Umsatz** = \`SUM(auftraege.wert_eur)\` mit Wert > 0 im Zeitraum (Auftragswert, nicht Rechnungsumsatz).
- **Kopfzahl** = aktive Mitarbeiter am Zeitraumende, deren \`department\` in der Einstellung „Produktionsabteilungen" steht.

**Daten**
\`auftraege\`, \`personio_employees\`.

**Sonderfälle**
Umsatz ≤ 0 oder Kopfzahl 0 → „—". Ohne konfigurierte Produktionsabteilungen „—" mit Link zu den Einstellungen.`,
    en: `**Formula**
Revenue ÷ production headcount.
- **Revenue** = \`SUM(auftraege.wert_eur)\` with value > 0 in the period (order value, not invoiced revenue).
- **Headcount** = active employees at the end of the period whose \`department\` is listed in the "production departments" setting.

**Data**
\`auftraege\`, \`personio_employees\`.

**Edge cases**
Revenue ≤ 0 or headcount 0 → "—". Without configured production departments "—" with a link to settings.`,
  },
  "hr.employee_overtime": {
    period: "range",
    de: `**Formel** (je Mitarbeiter)
- **Ist-Std.** = Σ \`(Ende − Start − Pause) ÷ 60\` über die Anwesenheiten im Zeitraum.
- **Überstunden** = Σ \`max(0, worked − daily_quota)\` mit \`daily_quota = weekly_working_hours ÷ 5\`, **Fallback 8 h** wenn keine Wochenstunden hinterlegt sind.
- **ÜS %** = Überstunden ÷ Ist-Std., nur wenn beide > 0, sonst „—".

**Daten**
\`personio_attendance\`, \`personio_employees\`.

**Filter**
Nur Mitarbeiter mit Anwesenheit im Zeitraum; Standard-Filter „Mit Überstunden", Sortierung nach Überstunden absteigend.

**Sonderfälle**
Gerechnet je Anwesenheitszeile, nicht je Tag (Segmente pro Tag ziehen das Tagessoll mehrfach ab).`,
    en: `**Formula** (per employee)
- **Hours** = Σ \`(end − start − break) ÷ 60\` over attendances in the period.
- **Overtime** = Σ \`max(0, worked − daily_quota)\` with \`daily_quota = weekly_working_hours ÷ 5\`, **fallback 8 h** if no weekly hours are stored.
- **OT %** = overtime ÷ hours, only if both > 0, otherwise "—".

**Data**
\`personio_attendance\`, \`personio_employees\`.

**Filters**
Only employees with attendance in the period; default filter "With overtime", sorted by overtime descending.

**Edge cases**
Computed per attendance row, not per day (several segments per day subtract the daily quota several times).`,
  },
  "hr.weekly_saldo": {
    period: "none",
    de: `**Formel**
Summe über alle Mitarbeiter von \`Ist − effektives Wochensoll\` für die gewählte ISO-Kalenderwoche (Mo–So).
1. **Ist** je Mitarbeiter und Tag summiert (Personio liefert Vor-/Nachmittag getrennt), nur Tage mit Tagessoll > 0.
2. **Tagessoll** aus dem Personio-Arbeitszeitmodell (\`work_schedule\`, \`HH:MM\` je Wochentag). Fehlt es: \`weekly_working_hours ÷ 5\`, Fallback 8 h.
3. **Entschuldigt**: alle Abwesenheiten (Urlaub, Krank, Freizeitausgleich …) werden proportional zum Tagessoll auf ihre Solltage verteilt.
4. **Effektives Soll** = Σ \`max(0, Tagessoll − entschuldigt)\` bis zur Grenze: in der **laufenden Woche** nur bis zum letzten gestempelten Tag des Mitarbeiters, in **abgeschlossenen Wochen** bis Sonntag.

**Daten**
\`personio_attendance\`, \`personio_absences\`, \`personio_employees.raw_json\`.

**Sonderfälle**
Nur Mitarbeiter mit mindestens einer Anwesenheit in der Woche zählen. Feiertage ohne Personio-Abwesenheit erscheinen in abgeschlossenen Wochen als Fehlstunden.`,
    en: `**Formula**
Sum over all employees of \`actual − effective weekly target\` for the selected ISO week (Mon–Sun).
1. **Actual** summed per employee and day (Personio delivers morning/afternoon separately), only days with a daily target > 0.
2. **Daily target** from the Personio work schedule (\`work_schedule\`, \`HH:MM\` per weekday). If missing: \`weekly_working_hours ÷ 5\`, fallback 8 h.
3. **Excused**: all absences (vacation, sick leave, time off in lieu …) are spread over their scheduled days in proportion to the daily target.
4. **Effective target** = Σ \`max(0, daily target − excused)\` up to the cut-off: in the **current week** only up to the employee's last recorded day, in **closed weeks** up to Sunday.

**Data**
\`personio_attendance\`, \`personio_absences\`, \`personio_employees.raw_json\`.

**Edge cases**
Only employees with at least one attendance in the week count. Public holidays without a Personio absence appear as missing hours in closed weeks.`,
  },
  "hr.weekly_ueberstunden": {
    period: "none",
    de: `**Formel**
Je Mitarbeiter \`max(0, Ist − effektives Wochensoll)\` (Rechenweg wie beim Saldo). Angezeigt werden die Top 5 mit mehr als 0,01 h, absteigend.

**Sonderfälle**
Wer unter dem Wochensoll bleibt, erscheint nicht in der Liste.`,
    en: `**Formula**
Per employee \`max(0, actual − effective weekly target)\` (same calculation as the balance). The top 5 above 0.01 h are shown, descending.

**Edge cases**
Anyone below the weekly target does not appear in the list.`,
  },
  "hr.weekly_krankheit": {
    period: "none",
    de: `**Formel**
Abwesenheiten mit Krank-Typ, die die Woche überlappen, anteilig nach **Kalendertagen**:
- \`spanne\` = Kalendertage der Abwesenheit, \`ueberlapp\` = davon in der Woche.
- **Tage** = \`days_count\` aus Personio (halbe Tage = 0,5; Fallback \`hours ÷ 8\`) × ueberlapp ÷ spanne.
- **Stunden** = \`hours\` × ueberlapp ÷ spanne.
Summe über alle Mitarbeiter, 2 Nachkommastellen.

**Daten**
\`personio_absences\`, Krank-Typ-IDs aus den Einstellungen (Fallback 568234, 3270500).

**Sonderfälle**
Anders als die entschuldigten Stunden im Saldo (Verteilung über Solltage) wird hier über Kalendertage verteilt.`,
    en: `**Formula**
Sick-leave absences overlapping the week, pro-rated by **calendar days**:
- \`span\` = calendar days of the absence, \`overlap\` = those inside the week.
- **Days** = \`days_count\` from Personio (half days = 0.5; fallback \`hours ÷ 8\`) × overlap ÷ span.
- **Hours** = \`hours\` × overlap ÷ span.
Sum over all employees, 2 decimals.

**Data**
\`personio_absences\`, sick-leave type IDs from settings (fallback 568234, 3270500).

**Edge cases**
Unlike the excused hours in the balance (spread over scheduled days), this spreads over calendar days.`,
  },
  "hr.weekly_krankheit_personen": {
    period: "none",
    de: `**Formel**
Je Mitarbeiter die Krankheits-Tage und -Stunden der Woche (Rechenweg wie bei „Krankheit"). Angezeigt werden die Top 5 mit Tagen oder Stunden > 0,01; die Sortierung folgt der gewählten Einheit (Tage/Std.).`,
    en: `**Formula**
Per employee the sick-leave days and hours of the week (same calculation as "Sick leave"). The top 5 with days or hours > 0.01 are shown; sorting follows the selected unit (days/hours).`,
  },
  "hr.belegschaft_geschlecht": {
    period: "none",
    de: `**Formel**
Verteilung der Mitarbeiter nach \`raw_json.attributes.gender.value\` (male → männlich, female → weiblich, diverse → divers, sonst „unbekannt"). Anzeige in ganzzahligen Prozent nach der Größter-Rest-Methode, Summe exakt 100.

**Grundmenge**
„Aktuell": alle mit \`status = active\`. Jahr/Quartal: Stichtag = \`min(Periodenende, heute)\`, aktiv = Eintritt ≤ Stichtag und kein Austritt ≤ Stichtag.

**Sonderfälle**
Es werden die **heutigen** Stammdaten der damals Beschäftigten verwendet, Personio liefert keine Historie.`,
    en: `**Formula**
Distribution of employees by \`raw_json.attributes.gender.value\` (male, female, diverse, otherwise "unknown"). Shown as integer percentages using the largest-remainder method, summing to exactly 100.

**Population**
"Current": everyone with \`status = active\`. Year/quarter: reference date = \`min(period end, today)\`, active = hired ≤ date and not terminated ≤ date.

**Edge cases**
**Today's** master data of the people employed back then is used; Personio provides no history.`,
  },
  "hr.belegschaft_beschaeftigung": {
    period: "none",
    de: `**Formel**
Einordnung je Mitarbeiter in dieser Reihenfolge:
1. \`employment_type = external\` → extern.
2. Personio-Feld mit Label „Art der Beschäftigung": enthält „geringf" → geringfügig, „teilzeit" → Teilzeit, „vollzeit" → Vollzeit.
3. Irgendein Attribut enthält „geringfügig" → geringfügig.
4. Sonst → **Vollzeit**.
Anzeige in absoluten Zahlen.

**Grundmenge**
Wie bei „Geschlecht" (aktuell oder Stichtag Jahr/Quartal).

**Sonderfälle**
Heutige Stammdaten, keine Historie.`,
    en: `**Formula**
Classification per employee in this order:
1. \`employment_type = external\` → external.
2. Personio field labelled "Art der Beschäftigung": contains "geringf" → marginal, "teilzeit" → part-time, "vollzeit" → full-time.
3. Any attribute contains "geringfügig" → marginal.
4. Otherwise → **full-time**.
Shown as absolute numbers.

**Population**
As for "Gender" (current or year/quarter reference date).

**Edge cases**
Today's master data, no history.`,
  },
  "hr.belegschaft_eintritt": {
    period: "none",
    de: `**Formel**
- **Neu** = \`hire_date\` zwischen Periodenstart und Periodenende (bzw. Stichtag).
- **Bestand** = alle anderen der Grundmenge.

„Aktuell": Periodenstart = Beginn des laufenden Quartals, Ende = heute. Jahr/Quartal: die gewählte Periode, Ende = \`min(Periodenende, heute)\`.

**Daten**
\`personio_employees.hire_date\`, \`termination_date\`.`,
    en: `**Formula**
- **New** = \`hire_date\` between period start and period end (or reference date).
- **Existing** = everyone else in the population.

"Current": period start = beginning of the current quarter, end = today. Year/quarter: the selected period, end = \`min(period end, today)\`.

**Data**
\`personio_employees.hire_date\`, \`termination_date\`.`,
  },
  "hr.belegschaft_abteilungen": {
    period: "none",
    de: `**Formel**
Anzahl Mitarbeiter je \`department\` der Grundmenge, absteigend sortiert. Leere Abteilung → „Sonstige".

**Sonderfälle**
Heutige Abteilungszuordnung, keine Historie.`,
    en: `**Formula**
Number of employees per \`department\` of the population, sorted descending. Empty department → "Sonstige".

**Edge cases**
Today's department assignment, no history.`,
  },

  // ---------------------------------------------------------------- Qualität
  "quality.audit_findings_l1": {
    period: "range",
    de: `**Formel**
\`COUNT(*)\` der 8D-Berichte mit Level 1 im Zeitraum. Reine Anzahl, keine Mengen, keine Quote.

**Daten**
Tabelle \`quality_records\` aus dem Upload \`8D.txt\`. Level aus der Spalte „Artikel": Text \`Major … Level 1\` → Level 1.

**Filter**
Nur Audit-Arten \`BH AUD\`, \`EX AUD\`, \`IN AUD\`, \`KU AUD\` (über den Filter wählbar). Zeilen mit „gelöscht = J" werden beim Upload verworfen.

**Ziel**
\`target_audit_findings_level1\`, Standard 0.

**Sonderfälle**
Berichte ohne erkennbares Level zählen nicht, erscheinen aber in der Tabelle.`,
    en: `**Formula**
\`COUNT(*)\` of 8D reports with level 1 in the period. A plain count, no quantities, no ratio.

**Data**
Table \`quality_records\` from the \`8D.txt\` upload. Level from the "Artikel" column: text \`Major … Level 1\` → level 1.

**Filters**
Only audit types \`BH AUD\`, \`EX AUD\`, \`IN AUD\`, \`KU AUD\` (selectable via the filter). Rows with "gelöscht = J" are dropped on upload.

**Target**
\`target_audit_findings_level1\`, default 0.

**Edge cases**
Reports without a recognisable level do not count but appear in the table.`,
  },
  "quality.audit_findings_l2": {
    period: "range",
    de: `**Formel**
\`COUNT(*)\` der 8D-Berichte mit Level 2 im Zeitraum. Reine Anzahl.

**Daten**
Tabelle \`quality_records\` aus dem Upload \`8D.txt\`. Level aus der Spalte „Artikel": Text \`Minor … Level 2\` → Level 2.

**Filter**
Nur Audit-Arten \`BH AUD\`, \`EX AUD\`, \`IN AUD\`, \`KU AUD\`.

**Ziel**
\`target_audit_findings_level2\`, Standard 5.

**Sonderfälle**
Berichte ohne erkennbares Level zählen nicht, erscheinen aber in der Tabelle.`,
    en: `**Formula**
\`COUNT(*)\` of 8D reports with level 2 in the period. A plain count.

**Data**
Table \`quality_records\` from the \`8D.txt\` upload. Level from the "Artikel" column: text \`Minor … Level 2\` → level 2.

**Filters**
Only audit types \`BH AUD\`, \`EX AUD\`, \`IN AUD\`, \`KU AUD\`.

**Target**
\`target_audit_findings_level2\`, default 5.

**Edge cases**
Reports without a recognisable level do not count but appear in the table.`,
  },
  "quality.complaint_customer": {
    period: "range",
    de: `**Formel**
On Quality = \`1 − Fehlerquote\`, Fehlerquote = reklamierte Menge ÷ gelieferte Menge.
- **Zähler** = \`SUM(Menge)\` der 8D-Berichte mit Art \`KUNRE\` oder \`KUN RE\` im Zeitraum (nach Berichtsdatum). Mengenspalte je Umschalter: „Menge" oder „akzeptierte Menge".
- **Nenner** = \`SUM(quantity)\` der Lieferscheine (\`AswKpf_LS\`, nur Typ LS) im Zeitraum (nach Lieferdatum).

**Daten**
\`quality_records\`, \`delivery_records\`.

**Ziel**
\`target_complaint_rate_customer\` als Fehlerquote (Standard 2 %); Soll-Linie = 1 − Ziel.

**Sonderfälle**
Gelieferte Menge ≤ 0 → „—". Kein Level- oder Statusfilter. Berichts- und Lieferdatum sind verschiedene Felder, eine Reklamation kann in einem anderen Monat liegen als die Lieferung. Die Deltas werden im On-Quality-Raum gerechnet (grün = besser).`,
    en: `**Formula**
On quality = \`1 − defect rate\`, defect rate = complained quantity ÷ delivered quantity.
- **Numerator** = \`SUM(quantity)\` of 8D reports with type \`KUNRE\` or \`KUN RE\` in the period (by report date). Quantity column per toggle: "Menge" or "akzeptierte Menge".
- **Denominator** = \`SUM(quantity)\` of delivery notes (\`AswKpf_LS\`, type LS only) in the period (by delivery date).

**Data**
\`quality_records\`, \`delivery_records\`.

**Target**
\`target_complaint_rate_customer\` as defect rate (default 2 %); target line = 1 − target.

**Edge cases**
Delivered quantity ≤ 0 → "—". No level or status filter. Report date and delivery date are different fields, so a complaint can fall into a different month than the delivery. Deltas are computed in on-quality space (green = better).`,
  },
  "quality.complaint_internal": {
    period: "range",
    de: `**Formel**
On Quality = \`1 − Fehlerquote\`, Fehlerquote = interne Reklamationsmenge ÷ gelieferte Menge.
- **Zähler** = \`SUM(Menge)\` der 8D-Berichte mit Art \`INT RE\` oder \`INRE\` im Zeitraum.
- **Nenner** = \`SUM(quantity)\` der **Kundenlieferungen** (\`delivery_records\`) im Zeitraum, bewusst dieselbe Bezugsmenge wie bei Kunde.

**Ziel**
\`target_complaint_rate_internal\` (Standard 4 %); Soll-Linie = 1 − Ziel.

**Sonderfälle**
Gelieferte Menge ≤ 0 → „—". Ob \`INRE\` fachlich dasselbe wie \`INT RE\` ist, ist im Code als Annahme markiert.`,
    en: `**Formula**
On quality = \`1 − defect rate\`, defect rate = internal complaint quantity ÷ delivered quantity.
- **Numerator** = \`SUM(quantity)\` of 8D reports with type \`INT RE\` or \`INRE\` in the period.
- **Denominator** = \`SUM(quantity)\` of **customer deliveries** (\`delivery_records\`) in the period, deliberately the same base as for customer complaints.

**Target**
\`target_complaint_rate_internal\` (default 4 %); target line = 1 − target.

**Edge cases**
Delivered quantity ≤ 0 → "—". Whether \`INRE\` means the same as \`INT RE\` is marked as an assumption in the code.`,
  },
  "quality.complaint_supplier": {
    period: "range",
    de: `**Formel**
On Quality = \`1 − Fehlerquote\`, Fehlerquote = Lieferantenreklamationsmenge ÷ Wareneingangsmenge Material.
- **Zähler** = \`SUM(Menge)\` der 8D-Berichte mit Art \`LIE RE\` oder \`LIERE\` im Zeitraum.
- **Nenner** = \`SUM(quantity)\` der Wareneingänge (\`AswKpf_WE\`, Typ WE) im Zeitraum, deren Warengruppe **nicht** \`DIENST\`/\`SERVIC\` ist (leere Warengruppe zählt als Material).

**Daten**
\`quality_records\`, \`goods_receipt_records\`.

**Ziel**
\`target_complaint_rate_supplier\` (Standard 2 %); Soll-Linie = 1 − Ziel.

**Sonderfälle**
Wareneingangsmenge ≤ 0 → „—".`,
    en: `**Formula**
On quality = \`1 − defect rate\`, defect rate = supplier complaint quantity ÷ material goods-receipt quantity.
- **Numerator** = \`SUM(quantity)\` of 8D reports with type \`LIE RE\` or \`LIERE\` in the period.
- **Denominator** = \`SUM(quantity)\` of goods receipts (\`AswKpf_WE\`, type WE) in the period whose material group is **not** \`DIENST\`/\`SERVIC\` (empty group counts as material).

**Data**
\`quality_records\`, \`goods_receipt_records\`.

**Target**
\`target_complaint_rate_supplier\` (default 2 %); target line = 1 − target.

**Edge cases**
Goods-receipt quantity ≤ 0 → "—".`,
  },
  "quality.complaint_subcontractor": {
    period: "range",
    de: `**Formel**
On Quality = \`1 − Fehlerquote\`, Fehlerquote = Unterauftragnehmer-Reklamationsmenge ÷ Wareneingangsmenge Fremdleistung.
- **Zähler** = \`SUM(Menge)\` der 8D-Berichte mit Art \`UA RE\` oder \`UARE\` im Zeitraum.
- **Nenner** = \`SUM(quantity)\` der Wareneingänge im Zeitraum mit Warengruppe \`DIENST\` oder \`SERVIC\`.

**Daten**
\`quality_records\`, \`goods_receipt_records\`.

**Ziel**
\`target_complaint_rate_subcontractor\` (Standard 5 %); Soll-Linie = 1 − Ziel.

**Sonderfälle**
Wareneingangsmenge ≤ 0 → „—". Wareneingänge ohne Warengruppe zählen hier nicht.`,
    en: `**Formula**
On quality = \`1 − defect rate\`, defect rate = subcontractor complaint quantity ÷ external-service goods-receipt quantity.
- **Numerator** = \`SUM(quantity)\` of 8D reports with type \`UA RE\` or \`UARE\` in the period.
- **Denominator** = \`SUM(quantity)\` of goods receipts in the period with material group \`DIENST\` or \`SERVIC\`.

**Data**
\`quality_records\`, \`goods_receipt_records\`.

**Target**
\`target_complaint_rate_subcontractor\` (default 5 %); target line = 1 − target.

**Edge cases**
Goods-receipt quantity ≤ 0 → "—". Goods receipts without a material group do not count here.`,
  },
  "quality.delivered_qty": {
    period: "range",
    de: `**Formel**
Der Nenner der On-Quality-Quote, unverändert:
- Kunde / intern: \`SUM(quantity)\` der Lieferscheine (\`delivery_records\`, Typ LS) im Zeitraum nach Lieferdatum.
- Material Lieferanten: \`SUM(quantity)\` der Wareneingänge ohne Warengruppe \`DIENST\`/\`SERVIC\`.
- Werkbänke: \`SUM(quantity)\` der Wareneingänge mit Warengruppe \`DIENST\`/\`SERVIC\`.

**Sonderfälle**
\`NULL\`-Mengen zählen als 0.`,
    en: `**Formula**
The denominator of the on-quality ratio, unchanged:
- Customer / internal: \`SUM(quantity)\` of delivery notes (\`delivery_records\`, type LS) in the period by delivery date.
- Material suppliers: \`SUM(quantity)\` of goods receipts without material group \`DIENST\`/\`SERVIC\`.
- Workbenches: \`SUM(quantity)\` of goods receipts with material group \`DIENST\`/\`SERVIC\`.

**Edge cases**
\`NULL\` quantities count as 0.`,
  },
  "quality.complaint_qty": {
    period: "range",
    de: `**Formel**
Der Zähler der On-Quality-Quote: \`SUM(Menge)\` bzw. \`SUM(akzeptierte Menge)\` (je Umschalter) der 8D-Berichte im Zeitraum, deren Art zum gewählten Reklamationstyp passt (Kunde \`KUNRE\`/\`KUN RE\`, intern \`INT RE\`/\`INRE\`, Lieferant \`LIE RE\`/\`LIERE\`, Werkbänke \`UA RE\`/\`UARE\`).

**Daten**
\`quality_records\` aus \`8D.txt\`, Datum = Berichtsdatum.

**Sonderfälle**
Kein Level- oder Statusfilter. \`NULL\`-Mengen zählen als 0.`,
    en: `**Formula**
The numerator of the on-quality ratio: \`SUM(quantity)\` or \`SUM(accepted quantity)\` (per toggle) of 8D reports in the period whose type matches the selected complaint type (customer \`KUNRE\`/\`KUN RE\`, internal \`INT RE\`/\`INRE\`, supplier \`LIE RE\`/\`LIERE\`, workbenches \`UA RE\`/\`UARE\`).

**Data**
\`quality_records\` from \`8D.txt\`, date = report date.

**Edge cases**
No level or status filter. \`NULL\` quantities count as 0.`,
  },
  "quality.inspection_large": {
    period: "range",
    de: `**Formel**
Produkte pro Tag und Prüfer:
\`round( SUM(buchungs_menge der großen Produkte) ÷ (Anzahl verschiedener Prüfer × Anzahl verschiedener Prüftage) )\`.
Der Nenner ist **gemeinsam** für groß und klein, damit Prüfer, die beides prüfen, nicht doppelt zählen.

**Daten**
\`inspection_records\` aus dem Upload \`AswQs2151.txt\`. „Groß" = alles, was nicht als klein erkannt wird (klein: Produktgruppe DIEHL, Bezeichnung mit Literature Pocket, Strap, Lederriemen, Stowage Pouch, Aufbewahrungstasche oder Net/Netz).

**Filter**
Nur Buchungen mit Kostenschlüssel \`RSC = 70000\` (echte Qualitätsprüfung) und ohne Admin-Ausschluss-Häkchen. Werkzeug-Buchungen (Typ WKZ) werden beim Upload verworfen.

**Ziel**
\`target_inspection_large\`, Standard 150.

**Sonderfälle**
Nenner 0 → **0** (nicht „—"). Rundung nach Banker's Rounding. Ein Re-Upload ersetzt alle Buchungen im Datumsbereich der Datei, gesetzte Ausschluss-Häkchen gehen dabei verloren.`,
    en: `**Formula**
Products per day and inspector:
\`round( SUM(booked quantity of large products) ÷ (number of distinct inspectors × number of distinct inspection days) )\`.
The denominator is **shared** between large and small so inspectors who do both are not counted twice.

**Data**
\`inspection_records\` from the \`AswQs2151.txt\` upload. "Large" = everything not recognised as small (small: product group DIEHL, description with Literature Pocket, Strap, Lederriemen, Stowage Pouch, Aufbewahrungstasche or Net/Netz).

**Filters**
Only bookings with cost key \`RSC = 70000\` (real quality inspection) and without the admin exclusion checkbox. Tool bookings (type WKZ) are dropped on upload.

**Target**
\`target_inspection_large\`, default 150.

**Edge cases**
Denominator 0 → **0** (not "—"). Banker's rounding. A re-upload replaces all bookings in the file's date range; exclusion checkboxes set there are lost.`,
  },
  "quality.inspection_small": {
    period: "range",
    de: `**Formel**
Produkte pro Tag und Prüfer:
\`round( SUM(buchungs_menge der kleinen Produkte) ÷ (Anzahl verschiedener Prüfer × Anzahl verschiedener Prüftage) )\`.
Derselbe gemeinsame Nenner wie bei „Große Produkte".

**Daten**
\`inspection_records\`. „Klein" = Produktgruppe DIEHL oder Bezeichnung mit Literature Pocket, Strap, Lederriemen, Stowage Pouch, Aufbewahrungstasche oder Net/Netz.

**Filter**
Nur \`RSC = 70000\`, keine ausgeschlossenen Buchungen.

**Ziel**
\`target_inspection_small\`, Standard 400.

**Sonderfälle**
Nenner 0 → 0. Banker's Rounding.`,
    en: `**Formula**
Products per day and inspector:
\`round( SUM(booked quantity of small products) ÷ (number of distinct inspectors × number of distinct inspection days) )\`.
Same shared denominator as "Large products".

**Data**
\`inspection_records\`. "Small" = product group DIEHL or description with Literature Pocket, Strap, Lederriemen, Stowage Pouch, Aufbewahrungstasche or Net/Netz.

**Filters**
Only \`RSC = 70000\`, no excluded bookings.

**Target**
\`target_inspection_small\`, default 400.

**Edge cases**
Denominator 0 → 0. Banker's rounding.`,
  },

  // ---------------------------------------------------------------- Finanzen
  "finance.material_cost_ratio": {
    period: "range",
    de: `**Formel**
Materialkosten ÷ Umsatz.
1. **Preis je Artikel**: neueste Wareneingangszeile mit Menge ≠ 0; \`unit_price = pos_wert ÷ menge\` (die Rohspalte „Preis" wird nicht genutzt, sie kann je 100/1000 Stück sein).
2. **Verbrauch je Artikel** = \`−SUM(bewegungsmenge)\` über Buchtyp M (Entnahme) und SM (Storno) im Zeitraum.
3. **Materialkosten** = Σ Verbrauch × Preis über Artikel **mit** Preis.
4. **Umsatz** = \`SUM(revenues.wert_eur)\` im Zeitraum (netto, Gutschriften negativ).

**Daten**
\`material_movements\` (\`AswLagBew.txt\`), \`material_prices\` (\`AswKpf_WE.txt\`), \`revenues\`.

**Ziel**
\`target_material_cost_ratio\` (in den Einstellungen in Prozent).

**Sonderfälle**
Umsatz ≤ 0 → „—". Artikel ohne Preis werden nicht mit 0 bewertet, sondern ausgelassen (siehe Kachel „Ohne Preis"). Vorperiode/Vorjahr nutzen die heutige Preisliste. Mehr Storno als Entnahme ergibt negative Kosten.`,
    en: `**Formula**
Material cost ÷ revenue.
1. **Price per article**: latest goods-receipt row with quantity ≠ 0; \`unit_price = pos_wert ÷ menge\` (the raw "Preis" column is not used, it may be per 100/1000 units).
2. **Consumption per article** = \`−SUM(bewegungsmenge)\` over booking types M (withdrawal) and SM (reversal) in the period.
3. **Material cost** = Σ consumption × price over articles **with** a price.
4. **Revenue** = \`SUM(revenues.wert_eur)\` in the period (net, credit notes negative).

**Data**
\`material_movements\` (\`AswLagBew.txt\`), \`material_prices\` (\`AswKpf_WE.txt\`), \`revenues\`.

**Target**
\`target_material_cost_ratio\` (entered as percent in settings).

**Edge cases**
Revenue ≤ 0 → "—". Articles without a price are not valued at 0 but left out (see the "Without price" tile). Previous period/year use today's price list. More reversals than withdrawals yield negative cost.`,
  },
  "finance.material_cost": {
    period: "range",
    de: `**Formel**
Zähler der Materialkostenquote: Σ (Nettoverbrauch × Stückpreis) über alle Artikel mit Preis im Zeitraum.
- Nettoverbrauch = \`−SUM(bewegungsmenge)\` über Buchtyp M und SM.
- Stückpreis = \`pos_wert ÷ menge\` der neuesten Wareneingangszeile des Artikels.

**Daten**
\`material_movements\`, \`material_prices\`.

**Sonderfälle**
Artikel ohne Preis fehlen in der Summe. Mehr Storno als Entnahme ergibt negative Kosten.`,
    en: `**Formula**
Numerator of the material cost ratio: Σ (net consumption × unit price) over all articles with a price in the period.
- Net consumption = \`−SUM(bewegungsmenge)\` over booking types M and SM.
- Unit price = \`pos_wert ÷ menge\` of the article's latest goods-receipt row.

**Data**
\`material_movements\`, \`material_prices\`.

**Edge cases**
Articles without a price are missing from the sum. More reversals than withdrawals yield negative cost.`,
  },
  "finance.revenue": {
    period: "range",
    de: `**Formel**
Nenner der Kostenquoten: \`SUM(wert_eur)\` aller Rechnungen im Zeitraum.

**Daten**
Tabelle \`revenues\` aus \`AswKpf_RG.txt\` (RG + GS). Gutschriften sind negativ gespeichert, die Summe ist der Netto-Umsatz. Derselbe Wert wie die Kachel „Umsatz" im Vertriebs-Dashboard.

**Sonderfälle**
Umsatz ≤ 0 → die Quote zeigt „—".`,
    en: `**Formula**
Denominator of the cost ratios: \`SUM(wert_eur)\` of all invoices in the period.

**Data**
Table \`revenues\` from \`AswKpf_RG.txt\` (RG + GS). Credit notes are stored negative, so the sum is net revenue. Same value as the "Revenue" tile on the sales dashboard.

**Edge cases**
Revenue ≤ 0 → the ratio shows "—".`,
  },
  "finance.unmatched": {
    period: "range",
    de: `**Formel**
Anzahl der Artikel mit Nettoverbrauch im Zeitraum, für die keine Preiszeile im Wareneingang gefunden wurde.

**Bedeutung**
Diese Artikel fehlen in den Materialkosten komplett (sie werden nicht mit 0 bewertet). Je höher die Zahl, desto unvollständiger der Zähler der Quote. Die Prüftabelle listet sie mit leerem Preis am Ende.`,
    en: `**Formula**
Number of articles with net consumption in the period for which no goods-receipt price row was found.

**Meaning**
These articles are entirely missing from material cost (they are not valued at 0). The higher the number, the less complete the numerator of the ratio. The audit table lists them with an empty price at the end.`,
  },
  "finance.personnel_cost_ratio": {
    period: "range",
    de: `**Formel**
Personalkosten ÷ Umsatz.
- **Festgehalt** (\`fix_salary\` > 0, Monatsbrutto): je Kalendermonat anteilig nach aktiven Tagen im Zeitraum (Eintritt/Austritt berücksichtigt), voller Monat = ein Monatsgehalt.
- **Stundenlohn** (kein Festgehalt, \`hourly_salary\` > 0): Stundensatz × Ist-Stunden aus den Anwesenheiten im Zeitraum.
- **Umsatz** = \`SUM(revenues.wert_eur)\` im Zeitraum.

**Daten**
Gehälter aus \`personio_employees.raw_json\` (aktueller Stand, keine Gehaltshistorie), \`personio_attendance\`, \`revenues\`.

**Ziel**
\`target_personnel_cost_ratio\`.

**Sonderfälle**
Umsatz ≤ 0 → „—". Brutto ohne Arbeitgeber-Nebenkosten. Mitarbeiter ohne Gehaltsangabe tragen nichts bei. Einzelgehälter werden nie angezeigt, nur Abteilungssummen.`,
    en: `**Formula**
Personnel cost ÷ revenue.
- **Fixed salary** (\`fix_salary\` > 0, monthly gross): per calendar month pro-rated by active days in the period (hire/termination respected), a full month = one monthly salary.
- **Hourly wage** (no fixed salary, \`hourly_salary\` > 0): hourly rate × actual hours from attendances in the period.
- **Revenue** = \`SUM(revenues.wert_eur)\` in the period.

**Data**
Salaries from \`personio_employees.raw_json\` (current snapshot, no salary history), \`personio_attendance\`, \`revenues\`.

**Target**
\`target_personnel_cost_ratio\`.

**Edge cases**
Revenue ≤ 0 → "—". Gross without employer on-costs. Employees without salary data contribute nothing. Individual salaries are never shown, only department totals.`,
  },
  "finance.personnel_cost": {
    period: "range",
    de: `**Formel**
Zähler der Personalkostenquote: Σ über alle Mitarbeiter von
- Festgehalt anteilig nach aktiven Tagen je Kalendermonat im Zeitraum, oder
- Stundensatz × Ist-Stunden im Zeitraum (nur wenn kein Festgehalt).

**Daten**
Gehaltsfelder aus dem aktuellen Personio-Stand, \`personio_attendance\`.

**Sonderfälle**
Brutto ohne Arbeitgeber-Nebenkosten. Wer weder Festgehalt noch Stundensatz hat, fehlt in der Summe.`,
    en: `**Formula**
Numerator of the personnel cost ratio: Σ over all employees of
- fixed salary pro-rated by active days per calendar month in the period, or
- hourly rate × actual hours in the period (only without a fixed salary).

**Data**
Salary fields from the current Personio snapshot, \`personio_attendance\`.

**Edge cases**
Gross without employer on-costs. Anyone without fixed salary or hourly rate is missing from the sum.`,
  },
  "finance.headcount": {
    period: "range",
    de: `**Formel**
Anzahl der Mitarbeiter, die im Zeitraum Personalkosten > 0 beitragen (Festgehalt oder Stundensatz × Stunden).

**Sonderfälle**
Mitarbeiter ohne Gehaltsangabe oder Stundenlöhner ohne Anwesenheit im Zeitraum zählen nicht mit. Das ist deshalb keine Kopfzahl der Belegschaft.`,
    en: `**Formula**
Number of employees contributing personnel cost > 0 in the period (fixed salary or hourly rate × hours).

**Edge cases**
Employees without salary data or hourly workers without attendance in the period are not counted. This is therefore not a workforce headcount.`,
  },

  // ----------------------------------------------------------------- Einkauf
  "procurement.otd": {
    period: "range",
    de: `**Formel**
Pünktliche Positionen ÷ alle Positionen.
- Zeitraum über das **Ist-Lieferdatum** („geliefert").
- Pünktlich = \`Verzug (Tage) ≤ 0\` (Toleranz 0 Tage, frühe Lieferung zählt als pünktlich).
- Gezählt wird je Bestellposition, nicht nach Menge.

**Daten**
\`delivery_reliability\` aus dem Upload \`dev_excel_Liefertreue_Einkauf.txt\` (Upsert auf Auftrag/Pos/UPos).

**Ziel**
Fest 98 % (nicht konfigurierbar).

**Sonderfälle**
Keine Positionen → „—". Positionen ohne Verzugswert zählen im Nenner, nie im Zähler. Keine Storno- oder Teillieferungslogik. Keine Gruppierung nach Lieferant.`,
    en: `**Formula**
Punctual positions ÷ all positions.
- Period by the **actual delivery date** ("geliefert").
- Punctual = \`delay (days) ≤ 0\` (tolerance 0 days, early delivery counts as punctual).
- Counted per order position, not by quantity.

**Data**
\`delivery_reliability\` from the \`dev_excel_Liefertreue_Einkauf.txt\` upload (upsert on order/pos/sub-pos).

**Target**
Fixed 98 % (not configurable).

**Edge cases**
No positions → "—". Positions without a delay value count in the denominator, never in the numerator. No cancellation or partial-delivery logic. No grouping by supplier.`,
  },
  "procurement.punctual_count": {
    period: "range",
    de: `**Formel**
\`COUNT\` der Bestellpositionen mit Ist-Lieferdatum im Zeitraum und \`Verzug (Tage) ≤ 0\`. Zähler der OTD-Quote.

**Daten**
\`delivery_reliability\`.`,
    en: `**Formula**
\`COUNT\` of order positions with actual delivery date in the period and \`delay (days) ≤ 0\`. Numerator of the OTD ratio.

**Data**
\`delivery_reliability\`.`,
  },
  "procurement.total_count": {
    period: "range",
    de: `**Formel**
\`COUNT\` aller Bestellpositionen mit Ist-Lieferdatum im Zeitraum. Nenner der OTD-Quote.

**Sonderfälle**
Positionen ohne Verzugswert zählen hier mit, können aber nie pünktlich sein.`,
    en: `**Formula**
\`COUNT\` of all order positions with actual delivery date in the period. Denominator of the OTD ratio.

**Edge cases**
Positions without a delay value count here but can never be punctual.`,
  },
  "procurement.avg_delay": {
    period: "range",
    de: `**Formel**
\`SUM(Verzug Tage) ÷ COUNT(Verzug Tage)\` über alle Positionen im Zeitraum. Frühe Lieferungen gehen negativ ein, der Mittelwert kann negativ sein.

**Sonderfälle**
Positionen ohne Verzugswert werden nicht mitgezählt. Keine Werte → „—".`,
    en: `**Formula**
\`SUM(delay days) ÷ COUNT(delay days)\` over all positions in the period. Early deliveries enter negative, so the mean can be negative.

**Edge cases**
Positions without a delay value are not counted. No values → "—".`,
  },
  "procurement.stock_orders": {
    period: "none",
    de: `**Formel**
1. Lagerartikel = Artikelnummer beginnt mit \`L\`.
2. Bestand je Artikel = \`SUM(bewegungsmenge)\` über **alle** hochgeladenen Bewegungen (kein Zeit-, kein Buchtyp-Filter); letzte Bewegung = \`MAX(buch_datum)\`.
3. Ladenhüter = letzte Bewegung älter als 28 Tage **und** Bestand > 0.
4. Wert = Bestand × Stückpreis (\`Wert ÷ Preismenge\` aus der Lagerpreisliste, erste Zeile je Artikel).
5. Top 20 nach Wert; „Gebundenes Kapital" = Summe der 20 angezeigten Zeilen.

**Daten**
\`material_movements\` (\`AswLagBew.txt\`), \`stock_article_prices\` (Preisliste, kompletter Ersatz je Upload).

**Zeitraum**
Der Dashboard-Zeitraum wird **ignoriert**, Stichtag ist immer heute.

**Sonderfälle**
Artikel ohne Preiszeile fallen ohne Hinweis heraus. Der Bestand ist nur so vollständig wie die hochgeladene Bewegungshistorie.`,
    en: `**Formula**
1. Stock article = article number starts with \`L\`.
2. Stock per article = \`SUM(bewegungsmenge)\` over **all** uploaded movements (no time or booking-type filter); last movement = \`MAX(buch_datum)\`.
3. Slow mover = last movement older than 28 days **and** stock > 0.
4. Value = stock × unit price (\`Wert ÷ Preismenge\` from the stock price list, first row per article).
5. Top 20 by value; "tied-up capital" = sum of the 20 rows shown.

**Data**
\`material_movements\` (\`AswLagBew.txt\`), \`stock_article_prices\` (price list, fully replaced per upload).

**Period**
The dashboard date range is **ignored**; the reference date is always today.

**Edge cases**
Articles without a price row drop out silently. Stock is only as complete as the uploaded movement history.`,
  },

  // -------------------------------------------------------------- Produktion
  "production.verzug": {
    period: "range",
    de: `**Formel**
Aufträge in Verzug ÷ gezählte Aufträge.
1. **Zieltermin** je Auftrag = \`MAX(lieferdatum)\` der Auftragspositionen.
2. **Ist** je Auftrag = \`MAX(delivery_date)\` der Lieferscheinzeilen mit passender Auftragsnummer.
3. \`delay = (Ist oder heute) − Ziel\` in Tagen.
4. **Gezählt** wird ein Auftrag nur, wenn sein Ausgang feststeht: geliefert **oder** Ziel < heute. Noch nicht fällige offene Aufträge fehlen in Zähler und Nenner.
5. Zeitraum über den **Zieltermin**. In Verzug = \`delay > 0\` (zu spät geliefert plus überfällig offen).

**Daten**
\`auftrag_positionen\` (\`AswKpf_AUF.txt\`, Positionsebene), \`delivery_records\` (\`AswKpf_LS.xlsx\`).

**Ziel**
\`target_produktion_verzug\` („Max. Verzugsquote" in Prozent).

**Sonderfälle**
Keine gezählten Aufträge → „—". Der Seriengeschäft-Filter (Pos-Typ 2) ist vorbereitet, aber leer: es zählen alle Aufträge. Eine frühe Teillieferung macht den Auftrag zu „geliefert". Beim Preset „Gesamt" wird der laufende Monat genommen. Das Delta wird über die Termintreue (1 − Quote) gerechnet, grün = weniger Verzug.`,
    en: `**Formula**
Orders in delay ÷ counted orders.
1. **Target date** per order = \`MAX(lieferdatum)\` of the order positions.
2. **Actual** per order = \`MAX(delivery_date)\` of delivery-note rows with the matching order number.
3. \`delay = (actual or today) − target\` in days.
4. An order is **counted** only once its outcome is known: delivered **or** target < today. Open orders not yet due are missing from numerator and denominator.
5. Period by **target date**. In delay = \`delay > 0\` (delivered late plus overdue open).

**Data**
\`auftrag_positionen\` (\`AswKpf_AUF.txt\`, position level), \`delivery_records\` (\`AswKpf_LS.xlsx\`).

**Target**
\`target_produktion_verzug\` ("max. delay rate" in percent).

**Edge cases**
No counted orders → "—". The series-business filter (pos type 2) is prepared but empty: all orders count. An early partial delivery marks the order as "delivered". The "All time" preset falls back to the current month. The delta is computed on on-time performance (1 − rate), green = less delay.`,
  },
  "production.in_verzug_count": {
    period: "range",
    de: `**Formel**
\`COUNT\` der gezählten Aufträge mit Zieltermin im Zeitraum und \`delay > 0\`. Umfasst zu spät gelieferte **und** überfällig offene Aufträge (die beiden Tabellen darunter).

**Sonderfälle**
Überfällig offene Aufträge bleiben hier, bis ein Lieferschein vorliegt. Bei leerem Zeitraum zeigt die Kachel 0.`,
    en: `**Formula**
\`COUNT\` of counted orders with target date in the period and \`delay > 0\`. Includes orders delivered late **and** overdue open orders (the two tables below).

**Edge cases**
Overdue open orders stay here until a delivery note exists. With an empty period the tile shows 0.`,
  },
  "production.total_count": {
    period: "range",
    de: `**Formel**
\`COUNT\` der Aufträge mit Zieltermin im Zeitraum, deren Ausgang feststeht (geliefert oder Ziel < heute). Nenner der Verzugsquote.

**Sonderfälle**
Nicht die Anzahl aller Aufträge des Zeitraums: noch nicht fällige offene Aufträge fehlen. Für Zeiträume, die die Gegenwart überlappen, kann der Wert morgen größer sein.`,
    en: `**Formula**
\`COUNT\` of orders with target date in the period whose outcome is known (delivered or target < today). Denominator of the delay rate.

**Edge cases**
Not the number of all orders in the period: open orders not yet due are missing. For periods overlapping the present the value can be larger tomorrow.`,
  },
  "production.avg_delay": {
    period: "range",
    de: `**Formel**
\`SUM(delay) ÷ Anzahl gezählter Aufträge\`, mit \`delay = (Ist oder heute) − Zieltermin\` in Tagen. Mittel über **alle** gezählten Aufträge, pünktliche gehen negativ ein, der Wert kann negativ sein.

**Sonderfälle**
Überfällig offene Aufträge gehen mit \`heute − Ziel\` ein, der Wert wächst dadurch täglich. Keine gezählten Aufträge → „—".`,
    en: `**Formula**
\`SUM(delay) ÷ number of counted orders\`, with \`delay = (actual or today) − target date\` in days. Mean over **all** counted orders, punctual ones enter negative, so the value can be negative.

**Edge cases**
Overdue open orders enter with \`today − target\`, so the value grows daily. No counted orders → "—".`,
  },
};

export const KPI_INFO_KEYS = Object.keys(INFO) as KpiInfoKey[];

/** Markdown body for a KPI in the given UI language ("de" or anything else → "en"). */
export function getKpiInfo(key: KpiInfoKey, language: string): string {
  const entry = INFO[key];
  const lang: "de" | "en" = language.startsWith("de") ? "de" : "en";
  const body = entry[lang];
  return entry.period === "range" ? body + COMMON_RANGE[lang] : body;
}
