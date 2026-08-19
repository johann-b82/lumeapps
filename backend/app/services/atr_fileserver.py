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


def smb_credentials_from_settings(row) -> SmbConfig | None:
    """Like smb_config_from_settings but only requires the connection credentials
    (host/share/domain/user/password) — the scan Input/Output/Archiv paths are
    left empty. Used by the "save to server" targets, which carry their own paths."""
    if not (row.atr_smb_host and row.atr_smb_share and row.atr_smb_user
            and row.atr_smb_password_enc):
        return None
    return SmbConfig(
        host=row.atr_smb_host, share=row.atr_smb_share, domain=row.atr_smb_domain,
        user=row.atr_smb_user, password=decrypt_credential(row.atr_smb_password_enc),
        input_path="", output_path="", archive_path="",
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


def _dedupe_name(cfg: SmbConfig, rel_path: str, filename: str) -> str:
    """Return `filename`, or `name (n).ext` if it already exists in `rel_path`."""
    existing = set(smbclient.listdir(_unc(cfg.host, cfg.share, rel_path)))
    if filename not in existing:
        return filename
    stem, dot, ext = filename.rpartition(".")
    base, suffix = (stem, f".{ext}") if dot else (filename, "")
    n = 1
    while f"{base} ({n}){suffix}" in existing:
        n += 1
    return f"{base} ({n}){suffix}"


def write_file(cfg: SmbConfig, rel_path: str, filename: str, data: bytes) -> str:
    """Write `data` to `\\host\share\rel_path\filename`, creating the folder tree
    (e.g. year / calendar-week) as needed. If the file already exists, append a
    running ` (n)` instead of overwriting. Returns the actual filename written."""
    try:
        _register(cfg)
        smbclient.makedirs(_unc(cfg.host, cfg.share, rel_path), exist_ok=True)
        target = _dedupe_name(cfg, rel_path, filename)
        with smbclient.open_file(_unc(cfg.host, cfg.share, rel_path, target), mode="wb") as fh:
            fh.write(data)
        return target
    except Exception as exc:  # noqa: BLE001
        raise AtrFileserverError(f"write_file failed for {filename}: {exc}") from exc


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
