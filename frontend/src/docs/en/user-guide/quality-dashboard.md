# Quality Dashboard

The Quality perspective bundles three views of your quality picture: **Audits** (8D findings from audits), **Complaints** (on-quality rate and complaint lists) and **Inspection** (number of products inspected per inspector-day). Use the segmented switcher at the top left to move between the three views; matching filters appear beside it depending on the view. All three views respond to the page's date-range filter.

You reach the perspective via the **Quality** tile in the KPI dashboard (route `/quality`).

## Audits

This view counts audit findings by severity. At the top right you filter with the **Audit types** checkbox group — authority audit (BH AUD), sub-supplier audit (EX AUD), internal audit (IN AUD) and customer audit (KU AUD). All four are pre-selected; unchecking a type removes its findings from every metric.

**KPI cards:** two cards — **Audit Findings Level 1** and **Audit Findings Level 2**. Both show delta badges versus the previous period and previous year once a comparison window exists.

**Charts:** two bar charts — *Audit Findings Level 1 by category* and *Level 2 by category*. The **−** / **+** buttons switch granularity (week / month / quarter / year), and **Zoom** caps the Y-axis. If a target is set in Settings, a dashed **target** line appears.

**Findings overview (table):** one row per 8D report, searchable and sortable. Columns: No., Date, Category, Level, Issuer, Source (customer/supplier), Designation, Status (colored indicator).

## Complaints

This view shows the on-quality rate. At the top right you pick the **complaint type** — Customer, Internal, Material Suppliers or Workbenches — and use the **quantity mode** toggle to decide whether the numerator uses the full **quantity** or only the **accepted quantity**.

**KPI cards:** three cards — **On Quality** (in %, card label depends on the complaint type; the defect rate shows as a subtitle, and delta badges are computed in on-quality space), **Delivered pieces** (denominator) and **Complained pieces** or **Accepted complaint quantity** (numerator, depending on the quantity mode).

**Chart:** a single bar chart of the on-quality trend, with the same granularity and zoom buttons and an optional target line.

**Complaints list (table):** the title reflects the type (e.g. *Customer complaints*, *Supplier complaints*). Columns: No., Date, Source, Designation, Quantity, Acc. quantity, Issuer, Status.

## Inspection

This view measures how many products were inspected — normalized as **products/day/employee** (inspected quantity divided by inspectors × inspection days in the window). The data source is the ERP export **AswQs2151**: one row per inspection booking. On import, each product is automatically classified as **large** or **small** (small includes literature pockets, straps, net variants, life-vest/stowage pouches and all Diehl product groups; everything else is large). Only bookings with cost key "70000" count as a real inspection; tool rows are discarded.

**KPI cards:** **Large products (inspected)** and **Small products (inspected)**, each with the unit *products/day/employee* and delta badges.

**Charts:** two bar charts — *Large products over time* and *Small products over time* — with granularity and zoom buttons. If a target is set (default: 150 large / 400 small), a dashed target line appears.

**Inspection bookings (table):** one row per booking, filterable by class (All / Large / Small) and searchable. Columns: KPI checkbox, Date (with time), User, FA, Article, Designation, Class, Product group, Quantity, Scrap. The checkbox in the first column excludes individual mis-bookings from the KPI (excluded rows stay visible with a strikethrough, and cards and charts recompute immediately). Changing it is reserved for admins.

**Uploading data:** Inspection is fed by the file `AswQs2151.txt` (tab-separated, Windows-1252). Drop it onto the drop zone or, as an admin, pick it via **Browse**. See [Uploading data](/docs/user-guide/uploading-data) for a walkthrough.

## Date range

All three views respect the page's date-range filter. Range presets and custom ranges are explained under [Filters &amp; Date Ranges](/docs/user-guide/filters).
