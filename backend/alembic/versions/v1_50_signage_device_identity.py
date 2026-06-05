"""v1.50: signage_devices identity columns (mac_address, hostname, ip_address)

Pi sidecar reports these in the heartbeat payload so admins can identify
a kiosk by network identity in the device list. All three are nullable —
older sidecars that don't send them (or the browser fallback heartbeat
which can't know them) just don't update those fields.

Widths:
    mac_address VARCHAR(17)  — `aa:bb:cc:dd:ee:ff`
    hostname    VARCHAR(253) — RFC 1035 max DNS name length
    ip_address  VARCHAR(45)  — fits IPv6 (`xxxx:xxxx:...`) with room to spare
"""
from alembic import op
import sqlalchemy as sa


revision = "v1_50_signage_device_identity"
down_revision = "v1_49_quality_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "signage_devices",
        sa.Column("mac_address", sa.String(length=17), nullable=True),
    )
    op.add_column(
        "signage_devices",
        sa.Column("hostname", sa.String(length=253), nullable=True),
    )
    op.add_column(
        "signage_devices",
        sa.Column("ip_address", sa.String(length=45), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("signage_devices", "ip_address")
    op.drop_column("signage_devices", "hostname")
    op.drop_column("signage_devices", "mac_address")
