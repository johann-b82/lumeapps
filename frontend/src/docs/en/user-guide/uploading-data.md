# Uploading Data

This article explains how to upload a sales data file, what happens during processing, and how to manage your upload history. Uploading data is the first step to seeing your KPIs on the Sales Dashboard.

## Before You Begin

> **Note:** The Upload page is only accessible to Admin users. If you see a "You don't have permission to access this page" message, you do not have the required role. Contact your administrator to upload the file on your behalf.

The upload page accepts `.csv` and `.txt` files only.

> **Tip:** Only `.csv` and `.txt` files are accepted. Excel files (`.xlsx`) are not supported on the upload page.

## How to Upload a File

You can add a file in two ways:

1. **Drag and drop** — Drag your file directly onto the drop zone. The border highlights and the prompt changes while you hold the file over it. Release to start the upload.

2. **Browse** — Click the **Browse** button to open a file picker. Select your `.csv` or `.txt` file and confirm.

The upload begins immediately after you drop or select the file. The drop zone shows a spinner and the text "Processing..." while the file is being imported. Do not navigate away during processing.

## Upload States

Once processing completes, you will see one of the following outcomes:

- **Success (full import)** — A toast notification appears: "File uploaded" with the message `{filename}: {count} rows imported`. All rows were imported without errors.

- **Success (partial import)** — The toast shows `{filename}: {count} rows imported, {errors} rows skipped`. Some rows contained validation errors. An error list appears below the drop zone showing each affected row, the column name, and the error message.

- **File type rejected** — An inline error message appears: "Unsupported format: `{ext}`. Only `.csv` and `.txt` allowed." No data is imported. Try converting the file to CSV first.

- **Network error** — An error toast appears with the server's error message. Check your connection and try again.

## Reading the Error List

When rows are skipped, an error list appears below the drop zone with the heading **Import errors ({{count}} rows skipped)**. Each entry shows:

- The row number
- The column that caused the error (when applicable)
- A description of the error

Use this list to correct the source file and re-upload. The previously imported rows remain in the database.

## Managing Upload History

The **Upload History** table on the right side of the page shows every file you have uploaded. Columns:

| Column | Description |
|--------|-------------|
| Filename | The original file name |
| Uploaded at | Date and time of the upload |
| Rows | Number of rows imported |
| Status | Import outcome (success, partial, error) |
| Errors | Number of rows skipped |

To delete an upload and all its associated records, click the delete icon in the row. A confirmation dialog will appear — click **Delete** to confirm or **Keep upload** to cancel.

> **Note:** Deleting an upload permanently removes all sales records that came from that file. This cannot be undone.

## Related Articles

- [Sales Dashboard](/docs/user-guide/sales-dashboard) — See your uploaded data as KPI cards and charts.
- [Filters & Date Ranges](/docs/user-guide/filters) — Learn how to narrow the dashboard view by date range.
