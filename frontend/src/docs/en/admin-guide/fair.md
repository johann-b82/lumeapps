# FAIR – First Article Inspection / Drawing Ballooning

FAIR is the tool for First Article Inspection Reports: you upload a technical drawing, mark the characteristics to be inspected on it (dimensions, tolerances, notes) and FAIR numbers them automatically – classic "ballooning". Each marked characteristic is read via OCR, collected in a running value list and can finally be exported as a ballooned PDF plus a value list (CSV/Excel). Text recognition runs entirely in the browser with Tesseract.js – the language data (German + English) ships locally, so nothing is sent to external services.

## Access

FAIR is **admin-only**. The "FAIR" tile (teal-green, ruler icon) appears in the launcher for admin accounts only; the routes `/fair` and `/fair/:id` as well as all `/api/fair/*` endpoints are admin-gated. Viewers see neither the tile nor the page.

## 1. Upload a drawing

On the FAIR landing page, drag a file onto the drop zone or pick it via **Select file**. **PDF, PNG and JPG** are supported. The file is stored in Directus, a project is created and you land directly in the editor.

Existing projects are listed below, **grouped by customer** (groups are collapsible and collapsed by default). The search box filters live by name, part number, customer or article number.

## 2. Project header data

In the editor header you enter **Customer**, **Article number** and **Part number**. Fields save on blur or Enter. The part number is later used as the filename of the exported PDF.

## 3. Mark and balloon characteristics

The editor shows the drawing (PDF page or image) with zoom, pan (also via right mouse button), rotate and – for multi-page PDFs – page navigation. Balloon size can be adjusted globally; rotation and balloon size are persisted.

Workflow in the **Add** tool:

1. Drag a rectangle over the characteristic.
2. On release, **OCR** starts. The crop is recognized in all four orientations (the drag direction is preferred) and the best result is taken.
3. The recognized value appears in an **editable** input. Using the toggles you can re-run recognition specifically as **Measure** (digits/dimension characters only) or as **Text**.
4. A **click on the drawing** places the leader tip and confirms the value at the same time – the balloon is saved and numbered sequentially by the server.

**Escape** cancels an in-progress mark. Balloons can later be moved by dragging their tip.

## 4. Review and maintain the value list

To the right of the drawing, FAIR keeps a table of all balloons (No., Value; newest on top):

- **Edit value inline** – click the field; Enter/blur saves.
- **Re-recognize** (refresh icon) – re-runs OCR on that row's stored region.
- **Delete** – removes the balloon; the remaining ones are renumbered 1..n server-side.
- **Reorder by drag-and-drop** – reordering renumbers all balloons (also reflected on the drawing).
- **Copy** puts the list on the clipboard as TSV (paste straight into Excel); **CSV** downloads a file with semicolons and a BOM for German Excel.

## 5. Export the ballooned PDF

**Export** in the toolbar produces a PDF with the balloons burned in (page-faithful for multi-page PDFs). The filename follows the part number or project name: `<part-number>_ballooned.pdf`.

**Note:** OCR is an assist, not an automation – on awkward drawings it may come back empty or wrong. Manual correction is available everywhere, and you verify every value yourself.
