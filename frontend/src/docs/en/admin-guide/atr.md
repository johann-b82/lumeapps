# ATR

ATR is an admin tool that ties two things together: a **parts catalog** (master data for part numbers, names, drawings, weights) and the generation of **ATR delivery documents**. You import the catalog from Excel files, upload a delivery note, match its positions against the catalog, review the header and position data, and generate the finished output files (ATR as XLSX and PDF plus a container label as DOCX).

## Access

ATR is for the **Admin role** only. Every `/api/atr/*` endpoint is admin-gated at the router level; Viewers don't see the ATR tile in the launcher and have no access to the pages under `/atr`.

## Importing the parts catalog

Open **ATR → Import** (`/atr/import`).

1. Pick one or more `.xlsx` files and click **Preview**. Nothing is saved yet — you get a per-file summary with the counters **New**, **Updated**, and **Unchanged**, plus any **warnings**. Each part row is colored by its status.
2. Check the preview. Optionally tick two boxes:
   - **Update template** — copies the file's header data into the ATR template (see Settings).
   - **Set structure** — stores the uploaded file as the structure template.
3. Click **Commit**. Only now is anything written; the success message reports the number of parts created and updated (`+new / ~updated`).

Matching runs on a normalized part number. Existing parts are classified as "updated" or "unchanged" by comparing their value fields (name, drawing, weight, quantity, category, etc.).

## Managing parts

Under **ATR → Parts** (`/atr`) you search the catalog (part number, name, supplier article code) and see the columns Part number, Name, Category, Drawing, Weight, PO pos, and Source file. **Edit** lets you change name, drawing number, weight, and PO pos inline; **Delete** removes a part. The source shows which import file a part came from (or `(manual)`).

## Deliveries

Under **ATR → Deliveries** (`/atr/deliveries`) you start a new delivery two ways:

- **Upload delivery note** — pick a `.pdf`. The positions are read out and matched against the catalog; you land straight in the review view.
- **From folder** — only visible when the fileserver is configured. Pick a PDF from the input folder and click **Process**.

The table lists all deliveries with source file, BA order, status, and creation date. **Open** takes you to the review.

### Review and generate

In the review view (`/atr/deliveries/:id`) you edit the **header fields** (ATR number, container number, set title, PO number, weighing and testing date, QA signer, max guaranteed weight) and save them. Below are the **positions**: rows with no catalog match are highlighted red. You can enter weight and PO pos per position directly (saved when you leave the field).

**Generate** builds the output files. Warnings appear as notices. The downloads are then available: **ATR (XLSX)**, **ATR (PDF)**, and **Container label (DOCX)**.

## Template

Under **ATR → Template** (`/atr/template`) you maintain the fixed header data that flows into every ATR (customer, AC programme, work package, specifications, supplier, NSCM code, ATA chapter, weighing equipment, etc.) as well as the **default QA signer**, which is pre-filled for new deliveries automatically. You also upload the **structure file** (`.xlsx`) here, which serves as the layout template.

## Settings (fileserver)

Under **Settings → ATR** (`/settings/atr`) you configure the SMB fileserver: host, share, domain, user, and password, plus the paths for **input**, **output**, and **archive**. **Test connection** validates the credentials. The **scan interval** and **auto mode** control automatic processing. When the fileserver is configured, the "From folder" option appears on the Deliveries page, and generated files are written to the output path.
