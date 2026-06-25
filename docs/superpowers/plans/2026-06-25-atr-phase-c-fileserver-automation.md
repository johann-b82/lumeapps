# ATR Phase C — Fileserver (AD/SMB) + Scheduler Automation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A scheduler job that lists new Lieferschein PDFs on an AD-authenticated SMB share (configured in the Settings UI), runs the Phase B pipeline, and — per a configurable auto/review mode — generates the ATR + label, writes them to the Output directory, and archives the input.

**Architecture:** A settings-driven SMB client (`smbprotocol`/`smbclient`, run via `asyncio.to_thread`) authenticating with credentials stored Fernet-encrypted in `app_settings`. A `services/atr_fileserver.py` wrapper; a shared `services/atr_deliver.py` generate-and-deliver routine used by both the scheduler and the Phase B Generate endpoint; an `atr_scan` APScheduler job mirroring the sensor-poll reschedule pattern; a `/settings/atr` page.

**Tech Stack:** FastAPI · SQLAlchemy 2.0 async · APScheduler · smbprotocol · openpyxl/python-docx/LibreOffice (from Phase B) · React 19 · wouter.

Reference spec: `docs/superpowers/specs/2026-06-25-atr-phase-c-fileserver-automation.md`. Branch: `feat/atr-phase-c` (off Phase B `feat/atr-phase-b`).

## Global Constraints

- **Admin-only writes.** Settings writes (`PUT /api/settings`) and `POST /api/atr/fileserver/test` are admin-gated (settings router is mixed-gate: viewer GET, admin PUT; mirror the existing per-route `Depends(require_admin)`).
- **Migration:** new `v1_65_atr_fileserver`, `down_revision = "v1_64_atr_delivery"` (re-verify head with `alembic heads`).
- **⚠ TEST DB SAFETY:** run backend pytest **only** against the disposable `acm_test` DB via `-e POSTGRES_DB=acm_test`; never the production `acm_kpi`. In-container test path is `tests/...` (workdir `/app`).
- **No real SMB in CI.** `smbclient` is monkeypatched in all backend tests; the real `\\acm_file\Dateiablage` is validated only by the manual acceptance check (Test-connection button). `smbprotocol` calls are synchronous → always invoked via `asyncio.to_thread(...)` from async code so the event loop is never blocked.
- **Credentials:** the SMB password is Fernet-encrypted with `app.security.fernet.encrypt_credential` / `decrypt_credential`, write-only over the API (never returned); the read schema exposes only `atr_smb_has_password: bool` (mirror `worldcup_has_api_key`).
- **Interval semantics:** `atr_scan_interval_s == 0` disables the job (mirror `sensor_poll_interval_s` / `reschedule_sensor_poll`); changes take effect immediately via `reschedule_atr_scan`.
- **Decimals as strings** on the wire; **flat i18n keys** (`keySeparator: false`), both locales.
- Commit after each task; image-affecting changes (requirements) require an api rebuild before affected tests.

---

## File Structure

**Backend**
- Create `backend/alembic/versions/v1_65_atr_fileserver.py`.
- Modify `backend/app/models/_base.py` (AppSettings columns), `backend/app/models/atr.py` (AtrDelivery columns).
- Modify `backend/app/defaults.py` (atr setting defaults for reset-isolation).
- Create `backend/app/services/atr_fileserver.py` (SMB wrapper).
- Create `backend/app/services/atr_deliver.py` (shared generate-and-deliver).
- Modify `backend/app/routers/atr_delivery.py` (input-files → SMB; generate → deliver routine).
- Modify `backend/app/routers/settings.py` (atr settings read/write + reschedule), add `POST /api/atr/fileserver/test`.
- Modify `backend/app/schemas/_base.py` (SettingsRead/SettingsUpdate atr fields).
- Modify `backend/app/scheduler.py` (`atr_scan` job + `reschedule_atr_scan` + lifespan).
- Modify `backend/requirements.txt` (`smbprotocol`).
- Modify `backend/tests/conftest.py` (reset atr settings columns).
- Tests under `backend/tests/`.

**Frontend**
- Modify `frontend/src/lib/api.ts` (Settings atr fields) — note: the global settings live in `api.ts`, not `atrApi.ts`.
- Modify `frontend/src/locales/en.json`, `de.json` (flat `atr.fileserver.*`).
- Create `frontend/src/pages/AtrSettingsPage.tsx`; modify `frontend/src/App.tsx` + `frontend/src/components/SettingsSectionPicker.tsx`.
- Tests under `frontend/src/pages/__tests__/`.

---

# Wave 1 — Settings columns + SMB service + Test-connection

## Task 1: Migration + model columns + defaults

**Files:**
- Modify: `backend/app/models/_base.py`, `backend/app/models/atr.py`, `backend/app/defaults.py`
- Create: `backend/alembic/versions/v1_65_atr_fileserver.py`
- Test: `backend/tests/test_atr_fileserver_columns.py`

**Interfaces:**
- Produces: `AppSettings.atr_smb_host/.atr_smb_share/.atr_smb_domain/.atr_smb_user/.atr_smb_password_enc/.atr_input_path/.atr_output_path/.atr_archive_path/.atr_scan_interval_s/.atr_auto_mode`; `AtrDelivery.origin/.source_path/.output_written_at`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_atr_fileserver_columns.py
from app.models import AppSettings, AtrDelivery


def test_appsettings_atr_columns():
    cols = {c.name for c in AppSettings.__table__.columns}
    assert {"atr_smb_host", "atr_smb_share", "atr_smb_domain", "atr_smb_user",
            "atr_smb_password_enc", "atr_input_path", "atr_output_path",
            "atr_archive_path", "atr_scan_interval_s", "atr_auto_mode"} <= cols


def test_delivery_origin_columns():
    cols = {c.name for c in AtrDelivery.__table__.columns}
    assert {"origin", "source_path", "output_written_at"} <= cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_fileserver_columns.py -v`
Expected: FAIL (AttributeError / missing columns).

- [ ] **Step 3: Add the model columns**

In `backend/app/models/_base.py`, append to `AppSettings` (after `worldcup_refresh_seconds`):

```python
    # --- v1.65 ATR fileserver (Phase C) ---
    atr_smb_host: Mapped[str | None] = mapped_column(String(255), nullable=True)
    atr_smb_share: Mapped[str | None] = mapped_column(String(255), nullable=True)
    atr_smb_domain: Mapped[str | None] = mapped_column(String(128), nullable=True)
    atr_smb_user: Mapped[str | None] = mapped_column(String(128), nullable=True)
    atr_smb_password_enc: Mapped[bytes | None] = mapped_column(BYTEA, nullable=True)
    atr_input_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    atr_output_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    atr_archive_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    atr_scan_interval_s: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    atr_auto_mode: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
```

In `backend/app/models/atr.py`, append to `AtrDelivery` (after `updated_at`, before the `items` relationship):

```python
    origin: Mapped[str] = mapped_column(String(8), nullable=False, default="upload")
    source_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    output_written_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
```

(`Boolean` is already imported in `_base.py`; confirm `String`, `Integer`, `BYTEA` imports exist — they do.)

- [ ] **Step 4: Write the migration**

```python
# backend/alembic/versions/v1_65_atr_fileserver.py
"""v1.65: ATR fileserver settings + delivery origin (Phase C)

Revision ID: v1_65_atr_fileserver
Revises: v1_64_atr_delivery
Create Date: 2026-06-25
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "v1_65_atr_fileserver"
down_revision = "v1_64_atr_delivery"
branch_labels = None
depends_on = None

_DEFAULT_INPUT = "0900 - EDV/Test_ATR/Input"
_DEFAULT_OUTPUT = "0900 - EDV/Test_ATR/Output"
_DEFAULT_ARCHIVE = "0900 - EDV/Test_ATR/Archiv"


def upgrade() -> None:
    op.add_column("app_settings", sa.Column("atr_smb_host", sa.String(255), nullable=True))
    op.add_column("app_settings", sa.Column("atr_smb_share", sa.String(255), nullable=True))
    op.add_column("app_settings", sa.Column("atr_smb_domain", sa.String(128), nullable=True))
    op.add_column("app_settings", sa.Column("atr_smb_user", sa.String(128), nullable=True))
    op.add_column("app_settings", sa.Column("atr_smb_password_enc", postgresql.BYTEA, nullable=True))
    op.add_column("app_settings", sa.Column("atr_input_path", sa.String(512), nullable=True))
    op.add_column("app_settings", sa.Column("atr_output_path", sa.String(512), nullable=True))
    op.add_column("app_settings", sa.Column("atr_archive_path", sa.String(512), nullable=True))
    op.add_column("app_settings", sa.Column("atr_scan_interval_s", sa.Integer, nullable=False, server_default="0"))
    op.add_column("app_settings", sa.Column("atr_auto_mode", sa.Boolean, nullable=False, server_default=sa.false()))

    op.add_column("atr_delivery", sa.Column("origin", sa.String(8), nullable=False, server_default="upload"))
    op.add_column("atr_delivery", sa.Column("source_path", sa.String(512), nullable=True))
    op.add_column("atr_delivery", sa.Column("output_written_at", sa.DateTime(timezone=True), nullable=True))

    # Seed default paths on the singleton row.
    op.execute(
        sa.text(
            "UPDATE app_settings SET atr_input_path=:i, atr_output_path=:o, atr_archive_path=:a WHERE id=1"
        ).bindparams(i=_DEFAULT_INPUT, o=_DEFAULT_OUTPUT, a=_DEFAULT_ARCHIVE)
    )


def downgrade() -> None:
    for col in ("output_written_at", "source_path", "origin"):
        op.drop_column("atr_delivery", col)
    for col in ("atr_auto_mode", "atr_scan_interval_s", "atr_archive_path", "atr_output_path",
                "atr_input_path", "atr_smb_password_enc", "atr_smb_user", "atr_smb_domain",
                "atr_smb_share", "atr_smb_host"):
        op.drop_column("app_settings", col)
```

- [ ] **Step 5: Apply migration + reset-isolation defaults**

In `backend/app/defaults.py`, add atr setting keys to `DEFAULT_SETTINGS` so the autouse `reset_settings` fixture restores them between tests:

```python
    "atr_smb_host": None,
    "atr_smb_share": None,
    "atr_smb_domain": None,
    "atr_smb_user": None,
    "atr_input_path": "0900 - EDV/Test_ATR/Input",
    "atr_output_path": "0900 - EDV/Test_ATR/Output",
    "atr_archive_path": "0900 - EDV/Test_ATR/Archiv",
    "atr_scan_interval_s": 0,
    "atr_auto_mode": False,
```

(The `DEFAULT_SETTINGS` type hint is `dict[str, str]`; widen it to `dict[str, object]`. `atr_smb_password_enc` is NOT reset here — clear it explicitly in tests that set it.)

Apply: `docker compose exec -T -e POSTGRES_DB=acm_test api alembic upgrade head`
Expected: `Running upgrade v1_64_atr_delivery -> v1_65_atr_fileserver`.

- [ ] **Step 6: Run the test**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_fileserver_columns.py -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add backend/app/models/_base.py backend/app/models/atr.py backend/app/defaults.py backend/alembic/versions/v1_65_atr_fileserver.py backend/tests/test_atr_fileserver_columns.py
git commit -m "feat(atr): fileserver settings + delivery origin columns (migration v1_65)"
```

---

## Task 2: SMB fileserver service

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/app/services/atr_fileserver.py`
- Test: `backend/tests/test_atr_fileserver.py`

**Interfaces:**
- Produces: dataclass `SmbConfig`; `AtrFileserverError`; `smb_config_from_settings(row) -> SmbConfig | None`; `list_input_pdfs(cfg) -> list[str]`; `read_input(cfg, name) -> bytes`; `write_output(cfg, filename, data) -> None`; `archive_input(cfg, name) -> None`; `test_connection(cfg) -> tuple[bool, str | None]`. All synchronous.

- [ ] **Step 1: Add the dependency**

In `backend/requirements.txt`, add: `smbprotocol==1.15.0`. Then rebuild: `docker compose build api && docker compose up -d api` and verify `docker compose exec -T api python -c "import smbclient; print('smbclient ok')"` → `smbclient ok`.

- [ ] **Step 2: Write the failing test**

```python
# backend/tests/test_atr_fileserver.py
import types
import pytest

from app.services import atr_fileserver as fs
from app.services.atr_fileserver import SmbConfig, AtrFileserverError


def _cfg():
    return SmbConfig(host="srv", share="Dateiablage", domain="ACME", user="svc",
                     password="pw", input_path="A/In", output_path="A/Out", archive_path="A/Arch")


def test_unc_building():
    assert fs._unc("srv", "Dateiablage", "A/In", "x.pdf") == r"\\srv\Dateiablage\A\In\x.pdf"


def test_list_filters_pdf(monkeypatch):
    fake = types.SimpleNamespace(
        register_session=lambda *a, **k: None,
        listdir=lambda unc: ["a.pdf", "b.PDF", "c.txt", "sub"],
    )
    monkeypatch.setattr(fs, "smbclient", fake)
    assert fs.list_input_pdfs(_cfg()) == ["a.pdf", "b.PDF"]


def test_write_and_archive_call_paths(monkeypatch):
    calls = {}
    class FakeFile:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def write(self, d): calls["wrote"] = d
        def read(self): return b"DATA"
    fake = types.SimpleNamespace(
        register_session=lambda *a, **k: None,
        open_file=lambda unc, mode="rb": (calls.__setitem__("open", (unc, mode)) or FakeFile()),
        makedirs=lambda unc, exist_ok=True: calls.__setitem__("mkdir", unc),
        rename=lambda s, d: calls.__setitem__("rename", (s, d)),
    )
    monkeypatch.setattr(fs, "smbclient", fake)
    fs.write_output(_cfg(), "out.xlsx", b"DATA")
    assert calls["open"][0] == r"\\srv\Dateiablage\A\Out\out.xlsx" and calls["wrote"] == b"DATA"
    fs.archive_input(_cfg(), "in.pdf")
    assert calls["rename"] == (r"\\srv\Dateiablage\A\In\in.pdf", r"\\srv\Dateiablage\A\Arch\in.pdf")


def test_errors_wrap(monkeypatch):
    def boom(*a, **k): raise OSError("net down")
    fake = types.SimpleNamespace(register_session=boom, listdir=boom)
    monkeypatch.setattr(fs, "smbclient", fake)
    with pytest.raises(AtrFileserverError):
        fs.list_input_pdfs(_cfg())


def test_test_connection_returns_tuple(monkeypatch):
    fake = types.SimpleNamespace(register_session=lambda *a, **k: None, listdir=lambda u: [])
    monkeypatch.setattr(fs, "smbclient", fake)
    ok, err = fs.test_connection(_cfg())
    assert ok is True and err is None


def test_config_from_settings_none_when_incomplete():
    row = types.SimpleNamespace(atr_smb_host=None, atr_smb_share="s", atr_smb_domain="d",
                                atr_smb_user="u", atr_smb_password_enc=b"x",
                                atr_input_path="i", atr_output_path="o", atr_archive_path="a")
    assert fs.smb_config_from_settings(row) is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_fileserver.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 4: Write the service**

```python
# backend/app/services/atr_fileserver.py
"""SMB fileserver access for the ATR module (Phase C).

Thin wrapper over smbprotocol's high-level `smbclient` API. Synchronous —
callers in async code wrap each function in `asyncio.to_thread(...)`.
Credentials come from app_settings (the AD service account). No OS mount.
"""
from __future__ import annotations

from dataclasses import dataclass

import smbclient

from app.security.fernet import decrypt_credential


@dataclass
class SmbConfig:
    host: str
    share: str
    domain: str | None
    user: str
    password: str
    input_path: str
    output_path: str
    archive_path: str


class AtrFileserverError(Exception):
    """Any SMB connection / IO failure, with a human-readable message."""


def smb_config_from_settings(row) -> SmbConfig | None:
    """Build an SmbConfig from the app_settings singleton, or None if incomplete."""
    if not (row.atr_smb_host and row.atr_smb_share and row.atr_smb_user
            and row.atr_smb_password_enc and row.atr_input_path
            and row.atr_output_path and row.atr_archive_path):
        return None
    return SmbConfig(
        host=row.atr_smb_host, share=row.atr_smb_share, domain=row.atr_smb_domain,
        user=row.atr_smb_user, password=decrypt_credential(row.atr_smb_password_enc),
        input_path=row.atr_input_path, output_path=row.atr_output_path,
        archive_path=row.atr_archive_path,
    )


def _unc(host: str, share: str, *parts: str) -> str:
    segs: list[str] = []
    for p in parts:
        segs.extend(s for s in p.replace("/", "\\").split("\\") if s)
    tail = "\\".join(segs)
    return rf"\\{host}\{share}" + (("\\" + tail) if tail else "")


def _register(cfg: SmbConfig) -> None:
    username = f"{cfg.domain}\\{cfg.user}" if cfg.domain else cfg.user
    smbclient.register_session(cfg.host, username=username, password=cfg.password)


def list_input_pdfs(cfg: SmbConfig) -> list[str]:
    try:
        _register(cfg)
        unc = _unc(cfg.host, cfg.share, cfg.input_path)
        return [n for n in smbclient.listdir(unc) if n.lower().endswith(".pdf")]
    except Exception as exc:  # noqa: BLE001
        raise AtrFileserverError(f"list_input_pdfs failed: {exc}") from exc


def read_input(cfg: SmbConfig, name: str) -> bytes:
    try:
        _register(cfg)
        unc = _unc(cfg.host, cfg.share, cfg.input_path, name)
        with smbclient.open_file(unc, mode="rb") as fh:
            return fh.read()
    except Exception as exc:  # noqa: BLE001
        raise AtrFileserverError(f"read_input failed for {name}: {exc}") from exc


def write_output(cfg: SmbConfig, filename: str, data: bytes) -> None:
    try:
        _register(cfg)
        out_dir = _unc(cfg.host, cfg.share, cfg.output_path)
        smbclient.makedirs(out_dir, exist_ok=True)
        with smbclient.open_file(_unc(cfg.host, cfg.share, cfg.output_path, filename), mode="wb") as fh:
            fh.write(data)
    except Exception as exc:  # noqa: BLE001
        raise AtrFileserverError(f"write_output failed for {filename}: {exc}") from exc


def archive_input(cfg: SmbConfig, name: str) -> None:
    try:
        _register(cfg)
        arch_dir = _unc(cfg.host, cfg.share, cfg.archive_path)
        smbclient.makedirs(arch_dir, exist_ok=True)
        src = _unc(cfg.host, cfg.share, cfg.input_path, name)
        dst = _unc(cfg.host, cfg.share, cfg.archive_path, name)
        smbclient.rename(src, dst)
    except Exception as exc:  # noqa: BLE001
        raise AtrFileserverError(f"archive_input failed for {name}: {exc}") from exc


def test_connection(cfg: SmbConfig) -> tuple[bool, str | None]:
    try:
        _register(cfg)
        smbclient.listdir(_unc(cfg.host, cfg.share, cfg.input_path))
        return True, None
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
```

- [ ] **Step 5: Run the test**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_fileserver.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/requirements.txt backend/app/services/atr_fileserver.py backend/tests/test_atr_fileserver.py
git commit -m "feat(atr): SMB fileserver service (smbprotocol wrapper)"
```

---

## Task 3: Settings read/write + Test-connection endpoint

**Files:**
- Modify: `backend/app/schemas/_base.py` (SettingsRead/SettingsUpdate)
- Modify: `backend/app/routers/settings.py`
- Modify: `backend/tests/conftest.py` (reset atr password between tests)
- Test: `backend/tests/test_atr_settings.py`

**Interfaces:**
- Consumes: `smb_config_from_settings`, `test_connection`, `encrypt_credential`, `reschedule_atr_scan` (Task 7 adds the real reschedule; for now import lazily and guard).
- Produces: SettingsRead atr fields + `atr_smb_has_password`; SettingsUpdate atr write fields; `POST /api/atr/fileserver/test`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_atr_settings.py
from tests._auth import ADMIN_UUID, VIEWER_UUID, mint


def _admin():
    return {"Authorization": f"Bearer {mint(ADMIN_UUID)}"}


async def test_settings_roundtrip_atr(client):
    # read defaults
    r = await client.get("/api/settings", headers=_admin())
    assert r.status_code == 200
    body = r.json()
    assert body["atr_input_path"] == "0900 - EDV/Test_ATR/Input"
    assert body["atr_smb_has_password"] is False
    assert body["atr_scan_interval_s"] == 0

    # write (full PUT — colors+app_name required; reuse the read values)
    payload = {k: body[k] for k in ["color_primary","color_accent","color_background",
               "color_foreground","color_muted","color_destructive","app_name"]}
    payload.update({"atr_smb_host": "acm_file", "atr_smb_share": "Dateiablage",
                    "atr_smb_domain": "ACME", "atr_smb_user": "svc",
                    "atr_smb_password": "secret", "atr_output_path": "X/Out",
                    "atr_scan_interval_s": 0})
    r = await client.put("/api/settings", headers=_admin(), json=payload)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["atr_smb_host"] == "acm_file"
    assert out["atr_output_path"] == "X/Out"
    assert out["atr_smb_has_password"] is True  # password set, not echoed
    assert "atr_smb_password" not in out


async def test_fileserver_test_endpoint(client, monkeypatch):
    from app.services import atr_fileserver as fs
    # configure creds first
    r = await client.get("/api/settings", headers=_admin())
    body = r.json()
    payload = {k: body[k] for k in ["color_primary","color_accent","color_background",
               "color_foreground","color_muted","color_destructive","app_name"]}
    payload.update({"atr_smb_host": "h", "atr_smb_share": "s", "atr_smb_user": "u",
                    "atr_smb_password": "p"})
    await client.put("/api/settings", headers=_admin(), json=payload)
    monkeypatch.setattr(fs, "test_connection", lambda cfg: (True, None))
    r = await client.post("/api/atr/fileserver/test", headers=_admin())
    assert r.status_code == 200 and r.json() == {"ok": True, "error": None}


async def test_test_endpoint_admin_gated(client):
    r = await client.post("/api/atr/fileserver/test",
                          headers={"Authorization": f"Bearer {mint(VIEWER_UUID)}"})
    assert r.status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_settings.py -v`
Expected: FAIL.

- [ ] **Step 3: Extend the schemas**

In `backend/app/schemas/_base.py`, add to `SettingsRead` (the model returned by GET):

```python
    atr_smb_host: str | None = None
    atr_smb_share: str | None = None
    atr_smb_domain: str | None = None
    atr_smb_user: str | None = None
    atr_smb_has_password: bool = False
    atr_input_path: str | None = None
    atr_output_path: str | None = None
    atr_archive_path: str | None = None
    atr_scan_interval_s: int = 0
    atr_auto_mode: bool = False
```

and to `SettingsUpdate` (None = don't change; password is write-only):

```python
    atr_smb_host: str | None = None
    atr_smb_share: str | None = None
    atr_smb_domain: str | None = None
    atr_smb_user: str | None = None
    atr_smb_password: str | None = None
    atr_input_path: str | None = None
    atr_output_path: str | None = None
    atr_archive_path: str | None = None
    atr_scan_interval_s: int | None = None
    atr_auto_mode: bool | None = None
```

- [ ] **Step 4: Wire the router**

In `backend/app/routers/settings.py`:

a) In `_build_read(...)`, add the atr fields to the `SettingsRead(...)` construction:

```python
        atr_smb_host=row.atr_smb_host,
        atr_smb_share=row.atr_smb_share,
        atr_smb_domain=row.atr_smb_domain,
        atr_smb_user=row.atr_smb_user,
        atr_smb_has_password=row.atr_smb_password_enc is not None,
        atr_input_path=row.atr_input_path,
        atr_output_path=row.atr_output_path,
        atr_archive_path=row.atr_archive_path,
        atr_scan_interval_s=row.atr_scan_interval_s,
        atr_auto_mode=row.atr_auto_mode,
```

b) In `put_settings(...)`, before the final commit, add the atr writes (None = don't change; password encrypted; interval reschedules):

```python
    for _f in ("atr_smb_host", "atr_smb_share", "atr_smb_domain", "atr_smb_user",
               "atr_input_path", "atr_output_path", "atr_archive_path", "atr_auto_mode"):
        _v = getattr(payload, _f)
        if _v is not None:
            setattr(row, _f, _v)
    if payload.atr_smb_password is not None:
        from app.security.fernet import encrypt_credential
        row.atr_smb_password_enc = encrypt_credential(payload.atr_smb_password)
    if payload.atr_scan_interval_s is not None:
        row.atr_scan_interval_s = payload.atr_scan_interval_s
        try:
            from app.scheduler import reschedule_atr_scan
            reschedule_atr_scan(payload.atr_scan_interval_s)
        except Exception:  # scheduler hook lands in Task 7; never fail the PUT
            pass
```

c) Add the test-connection endpoint. Create a small admin-gated router in the same file (or reuse the settings router with a per-route admin dep). Add at the end of `settings.py`:

```python
from fastapi import APIRouter as _APIRouter  # already imported as APIRouter; reuse it

atr_fileserver_router = APIRouter(
    prefix="/api/atr/fileserver",
    tags=["atr"],
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)


@atr_fileserver_router.post("/test")
async def atr_fileserver_test(db: AsyncSession = Depends(get_async_db_session)) -> dict:
    from app.services import atr_fileserver as fs
    row = await _get_singleton(db)
    cfg = fs.smb_config_from_settings(row)
    if cfg is None:
        return {"ok": False, "error": "SMB not fully configured"}
    import asyncio
    ok, err = await asyncio.to_thread(fs.test_connection, cfg)
    return {"ok": ok, "error": err}
```

Register `atr_fileserver_router` in `backend/app/main.py`: `from app.routers.settings import atr_fileserver_router` + `app.include_router(atr_fileserver_router)`.

d) In `backend/tests/conftest.py`, extend the `reset_atr` fixture to also clear `atr_smb_password_enc` (the only atr column not in `DEFAULT_SETTINGS`): add `atr_smb_password_enc=None` to the `update(AtrTemplate)`-adjacent reset, OR add a one-line `update(AppSettings).where(id==1).values(atr_smb_password_enc=None)` in the existing reset block.

- [ ] **Step 5: Run the tests**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_settings.py tests/test_admin_gate_audit.py -v`
Expected: the atr settings tests PASS; `test_admin_gate_audit` unchanged (the new `/api/atr/fileserver/test` is admin-gated → no new violation).

- [ ] **Step 6: Commit**

```bash
git add backend/app/schemas/_base.py backend/app/routers/settings.py backend/app/main.py backend/tests/conftest.py backend/tests/test_atr_settings.py
git commit -m "feat(atr): settings read/write for fileserver + test-connection endpoint"
```

---

# Wave 2 — Scheduler scan + deliver + Phase B integration

## Task 4: Shared generate-and-deliver routine

**Files:**
- Create: `backend/app/services/atr_deliver.py`
- Test: `backend/tests/test_atr_deliver.py`

**Interfaces:**
- Consumes: `build_atr_xlsx`, `convert_xlsx_to_pdf`, `build_containerbeschriftung`, `AtrTemplate`, `AtrGenerateManifest`, `atr_fileserver`.
- Produces: `async generate_and_deliver(db, delivery, settings_row) -> AtrGenerateManifest`. Raises `ValueError` if no structural template.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_atr_deliver.py
import pytest
from tests._atr_fixtures import build_atr_workbook_bytes
from tests._auth import ADMIN_UUID, mint


def _auth():
    return {"Authorization": f"Bearer {mint(ADMIN_UUID)}"}


async def _seed_template_and_delivery(client, origin):
    # set structural template
    files = {"file": ("t.xlsx", build_atr_workbook_bytes(),
             "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    await client.post("/api/atr/template/structure", headers=_auth(), files=files)
    from app.database import AsyncSessionLocal
    from app.models import AtrDelivery, AtrDeliveryItem
    from datetime import datetime, timezone
    from decimal import Decimal
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        d = AtrDelivery(source_filename="LS.pdf", status="draft", origin=origin,
                        source_path=("0900 - EDV/Test_ATR/Input/LS.pdf" if origin=="scan" else None),
                        ba_auftrag="1024738", set_title="SET 6 BED CCRC", po_number="4501119979",
                        msn="830", created_at=now, updated_at=now)
        d.items.append(AtrDeliveryItem(pos=1, supplier_article_code="6060",
            part_number="VR11S 1010 016 000", part_number_norm="111010016000",
            part_name="CARPET EMERGENCY EXIT HATCH", drawing_number_issue="VR11S 1010-10/D",
            category="CARPET", qty=1, weight_kg=Decimal("0.413"), po_pos="050",
            match_status="matched", row_order=1))
        db.add(d); await db.commit(); await db.refresh(d)
        return d.id


async def test_deliver_writes_and_archives_for_scan(client, monkeypatch):
    did = await _seed_template_and_delivery(client, origin="scan")
    from app.services import atr_fileserver as fs
    written = {}
    monkeypatch.setattr(fs, "write_output", lambda cfg, name, data: written.__setitem__(name, len(data)))
    monkeypatch.setattr(fs, "archive_input", lambda cfg, name: written.__setitem__("archived", name))
    # make config "available"
    from app.database import AsyncSessionLocal
    from app.models import AppSettings
    from sqlalchemy import update
    async with AsyncSessionLocal() as db:
        await db.execute(update(AppSettings).where(AppSettings.id==1).values(
            atr_smb_host="h", atr_smb_share="s", atr_smb_user="u",
            atr_smb_password_enc=__import__("app.security.fernet", fromlist=["encrypt_credential"]).encrypt_credential("p")))
        await db.commit()

    from app.services.atr_deliver import generate_and_deliver
    from app.models import AtrDelivery
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    async with AsyncSessionLocal() as db:
        d = (await db.execute(select(AtrDelivery).options(selectinload(AtrDelivery.items)).where(AtrDelivery.id==did))).scalar_one()
        row = (await db.execute(select(AppSettings).where(AppSettings.id==1))).scalar_one()
        man = await generate_and_deliver(db, d, row)
    assert any(n.endswith(".xlsx") for n in written) and "archived" in written
    assert man.delivery_id == did


async def test_deliver_upload_origin_does_not_write(client, monkeypatch):
    did = await _seed_template_and_delivery(client, origin="upload")
    from app.services import atr_fileserver as fs
    written = {}
    monkeypatch.setattr(fs, "write_output", lambda *a: written.setdefault("x", 1))
    from app.database import AsyncSessionLocal
    from app.services.atr_deliver import generate_and_deliver
    from app.models import AtrDelivery, AppSettings
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    async with AsyncSessionLocal() as db:
        d = (await db.execute(select(AtrDelivery).options(selectinload(AtrDelivery.items)).where(AtrDelivery.id==did))).scalar_one()
        row = (await db.execute(select(AppSettings).where(AppSettings.id==1))).scalar_one()
        await generate_and_deliver(db, d, row)
    assert written == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_deliver.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Write the routine**

```python
# backend/app/services/atr_deliver.py
"""Shared generate-and-deliver routine (Phase C).

Builds the three documents for a delivery (Phase B generators), stores the
bytes on the row, and — for scan-origin deliveries when the SMB share is
configured — writes them to the Output dir and archives the source PDF.
Used by both the scheduler (auto mode) and the Phase B Generate endpoint.
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AtrTemplate
from app.schemas import AtrGenerateManifest
from app.services import atr_fileserver as fs
from app.services.atr_generate_docx import build_containerbeschriftung
from app.services.atr_generate_xlsx import build_atr_xlsx, convert_xlsx_to_pdf

log = logging.getLogger(__name__)


def _base_name(delivery) -> str:
    raw = delivery.atr_number or delivery.ba_auftrag or (
        (delivery.source_filename or "atr").rsplit(".", 1)[0])
    return re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("_") or "atr"


async def generate_and_deliver(db: AsyncSession, delivery, settings_row) -> AtrGenerateManifest:
    items = list(delivery.items)
    tmpl = (await db.execute(select(AtrTemplate).where(AtrTemplate.id == 1))).scalar_one_or_none()
    if tmpl is None or tmpl.structure_xlsx is None:
        raise ValueError("no structural template set")

    warnings: list[str] = []
    xlsx = build_atr_xlsx(tmpl.structure_xlsx, delivery, items)
    docx = build_containerbeschriftung(delivery, items)
    pdf: bytes | None = None
    try:
        pdf = await convert_xlsx_to_pdf(xlsx)
    except Exception as exc:  # noqa: BLE001
        log.warning("atr deliver: pdf conversion failed for delivery %s: %s", delivery.id, exc)
        warnings.append("PDF conversion failed; .xlsx and .docx are still available.")

    delivery.atr_xlsx = xlsx
    delivery.atr_pdf = pdf
    delivery.label_docx = docx
    delivery.status = "generated"
    delivery.updated_at = datetime.now(timezone.utc)

    cfg = fs.smb_config_from_settings(settings_row)
    if delivery.origin == "scan" and cfg is not None:
        base = _base_name(delivery)
        try:
            await asyncio.to_thread(fs.write_output, cfg, f"{base}.xlsx", xlsx)
            if pdf is not None:
                await asyncio.to_thread(fs.write_output, cfg, f"{base}.pdf", pdf)
            await asyncio.to_thread(fs.write_output, cfg, f"{base}_Container.docx", docx)
            if delivery.source_path:
                await asyncio.to_thread(fs.archive_input, cfg, delivery.source_path.rsplit("/", 1)[-1])
            delivery.output_written_at = datetime.now(timezone.utc)
            delivery.status = "delivered"
        except fs.AtrFileserverError as exc:
            log.warning("atr deliver: share write/archive failed for delivery %s: %s", delivery.id, exc)
            warnings.append(f"writing to the fileserver failed: {exc}")

    await db.commit()

    files = ["atr_xlsx", "label_docx"] + (["atr_pdf"] if pdf else [])
    unmatched = sum(1 for i in items if i.match_status != "matched")
    if unmatched:
        warnings.append(f"{unmatched} unmatched part(s) marked red in the ATR — fix in Excel.")
    return AtrGenerateManifest(delivery_id=delivery.id, files=files,
                               pdf_available=pdf is not None,
                               unmatched_count=unmatched, warnings=warnings)
```

- [ ] **Step 4: Run the test**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_deliver.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/atr_deliver.py backend/tests/test_atr_deliver.py
git commit -m "feat(atr): shared generate-and-deliver routine (write to share + archive for scan origin)"
```

---

## Task 5: Rewire Phase B Generate to the deliver routine

**Files:**
- Modify: `backend/app/routers/atr_delivery.py`
- Test: `backend/tests/test_atr_delivery_generate.py` (extend)

**Interfaces:**
- Consumes: `generate_and_deliver`, `AppSettings`.

- [ ] **Step 1: Write the failing test (extend the generate test)**

Append to `backend/tests/test_atr_delivery_generate.py`:

```python
async def test_generate_scan_origin_writes_to_share(client, monkeypatch):
    await _set_structure(client)
    from app.services import atr_fileserver as fs
    seen = {}
    monkeypatch.setattr(fs, "write_output", lambda cfg, name, data: seen.__setitem__(name, 1))
    monkeypatch.setattr(fs, "archive_input", lambda cfg, name: seen.__setitem__("arch", name))
    # configure SMB + create a scan-origin delivery directly
    from app.database import AsyncSessionLocal
    from app.models import AppSettings, AtrDelivery, AtrDeliveryItem
    from sqlalchemy import update
    from datetime import datetime, timezone
    from app.security.fernet import encrypt_credential
    now = datetime.now(timezone.utc)
    async with AsyncSessionLocal() as db:
        await db.execute(update(AppSettings).where(AppSettings.id==1).values(
            atr_smb_host="h", atr_smb_share="s", atr_smb_user="u",
            atr_smb_password_enc=encrypt_credential("p")))
        d = AtrDelivery(source_filename="LS.pdf", status="draft", origin="scan",
            source_path="0900 - EDV/Test_ATR/Input/LS.pdf", ba_auftrag="1024738",
            set_title="SET 6 BED CCRC", created_at=now, updated_at=now)
        d.items.append(AtrDeliveryItem(pos=1, supplier_article_code="6060",
            part_number="VR11S 1010 016 000", part_number_norm="111010016000",
            part_name="X", category="CARPET", qty=1, match_status="matched", row_order=1))
        db.add(d); await db.commit(); did = d.id
    r = await client.post(f"/api/atr/deliveries/{did}/generate", headers=_auth(), json={})
    assert r.status_code == 200, r.text
    assert any(n.endswith(".xlsx") for n in seen) and "arch" in seen
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_delivery_generate.py::test_generate_scan_origin_writes_to_share -v`
Expected: FAIL (endpoint still uses the old inline build; no share write).

- [ ] **Step 3: Refactor the generate endpoint to call the routine**

In `backend/app/routers/atr_delivery.py`, replace the body of `generate(...)` (the inline xlsx/docx/pdf build + store + manifest) with a call to the shared routine. Keep the `_get` (selectinload items) and the no-template→400 mapping:

```python
@router.post("/{delivery_id}/generate", response_model=AtrGenerateManifest)
async def generate(delivery_id: int,
                   db: AsyncSession = Depends(get_async_db_session)) -> AtrGenerateManifest:
    from app.models import AppSettings
    from app.services.atr_deliver import generate_and_deliver
    row = await _get(db, delivery_id)
    settings_row = (await db.execute(select(AppSettings).where(AppSettings.id == 1))).scalar_one()
    try:
        return await generate_and_deliver(db, row, settings_row)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
```

Remove the now-unused imports/helpers in `atr_delivery.py` that were only used by the old inline generate body (`build_atr_xlsx`, `convert_xlsx_to_pdf`, `build_containerbeschriftung`, `AtrTemplate`, `AtrGenerateManifest` stays — it's the response_model; keep `select`). Leave `_MEDIA` + the download endpoint untouched.

- [ ] **Step 4: Run the tests**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_delivery_generate.py -v`
Expected: PASS (the original generate/download test + the new scan-origin test).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/atr_delivery.py backend/tests/test_atr_delivery_generate.py
git commit -m "feat(atr): Generate endpoint delegates to shared deliver routine"
```

---

## Task 6: Rewire input-files to the SMB service

**Files:**
- Modify: `backend/app/routers/atr_delivery.py`
- Modify: `docker-compose.yml` (remove `ATR_INPUT_DIR`)
- Test: `backend/tests/test_atr_delivery_inputfiles.py`

**Interfaces:**
- Consumes: `atr_fileserver`, `AppSettings`. Replaces the local-filesystem input-files logic.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_atr_delivery_inputfiles.py
from tests._atr_pdf import make_text_pdf
from tests._auth import ADMIN_UUID, mint


def _auth():
    return {"Authorization": f"Bearer {mint(ADMIN_UUID)}"}


async def _configure_smb(client):
    from app.database import AsyncSessionLocal
    from app.models import AppSettings
    from sqlalchemy import update
    from app.security.fernet import encrypt_credential
    async with AsyncSessionLocal() as db:
        await db.execute(update(AppSettings).where(AppSettings.id==1).values(
            atr_smb_host="h", atr_smb_share="s", atr_smb_user="u",
            atr_smb_password_enc=encrypt_credential("p")))
        await db.commit()


async def test_input_files_unconfigured(client):
    r = await client.get("/api/atr/deliveries/input-files", headers=_auth())
    assert r.status_code == 200 and r.json() == {"configured": False, "files": []}


async def test_input_files_and_process_via_smb(client, monkeypatch):
    await _configure_smb(client)
    from app.services import atr_fileserver as fs
    pdf = make_text_pdf("\n".join([
        "LIEFERSCHEIN Nr. 20189798 Datum 08.06.2026", "1 6060 1 STK",
        "CARPET EMERG. EXIT HATCH", "Bauteil-Index: D", "Ihre Nr. VR11S1010016000",
        "Auftrag Nr. 1024738 / 5", "Bestelldaten 4501119979/A350/CCRC/MSN830/6-Bett"]))
    monkeypatch.setattr(fs, "list_input_pdfs", lambda cfg: ["LS.pdf"])
    monkeypatch.setattr(fs, "read_input", lambda cfg, name: pdf)

    r = await client.get("/api/atr/deliveries/input-files", headers=_auth())
    assert r.json() == {"configured": True, "files": ["LS.pdf"]}

    r = await client.post("/api/atr/deliveries/input-files/process", headers=_auth(),
                          json={"filename": "LS.pdf"})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["origin"] == "scan"
    assert body["source_path"].endswith("LS.pdf")
```

> Add `origin` and `source_path` to `AtrDeliveryRead` (schema) if not already present — they were added to the model in Task 1; expose them read-only: add `origin: str` and `source_path: str | None` and `output_written_at: datetime | None` to `AtrDeliveryRead` in `backend/app/schemas/atr_delivery.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_delivery_inputfiles.py -v`
Expected: FAIL (input-files still reads `ATR_INPUT_DIR`; no `origin` field).

- [ ] **Step 3: Rewire the endpoints**

In `backend/app/schemas/atr_delivery.py`, add to `AtrDeliveryRead`: `origin: str`, `source_path: str | None`, `output_written_at: datetime | None`.

In `backend/app/routers/atr_delivery.py`, replace `input_files` and `process_input_file` with SMB-backed versions (remove the `os`/`Path`/`ATR_INPUT_DIR` logic):

```python
async def _smb_cfg(db):
    from app.models import AppSettings
    from app.services import atr_fileserver as fs
    row = (await db.execute(select(AppSettings).where(AppSettings.id == 1))).scalar_one()
    return fs.smb_config_from_settings(row), row


@router.get("/input-files")
async def input_files(db: AsyncSession = Depends(get_async_db_session)) -> dict:
    import asyncio
    from app.services import atr_fileserver as fs
    cfg, _ = await _smb_cfg(db)
    if cfg is None:
        return {"configured": False, "files": []}
    try:
        files = await asyncio.to_thread(fs.list_input_pdfs, cfg)
    except fs.AtrFileserverError as exc:
        raise HTTPException(502, f"fileserver error: {exc}") from exc
    return {"configured": True, "files": files}


@router.post("/input-files/process", response_model=AtrDeliveryRead, status_code=201)
async def process_input_file(payload: dict,
                             db: AsyncSession = Depends(get_async_db_session)) -> AtrDelivery:
    import asyncio
    from app.services import atr_fileserver as fs
    cfg, _ = await _smb_cfg(db)
    if cfg is None:
        raise HTTPException(400, "SMB fileserver not configured")
    name = Path(str(payload.get("filename", ""))).name
    if not name.lower().endswith(".pdf"):
        raise HTTPException(404, "file not found")
    try:
        raw = await asyncio.to_thread(fs.read_input, cfg, name)
    except fs.AtrFileserverError as exc:
        raise HTTPException(502, f"fileserver error: {exc}") from exc
    try:
        parsed = await parse_lieferschein(raw)
    except ValueError as exc:
        raise HTTPException(400, f"could not read PDF: {exc}") from exc
    if not parsed.positions:
        raise HTTPException(422, "no positions found in Lieferschein")
    md = await match_positions(db, parsed, name)
    delivery = await _persist_draft(db, md)
    # mark origin = scan + source_path
    delivery.origin = "scan"
    delivery.source_path = f"{cfg.input_path}/{name}"
    await db.commit()
    return await _get(db, delivery.id)
```

Keep `from pathlib import Path` import; drop the `import os` if now unused. In `docker-compose.yml`, remove the `ATR_INPUT_DIR: ${ATR_INPUT_DIR:-}` line from the api `environment:` block.

- [ ] **Step 4: Run the tests**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_delivery_inputfiles.py tests/test_atr_delivery_router.py -v`
Expected: the new input-files tests PASS; `test_atr_delivery_router.py` — its old `test_input_files_empty_when_unset` still passes (unconfigured → `{configured: False, files: []}`).

- [ ] **Step 5: Commit**

```bash
git add backend/app/routers/atr_delivery.py backend/app/schemas/atr_delivery.py docker-compose.yml backend/tests/test_atr_delivery_inputfiles.py
git commit -m "feat(atr): input-files read from the SMB share; expose delivery origin"
```

---

## Task 7: Scheduler scan job

**Files:**
- Modify: `backend/app/scheduler.py`
- Test: `backend/tests/test_atr_scan.py`

**Interfaces:**
- Consumes: `atr_fileserver`, `parse_lieferschein`, `match_positions`, `generate_and_deliver`, `AppSettings`, `AtrDelivery`.
- Produces: `ATR_SCAN_JOB_ID`, `reschedule_atr_scan(new_interval_s)`, `_run_atr_scan()`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_atr_scan.py
import pytest
from tests._atr_pdf import make_text_pdf
from tests._auth import ADMIN_UUID, mint


def _auth():
    return {"Authorization": f"Bearer {mint(ADMIN_UUID)}"}


_LS = "\n".join(["LIEFERSCHEIN Nr. 20189798 Datum 08.06.2026", "1 6060 1 STK",
    "CARPET EMERG. EXIT HATCH", "Bauteil-Index: D", "Ihre Nr. VR11S1010016000",
    "Auftrag Nr. 1024738 / 5", "Bestelldaten 4501119979/A350/CCRC/MSN830/6-Bett"])


async def _configure(client, auto: bool):
    from app.database import AsyncSessionLocal
    from app.models import AppSettings
    from sqlalchemy import update
    from app.security.fernet import encrypt_credential
    # structural template (needed for auto generate)
    from tests._atr_fixtures import build_atr_workbook_bytes
    await client.post("/api/atr/template/structure", headers=_auth(),
        files={"file": ("t.xlsx", build_atr_workbook_bytes(),
               "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    async with AsyncSessionLocal() as db:
        await db.execute(update(AppSettings).where(AppSettings.id==1).values(
            atr_smb_host="h", atr_smb_share="s", atr_smb_user="u",
            atr_smb_password_enc=encrypt_credential("p"),
            atr_scan_interval_s=60, atr_auto_mode=auto))
        await db.commit()


async def test_scan_review_creates_draft(client, monkeypatch):
    await _configure(client, auto=False)
    from app.services import atr_fileserver as fs
    monkeypatch.setattr(fs, "list_input_pdfs", lambda cfg: ["LS.pdf"])
    monkeypatch.setattr(fs, "read_input", lambda cfg, name: make_text_pdf(_LS))
    wrote = {}
    monkeypatch.setattr(fs, "write_output", lambda *a: wrote.setdefault("x", 1))
    from app.scheduler import _run_atr_scan
    await _run_atr_scan()
    r = await client.get("/api/atr/deliveries", headers=_auth())
    assert any(d["source_filename"] == "LS.pdf" for d in r.json())
    assert wrote == {}  # review mode: no output written

    # second scan must SKIP the already-linked file
    await _run_atr_scan()
    r = await client.get("/api/atr/deliveries", headers=_auth())
    assert sum(1 for d in r.json() if d["source_filename"] == "LS.pdf") == 1


async def test_scan_auto_writes_and_archives(client, monkeypatch):
    await _configure(client, auto=True)
    from app.services import atr_fileserver as fs
    monkeypatch.setattr(fs, "list_input_pdfs", lambda cfg: ["LS.pdf"])
    monkeypatch.setattr(fs, "read_input", lambda cfg, name: make_text_pdf(_LS))
    seen = {}
    monkeypatch.setattr(fs, "write_output", lambda cfg, name, data: seen.__setitem__(name, 1))
    monkeypatch.setattr(fs, "archive_input", lambda cfg, name: seen.__setitem__("arch", name))
    from app.scheduler import _run_atr_scan
    await _run_atr_scan()
    assert any(n.endswith(".xlsx") for n in seen) and "arch" in seen


def test_reschedule_atr_scan_removes_on_zero():
    from app.scheduler import reschedule_atr_scan, ATR_SCAN_JOB_ID, scheduler
    reschedule_atr_scan(0)
    assert scheduler.get_job(ATR_SCAN_JOB_ID) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_scan.py -v`
Expected: FAIL (`_run_atr_scan` / `reschedule_atr_scan` not defined).

- [ ] **Step 3: Add the scheduler job**

In `backend/app/scheduler.py`, add near the other job ids: `ATR_SCAN_JOB_ID = "atr_scan"`. Add the loader, runner, and reschedule helper:

```python
async def _load_atr_interval() -> int:
    async with AsyncSessionLocal() as session:
        v = (await session.execute(
            select(AppSettings.atr_scan_interval_s).where(AppSettings.id == 1)
        )).scalar_one_or_none()
    return int(v) if v is not None else 0


async def _run_atr_scan() -> None:
    """List new Lieferscheine on the SMB share and process each (Phase C)."""
    import asyncio as _asyncio
    from app.models import AppSettings, AtrDelivery
    from app.services import atr_fileserver as fs
    from app.services.atr_deliver import generate_and_deliver
    from app.services.atr_lieferschein import parse_lieferschein
    from app.services.atr_match import match_positions

    async with AsyncSessionLocal() as session:
        row = (await session.execute(select(AppSettings).where(AppSettings.id == 1))).scalar_one_or_none()
        if row is None or row.atr_scan_interval_s == 0:
            return
        cfg = fs.smb_config_from_settings(row)
        if cfg is None:
            return
        try:
            names = await _asyncio.to_thread(fs.list_input_pdfs, cfg)
        except fs.AtrFileserverError:
            log.warning("atr_scan: list_input_pdfs failed", exc_info=True)
            return
        # names already linked to a scan-origin delivery → skip
        linked = set((await session.execute(
            select(AtrDelivery.source_filename).where(AtrDelivery.origin == "scan")
        )).scalars().all())
        for name in names:
            if name in linked:
                continue
            try:
                raw = await _asyncio.to_thread(fs.read_input, cfg, name)
                parsed = await parse_lieferschein(raw)
                if not parsed.positions:
                    log.warning("atr_scan: no positions in %s; skipping", name)
                    continue
                md = await match_positions(session, parsed, name)
                from app.routers.atr_delivery import _persist_draft  # reuse the draft builder
                delivery = await _persist_draft(session, md)
                delivery.origin = "scan"
                delivery.source_path = f"{cfg.input_path}/{name}"
                await session.commit()
                if row.atr_auto_mode:
                    from sqlalchemy.orm import selectinload
                    d = (await session.execute(
                        select(AtrDelivery).options(selectinload(AtrDelivery.items)).where(AtrDelivery.id == delivery.id)
                    )).scalar_one()
                    await generate_and_deliver(session, d, row)
            except Exception:
                log.exception("atr_scan: failed processing %s", name)
                await session.rollback()


def reschedule_atr_scan(new_interval_s: int) -> None:
    try:
        existing = scheduler.get_job(ATR_SCAN_JOB_ID)
        if new_interval_s <= 0:
            if existing is not None:
                scheduler.remove_job(ATR_SCAN_JOB_ID)
            return
        if existing is None:
            scheduler.add_job(_run_atr_scan, trigger="interval", seconds=new_interval_s,
                              id=ATR_SCAN_JOB_ID, replace_existing=True, max_instances=1,
                              coalesce=True, misfire_grace_time=30)
        else:
            scheduler.reschedule_job(ATR_SCAN_JOB_ID, trigger="interval", seconds=new_interval_s)
    except Exception:
        log.exception("reschedule_atr_scan failed (new_interval_s=%s)", new_interval_s)
```

In the lifespan (where sensor poll is registered), add after the sensor block:

```python
    atr_interval_s = await _load_atr_interval()
    if atr_interval_s > 0:
        scheduler.add_job(_run_atr_scan, trigger="interval", seconds=atr_interval_s,
                          id=ATR_SCAN_JOB_ID, replace_existing=True, max_instances=1,
                          coalesce=True, misfire_grace_time=30)
```

> `_persist_draft` is reused from `app.routers.atr_delivery`; it is module-level there. If importing it creates a cycle, move `_persist_draft` into a small helper module `app/services/atr_draft.py` and import from both — but a function-local import inside `_run_atr_scan` (as written) avoids the cycle.

- [ ] **Step 4: Run the tests**

Run: `docker compose exec -T -e POSTGRES_DB=acm_test api pytest tests/test_atr_scan.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/app/scheduler.py backend/tests/test_atr_scan.py
git commit -m "feat(atr): atr_scan scheduler job (review/auto) + reschedule_atr_scan"
```

---

# Wave 3 — Settings UI

## Task 8: Frontend settings fields + i18n

**Files:**
- Modify: `frontend/src/lib/api.ts` (Settings + SettingsUpdatePayload), add `testAtrFileserver`
- Modify: `frontend/src/locales/en.json`, `de.json`

**Interfaces:**
- Produces: `Settings` atr fields, `SettingsUpdatePayload` atr fields, `testAtrFileserver(): Promise<{ok:boolean;error:string|null}>`.

- [ ] **Step 1: Extend the API types**

In `frontend/src/lib/api.ts`, add to the `Settings` interface:

```typescript
  atr_smb_host: string | null;
  atr_smb_share: string | null;
  atr_smb_domain: string | null;
  atr_smb_user: string | null;
  atr_smb_has_password: boolean;
  atr_input_path: string | null;
  atr_output_path: string | null;
  atr_archive_path: string | null;
  atr_scan_interval_s: number;
  atr_auto_mode: boolean;
```

and to `SettingsUpdatePayload` (all optional):

```typescript
  atr_smb_host?: string | null;
  atr_smb_share?: string | null;
  atr_smb_domain?: string | null;
  atr_smb_user?: string | null;
  atr_smb_password?: string;
  atr_input_path?: string | null;
  atr_output_path?: string | null;
  atr_archive_path?: string | null;
  atr_scan_interval_s?: number;
  atr_auto_mode?: boolean;
```

and add a fetcher:

```typescript
export async function testAtrFileserver(): Promise<{ ok: boolean; error: string | null }> {
  return apiClient<{ ok: boolean; error: string | null }>("/api/atr/fileserver/test", { method: "POST" });
}
```

- [ ] **Step 2: Add flat i18n keys**

Add to `frontend/src/locales/en.json` (flat, `keySeparator` is false):

```json
"atr.fileserver.heading": "ATR fileserver",
"atr.fileserver.host": "SMB host",
"atr.fileserver.share": "Share",
"atr.fileserver.domain": "AD domain",
"atr.fileserver.user": "Service account user",
"atr.fileserver.password": "Service account password",
"atr.fileserver.password_set": "(password set — leave blank to keep)",
"atr.fileserver.input_path": "Input directory",
"atr.fileserver.output_path": "Output directory",
"atr.fileserver.archive_path": "Archive directory",
"atr.fileserver.interval": "Scan interval (seconds, 0 = off)",
"atr.fileserver.auto_mode": "Auto mode (generate without review)",
"atr.fileserver.test": "Test connection",
"atr.fileserver.test_ok": "Connection OK",
"atr.fileserver.save": "Save",
```

And the German mirror in `de.json`: `"atr.fileserver.heading": "ATR-Dateiserver"`, `"atr.fileserver.host": "SMB-Host"`, `"atr.fileserver.share": "Freigabe"`, `"atr.fileserver.domain": "AD-Domäne"`, `"atr.fileserver.user": "Servicekonto-Benutzer"`, `"atr.fileserver.password": "Servicekonto-Passwort"`, `"atr.fileserver.password_set": "(Passwort gesetzt — leer lassen zum Beibehalten)"`, `"atr.fileserver.input_path": "Eingangsverzeichnis"`, `"atr.fileserver.output_path": "Ausgangsverzeichnis"`, `"atr.fileserver.archive_path": "Archivverzeichnis"`, `"atr.fileserver.interval": "Scan-Intervall (Sekunden, 0 = aus)"`, `"atr.fileserver.auto_mode": "Automatik (ohne Prüfung generieren)"`, `"atr.fileserver.test": "Verbindung testen"`, `"atr.fileserver.test_ok": "Verbindung OK"`, `"atr.fileserver.save": "Speichern"`.

- [ ] **Step 3: Verify**

```bash
cd frontend && node -e "JSON.parse(require('fs').readFileSync('src/locales/en.json','utf8'));JSON.parse(require('fs').readFileSync('src/locales/de.json','utf8'));console.log('json ok')"
cd frontend && npx tsc --noEmit
```
Expected: `json ok`, tsc clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/locales/en.json frontend/src/locales/de.json
git commit -m "feat(atr): frontend settings types + i18n for fileserver"
```

---

## Task 9: ATR settings page

**Files:**
- Create: `frontend/src/pages/AtrSettingsPage.tsx`
- Modify: `frontend/src/App.tsx`, `frontend/src/components/SettingsSectionPicker.tsx`
- Test: `frontend/src/pages/__tests__/AtrSettingsPage.test.tsx`

**Interfaces:**
- Consumes: `fetchSettings`, `updateSettings`, `testAtrFileserver`.

- [ ] **Step 1: Write the page**

```tsx
// frontend/src/pages/AtrSettingsPage.tsx
import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import {
  fetchSettings, updateSettings, testAtrFileserver,
  type Settings, type SettingsUpdatePayload,
} from "@/lib/api";

export function AtrSettingsPage() {
  const { t } = useTranslation();
  const qc = useQueryClient();
  const { data } = useQuery({ queryKey: ["settings"], queryFn: fetchSettings });
  const [d, setD] = useState<Partial<Settings>>({});
  const [pw, setPw] = useState("");
  useEffect(() => { if (data) setD(data); }, [data]);

  async function save() {
    if (!data) return;
    const body: SettingsUpdatePayload = {
      color_primary: data.color_primary, color_accent: data.color_accent,
      color_background: data.color_background, color_foreground: data.color_foreground,
      color_muted: data.color_muted, color_destructive: data.color_destructive,
      app_name: data.app_name,
      atr_smb_host: d.atr_smb_host ?? null, atr_smb_share: d.atr_smb_share ?? null,
      atr_smb_domain: d.atr_smb_domain ?? null, atr_smb_user: d.atr_smb_user ?? null,
      atr_input_path: d.atr_input_path ?? null, atr_output_path: d.atr_output_path ?? null,
      atr_archive_path: d.atr_archive_path ?? null,
      atr_scan_interval_s: Number(d.atr_scan_interval_s ?? 0),
      atr_auto_mode: !!d.atr_auto_mode,
      ...(pw ? { atr_smb_password: pw } : {}),
    };
    try {
      await updateSettings(body);
      toast.success(t("atr.fileserver.save")); setPw("");
      qc.invalidateQueries({ queryKey: ["settings"] });
    } catch (e) { toast.error(String(e)); }
  }
  async function test() {
    try {
      const r = await testAtrFileserver();
      r.ok ? toast.success(t("atr.fileserver.test_ok")) : toast.error(r.error ?? "failed");
    } catch (e) { toast.error(String(e)); }
  }

  if (!data) return <div className="p-6">…</div>;
  const text = (k: keyof Settings, label: string) => (
    <label className="flex flex-col text-sm">
      <span className="text-muted-foreground">{t(label)}</span>
      <input className="border rounded px-2 py-1" value={(d[k] as string) ?? ""}
        onChange={(e) => setD((s) => ({ ...s, [k]: e.target.value }))} />
    </label>
  );

  return (
    <div className="max-w-2xl mx-auto px-6 py-6">
      <h1 className="text-xl font-semibold mb-4">{t("atr.fileserver.heading")}</h1>
      <div className="grid grid-cols-2 gap-3">
        {text("atr_smb_host", "atr.fileserver.host")}
        {text("atr_smb_share", "atr.fileserver.share")}
        {text("atr_smb_domain", "atr.fileserver.domain")}
        {text("atr_smb_user", "atr.fileserver.user")}
        <label className="flex flex-col text-sm">
          <span className="text-muted-foreground">{t("atr.fileserver.password")}</span>
          <input type="password" className="border rounded px-2 py-1" value={pw}
            placeholder={data.atr_smb_has_password ? t("atr.fileserver.password_set") : ""}
            onChange={(e) => setPw(e.target.value)} />
        </label>
        {text("atr_input_path", "atr.fileserver.input_path")}
        {text("atr_output_path", "atr.fileserver.output_path")}
        {text("atr_archive_path", "atr.fileserver.archive_path")}
        <label className="flex flex-col text-sm">
          <span className="text-muted-foreground">{t("atr.fileserver.interval")}</span>
          <input type="number" className="border rounded px-2 py-1"
            value={String(d.atr_scan_interval_s ?? 0)}
            onChange={(e) => setD((s) => ({ ...s, atr_scan_interval_s: Number(e.target.value) }))} />
        </label>
        <label className="flex items-center gap-2 text-sm mt-5">
          <input type="checkbox" checked={!!d.atr_auto_mode}
            onChange={(e) => setD((s) => ({ ...s, atr_auto_mode: e.target.checked }))} />
          {t("atr.fileserver.auto_mode")}
        </label>
      </div>
      <div className="mt-4 flex gap-3">
        <button className="px-4 py-2 bg-blue-600 text-white rounded" onClick={save}>{t("atr.fileserver.save")}</button>
        <button className="px-4 py-2 border rounded" onClick={test}>{t("atr.fileserver.test")}</button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Wire the route + settings picker**

In `frontend/src/App.tsx`: import `AtrSettingsPage` and add a route (before `/settings`): `<Route path="/settings/atr" component={AtrSettingsPage} />`.
In `frontend/src/components/SettingsSectionPicker.tsx`: add an `atr` option (value `atr`, label `t("atr.fileserver.heading")`) to the existing section `<Select>` so operators can navigate to it (mirror the existing `general`/`hr`/`sensors` entries).

- [ ] **Step 3: Write the test**

```tsx
// frontend/src/pages/__tests__/AtrSettingsPage.test.tsx
import type { ReactNode } from "react";
import { render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import { describe, it, expect, vi, beforeEach } from "vitest";
import i18n from "@/i18n";
import { AtrSettingsPage } from "../AtrSettingsPage";
import * as api from "@/lib/api";

vi.mock("@/lib/api");

function wrap(ui: ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}><I18nextProvider i18n={i18n}>{ui}</I18nextProvider></QueryClientProvider>;
}

describe("AtrSettingsPage", () => {
  beforeEach(() => vi.resetAllMocks());
  it("renders fileserver fields from settings", async () => {
    vi.mocked(api.fetchSettings).mockResolvedValue({
      color_primary: "x", color_accent: "x", color_background: "x", color_foreground: "x",
      color_muted: "x", color_destructive: "x", app_name: "A", logo_url: null, logo_updated_at: null,
      personio_has_credentials: false, personio_sync_interval_h: 168, personio_sick_leave_type_id: [],
      personio_production_dept: [], personio_skill_attr_key: [], target_overtime_ratio: null,
      target_sick_leave_ratio: null, target_fluctuation: null, target_revenue_per_employee: null,
      target_sales_erstkontakte: null, target_sales_interessenten: null, target_sales_besuche: null,
      target_sales_angebote_eur: null, target_sales_orders_per_rep_eur: null,
      sensor_poll_interval_s: 60, sensor_temperature_min: null, sensor_temperature_max: null,
      sensor_humidity_min: null, sensor_humidity_max: null, worldcup_has_api_key: false,
      worldcup_refresh_seconds: 60,
      atr_smb_host: "acm_file", atr_smb_share: "Dateiablage", atr_smb_domain: "ACME",
      atr_smb_user: "svc", atr_smb_has_password: true, atr_input_path: "0900 - EDV/Test_ATR/Input",
      atr_output_path: "0900 - EDV/Test_ATR/Output", atr_archive_path: "0900 - EDV/Test_ATR/Archiv",
      atr_scan_interval_s: 0, atr_auto_mode: false,
    } as unknown as api.Settings);
    render(wrap(<AtrSettingsPage />));
    await waitFor(() => expect(screen.getByDisplayValue("acm_file")).toBeInTheDocument());
    expect(screen.getByDisplayValue("Dateiablage")).toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Run the test + tsc**

Run: `cd frontend && npx vitest run src/pages/__tests__/AtrSettingsPage.test.tsx && npx tsc --noEmit`
Expected: PASS, tsc clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/AtrSettingsPage.tsx frontend/src/App.tsx frontend/src/components/SettingsSectionPicker.tsx frontend/src/pages/__tests__/AtrSettingsPage.test.tsx
git commit -m "feat(atr): /settings/atr fileserver settings page"
```

---

## Acceptance check (manual — needs the real AD service account)

On `/settings/atr`, enter the AD service account for `\\acm_file\Dateiablage` + the Input/Output/Archiv paths, click **Test connection** (expect OK). Set review mode + a 60s interval and Save. Drop `LIEFERSCHEIN_10005_20189798.pdf` into the Input folder; within ~60s a draft delivery appears in `/atr/deliveries`. Open it, Generate → confirm `.xlsx/.pdf/.docx` appear in Output and the source PDF moves to Archiv. Switch to auto mode → the 3 files appear without a manual Generate.

## Self-Review

- **Spec coverage:** settings columns + encryption + write-only password (T1, T3) ✓; SMB service with `to_thread` (T2) ✓; test-connection (T3) ✓; shared deliver routine, scan-origin write+archive (T4) ✓; Generate delegates to it (T5) ✓; input-files via SMB + origin/source_path (T6) ✓; scheduler scan, review/auto, skip-linked, per-file isolation, reschedule (T7) ✓; settings UI + test button + i18n (T8, T9) ✓; admin-gate (T3) ✓; acceptance check ✓.
- **Placeholder scan:** none (the one leftover `headers_extra` kwarg in a T3 test is explicitly called out to delete).
- **Type consistency:** `SmbConfig`/`smb_config_from_settings`/`list_input_pdfs`/`read_input`/`write_output`/`archive_input`/`test_connection`, `generate_and_deliver`, `reschedule_atr_scan`/`ATR_SCAN_JOB_ID`/`_run_atr_scan`, and the TS `Settings`/`SettingsUpdatePayload` atr fields + `testAtrFileserver` are consistent across tasks.
- **Risk flagged:** the SMB layer is mock-only in CI; the real share is validated solely by the manual acceptance check + Test-connection button (no `\\acm_file` access in CI).
```
