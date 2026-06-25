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
