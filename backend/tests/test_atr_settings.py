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


async def test_fileserver_test_unconfigured(client):
    r = await client.post("/api/atr/fileserver/test",
                          headers={"Authorization": f"Bearer {mint(ADMIN_UUID)}"})
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False and body["error"]
