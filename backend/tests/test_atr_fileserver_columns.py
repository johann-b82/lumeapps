from app.models import AppSettings, AtrDelivery


def test_appsettings_atr_columns():
    cols = {c.name for c in AppSettings.__table__.columns}
    assert {"atr_smb_host", "atr_smb_share", "atr_smb_domain", "atr_smb_user",
            "atr_smb_password_enc", "atr_input_path", "atr_output_path",
            "atr_archive_path", "atr_scan_interval_s", "atr_auto_mode"} <= cols


def test_delivery_origin_columns():
    cols = {c.name for c in AtrDelivery.__table__.columns}
    assert {"origin", "source_path", "output_written_at"} <= cols
