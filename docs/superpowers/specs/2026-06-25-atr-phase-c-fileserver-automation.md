# ATR module — Phase C: fileserver (AD/SMB) + scheduler automation

**Date:** 2026-06-25
**Status:** approved (brainstorm)
**Driver:** Phases A+B deliver the catalog/template and the manual generate-from-Lieferschein pipeline. Phase C closes the loop from the original brief: an **automation that regularly checks an input directory on the fileserver and runs the process**, accessing the share with a **Microsoft AD service account**, and the **input/output directories are configurable**. New Lieferscheine dropped on `\\acm_file\Dateiablage\…\Test_ATR\Input` are picked up automatically and (in auto mode) produce the ATR + Containerbeschriftung in the `Output` directory.

Builds on Phase B (`feat/atr-phase-b`): the parser, matcher, `atr_delivery`/`atr_delivery_item`, the generators (`build_atr_xlsx` + `convert_xlsx_to_pdf` + `build_containerbeschriftung`), and the delivery router.

## Goal

A scheduler job that, on a configurable interval, lists new Lieferschein PDFs on an SMB share (authenticated with an AD service account configured in the Settings UI), runs the Phase B pipeline for each, and — depending on a configurable **auto/review** mode — either generates the documents and writes them to the Output directory immediately, or leaves a draft for an operator to review and generate. Processed input PDFs are moved to an Archive subfolder. All configuration (credentials, paths, interval, mode) lives on a new `/settings/atr` page.

## Decisions (locked in brainstorm)

1. **Settings-driven SMB client, not a `.env` CIFS mount.** The AD service account is entered in the Settings UI, so the app talks to the share via a Python SMB client (`smbprotocol`/`smbclient`) authenticating per-session with the settings-stored domain/user/password. No privileged container, no static docker-compose mount; credentials are Fernet-encrypted in `app_settings` (like the Personio credentials) and changeable in the UI with a **Test connection** button.
2. **Auto vs review is configurable; default = review.** Review: a scan creates a draft delivery for an operator to review/generate in the Phase B UI. Auto: the scan generates and writes immediately.
3. **Processed input is moved to an Archive subfolder** (default `…/Test_ATR/Archiv`). Auto mode archives on generate; review mode archives when the operator generates.
4. **All three files** (`.xlsx`, PDF, `.docx`) are written to the Output directory per delivery.

## Non-goals

- A `.env`/docker-compose CIFS OS-mount (explicitly replaced by the settings-driven SMB client).
- Kerberos/SSO ticket auth — the service account uses NTLM username/password (`smbprotocol` supports it). Kerberos is a possible future enhancement.
- Reprocessing/auditing UI beyond the existing Phase B deliveries list.
- Multi-share / multiple input folders — one input, one output, one archive.

## Architecture / data flow

```
/settings/atr  ──►  app_settings (host, share, domain, user, password_enc, input/output/archive paths,
                                  scan_interval_s, auto_mode)
        │
  services/atr_fileserver.py  ──smbprotocol (AD auth from settings)──►  \\acm_file\Dateiablage
        ▲
  scheduler  atr_scan  (interval job, reschedulable like sensor_poll):
     list {input}/*.pdf  →  skip names already linked to an atr_delivery  →  for each new PDF:
        read bytes → parse → match → persist draft (origin='scan', source_path=<input path>)
          ├─ auto_mode:   generate → write .xlsx+PDF+.docx to {output} → move PDF to {archive}
          └─ review_mode: stop (draft only). Operator clicks Generate in the Phase B UI →
                          (because origin='scan') write the 3 files to {output} → move PDF to {archive}
```

## Settings model

New columns on `app_settings` (singleton), migration `v1_65_atr_fileserver` (`down_revision = "v1_64_atr_delivery"` — re-verify head). Reuse the existing Fernet helper used for `personio_*_enc` / `worldcup_api_key_enc` to encrypt the password.

| Column | Type | Notes |
|--------|------|-------|
| `atr_smb_host` | `String(255)` NULL | e.g. `acm_file` (or its FQDN/IP if NetBIOS isn't resolvable from the container) |
| `atr_smb_share` | `String(255)` NULL | e.g. `Dateiablage` |
| `atr_smb_domain` | `String(128)` NULL | AD domain (NetBIOS or DNS) |
| `atr_smb_user` | `String(128)` NULL | service-account username |
| `atr_smb_password_enc` | `BYTEA` NULL | Fernet-encrypted password (write-only via API) |
| `atr_input_path` | `String(512)` NULL | path under the share, default `0900 - EDV/Test_ATR/Input` |
| `atr_output_path` | `String(512)` NULL | default `0900 - EDV/Test_ATR/Output` |
| `atr_archive_path` | `String(512)` NULL | default `0900 - EDV/Test_ATR/Archiv` |
| `atr_scan_interval_s` | `Integer` NOT NULL default 0 | 0 disables the scheduler job (mirrors `sensor_poll_interval_s` semantics) |
| `atr_auto_mode` | `Boolean` NOT NULL default `false` | false = review, true = auto |

Also add to `atr_delivery` (same migration): `origin` `String(8)` NOT NULL default `'upload'` (`'upload'`|`'scan'`), `source_path` `String(512)` NULL (the SMB input path of a scanned file), `output_written_at` `DateTime(tz)` NULL (set when the 3 files were written to the share).

## `services/atr_fileserver.py`

A thin wrapper over `smbprotocol`'s high-level `smbclient` API (`register_session`, `listdir`, `open_file`, `rename`/`replace`, `path`). One function per operation, each taking a `SmbConfig` (host, share, domain, user, password, input/output/archive paths) built from settings:

- `test_connection(cfg) -> tuple[bool, str|None]` — register a session, list the input dir, return `(ok, error)`.
- `list_input_pdfs(cfg) -> list[str]` — basenames of `*.pdf` in the input dir.
- `read_input(cfg, name) -> bytes`.
- `write_output(cfg, filename, data: bytes) -> None` — into the output dir.
- `archive_input(cfg, name) -> None` — move the input file into the archive dir (create archive dir if missing).

UNC paths are built as `\\{host}\{share}\{path}\{name}` with `/`→`\` normalization. Auth: username passed as `{domain}\{user}` (or `user@domain`). All calls are wrapped so a connection/auth error raises a typed `AtrFileserverError` the callers handle; the service never leaks raw smbprotocol exceptions to the scheduler.

> smbprotocol is synchronous. The scheduler job and the (rare) settings test-connection run it in a worker thread via `asyncio.to_thread(...)` so the event loop is never blocked.

## Scheduler `atr_scan` job

In `app/scheduler.py`, mirror the sensor-poll pattern:
- `_load_atr_interval()` reads `app_settings.atr_scan_interval_s`; `reschedule_atr_scan(new_interval_s)` adds/reschedules/removes the job exactly like `reschedule_sensor_poll` (0 → remove). Registered in the lifespan if interval > 0. `max_instances=1, coalesce=True, misfire_grace_time=30`, outer `asyncio.wait_for`.
- `_run_atr_scan()`: load settings; if SMB not fully configured or `atr_scan_interval_s == 0`, no-op. List input PDFs; for each name **not already linked to an `atr_delivery`** (query `atr_delivery.source_path` endswith / `source_filename == name` for scan-origin rows), process it:
  1. `read_input` → `parse_lieferschein` → `match_positions` → persist draft (`origin='scan'`, `source_path = {input}/{name}`, `source_filename=name`).
  2. If `atr_auto_mode`: call the shared generate routine (below) → on success, write outputs + archive.
  Per-file errors are caught and logged (one bad PDF never stops the batch); the job never raises out of the scheduler.

**Shared generate-and-deliver routine** (used by both the auto path and the Phase B Generate endpoint): build the 3 files (Phase B), store bytes on the delivery; then **if `origin=='scan'` and SMB configured**: `write_output` the 3 files (names below), `archive_input(source name)`, set `output_written_at`. PDF-conversion failure still writes the xlsx + docx (Phase B rule) and is reported.

Output filenames (per delivery): base = sanitized `atr_number` if set else `ba_auftrag` else the source stem; write `{base}.xlsx`, `{base}.pdf`, `{base}_Container.docx`.

## Phase B integration

- The Phase B manual **"from input folder"** endpoints (`GET /input-files`, `POST /input-files/process`) are rewired from the local `ATR_INPUT_DIR` filesystem to the SMB service (list/read via `atr_fileserver`), so the manual picker and the scheduler read the same share. The `ATR_INPUT_DIR` env var is removed.
- The Phase B **`POST /{id}/generate`** endpoint calls the shared generate-and-deliver routine, so a review-mode operator generating a scan-origin delivery writes the outputs to the share + archives the source. Upload-origin deliveries stay download-only (no share write).
- A delivery's `origin`/`source_path`/`output_written_at` are surfaced read-only in the delivery schema for the UI.

## Settings page `/settings/atr`

A new settings peer-page (mirrors the existing `/settings/sensors`, `/settings/hr` pattern + `SettingsSectionPicker`): fields for host/share/domain/user/password (write-only, shows "set"/"not set" like Personio), input/output/archive paths, scan interval, auto/review toggle, and a **Test connection** button (`POST /api/atr/fileserver/test`). Admin-gated. German + English i18n (flat keys).

Settings read/write extends the existing `/api/settings` GET/PUT (the password is write-only; the response exposes `atr_smb_has_password: bool`). Changing `atr_scan_interval_s` calls `reschedule_atr_scan` (like the sensor interval).

## Error handling

- `test_connection` returns `(ok, message)` — never throws to the route; the UI shows success/failure.
- Scheduler: connection failure → log + skip this tick (no crash); per-file parse/generate/write failure → log + continue with the next file; a file that fails generation is left in the input dir (not archived) so it's retried/visible.
- SMB not configured → the scan job is a no-op (and the settings page shows it's inactive).
- Writing to Output: if a same-named file exists, overwrite (regeneration is idempotent) — documented.

## Testing

Backend (pytest, against the disposable `acm_test` DB; **never** production):
- `test_atr_fileserver.py` — unit-test the UNC path building + the `SmbConfig`-from-settings mapping with `smbclient` monkeypatched (no real SMB): `list_input_pdfs` filters `*.pdf`, `write_output`/`archive_input` call the right paths, errors wrap to `AtrFileserverError`.
- `test_atr_scan.py` — with `atr_fileserver` faked (in-memory dir): a new PDF creates a draft (review mode, no output written); auto mode writes 3 outputs + archives; an already-linked filename is skipped; a malformed PDF is logged and doesn't stop the batch.
- `test_atr_scan_reschedule.py` — `reschedule_atr_scan` add/reschedule/remove on 0 (mirror the sensor reschedule test).
- `test_atr_generate_deliver.py` — the shared routine writes to the share + archives for `origin='scan'`, and does NOT for `origin='upload'`.
- Settings round-trip: the new columns persist; password write-only; `atr_smb_has_password` exposed; interval change triggers reschedule.
- Admin-gate: `/api/atr/fileserver/test` and the settings writes are admin-gated.

**Acceptance check (manual, needs the real service account):** on `/settings/atr`, enter the AD service account + paths, click **Test connection** (expect OK). Set review mode + a 60s interval. Drop `LIEFERSCHEIN_10005_20189798.pdf` into the Input folder; within the interval a draft delivery appears; Generate it → confirm `.xlsx/.pdf/.docx` land in Output and the PDF moves to Archiv. Repeat in auto mode → the 3 files appear without a manual step.

## Open items / infrastructure notes

- **Hostname resolution:** the container must resolve `acm_file` and reach it on TCP 445. If NetBIOS isn't resolvable from the Linux container, store the FQDN or IP in `atr_smb_host`. (No code dependency — just the configured value.)
- **Dependency:** add `smbprotocol` to `backend/requirements.txt` (pin at implementation; it's pure-Python, no system packages).
- **Security:** the AD password is Fernet-encrypted at rest and write-only over the API (never returned). The service account should be least-privilege: read on Input/Archiv, write on Output, move within Input→Archiv.

## Roadmap context

```
Phase A (done)   Reference foundation: catalog + template + import UI
Phase B (done)   Generate from a Lieferschein (manual): parse → match → review → ATR(.xlsx+PDF) + label(.docx)
Phase C (this)   Fileserver + automation: settings-driven SMB/AD client, scheduler scan, auto/review, write-to-Output + archive
```

Phase C completes the original brief.

## Implementation waves (for the plan)

1. **Settings + SMB service:** migration `v1_65` (app_settings columns + atr_delivery origin/source_path/output_written_at); `atr_fileserver` service (smbprotocol, `to_thread`) + unit tests; `/api/atr/fileserver/test` endpoint; settings GET/PUT extension + `atr_smb_has_password`. Deliverable: configure + test the connection.
2. **Scheduler scan + deliver:** the shared generate-and-deliver routine; the `atr_scan` job + `reschedule_atr_scan`; rewire Phase B input-files + generate to the SMB service; new-file detection + auto/review branching + write/archive; tests. Deliverable: automated pipeline end-to-end.
3. **Settings UI:** the `/settings/atr` page + Test-connection button + i18n; `atrApi` settings fields. Deliverable: operator-configurable in the UI.
