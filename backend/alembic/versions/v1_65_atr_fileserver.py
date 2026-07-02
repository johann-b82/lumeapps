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
# Discovered deployment defaults (Z: -> \\acm_file\Dateiablage; AD domain ACM).
# FQDN, not the NetBIOS name 'acm_file', because the Linux container cannot
# resolve NetBIOS (verified) but resolves 'acm_file.acm.local' / 192.9.200.18.
_DEFAULT_HOST = "acm_file.acm.local"
_DEFAULT_SHARE = "Dateiablage"
_DEFAULT_DOMAIN = "ACM"


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

    # Seed default paths + the discovered host/share/domain on the singleton row.
    op.execute(
        sa.text(
            "UPDATE app_settings SET atr_input_path=:i, atr_output_path=:o, atr_archive_path=:a, "
            "atr_smb_host=:h, atr_smb_share=:s, atr_smb_domain=:d WHERE id=1"
        ).bindparams(i=_DEFAULT_INPUT, o=_DEFAULT_OUTPUT, a=_DEFAULT_ARCHIVE,
                     h=_DEFAULT_HOST, s=_DEFAULT_SHARE, d=_DEFAULT_DOMAIN)
    )


def downgrade() -> None:
    for col in ("output_written_at", "source_path", "origin"):
        op.drop_column("atr_delivery", col)
    for col in ("atr_auto_mode", "atr_scan_interval_s", "atr_archive_path", "atr_output_path",
                "atr_input_path", "atr_smb_password_enc", "atr_smb_user", "atr_smb_domain",
                "atr_smb_share", "atr_smb_host"):
        op.drop_column("app_settings", col)
