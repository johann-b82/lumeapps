"""v1.82: E-Mail background module — Office 365 (Microsoft Graph) config

Adds the shared e-mail/notification service configuration to the ``app_settings``
singleton. The service sends mail via the Microsoft Graph API using the
client-credentials OAuth flow, so we store the Azure/Entra app-registration
identifiers plus the sender identity. The client secret is Fernet-encrypted
BYTEA — same pattern as ``personio_client_secret_enc`` / ``worldcup_api_key_enc``
/ ``atr_smb_password_enc``.

``email_enabled`` is a master switch so other modules can cheaply check whether
mailing is turned on before building a message.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "v1_82_email_office365"
down_revision = "v1_81_inspection_rsc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("app_settings", sa.Column("email_tenant_id", sa.String(128), nullable=True))
    op.add_column("app_settings", sa.Column("email_client_id", sa.String(128), nullable=True))
    op.add_column("app_settings", sa.Column("email_client_secret_enc", postgresql.BYTEA, nullable=True))
    op.add_column("app_settings", sa.Column("email_sender_address", sa.String(320), nullable=True))
    op.add_column("app_settings", sa.Column("email_sender_name", sa.String(200), nullable=True))
    op.add_column(
        "app_settings",
        sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("app_settings", "email_enabled")
    op.drop_column("app_settings", "email_sender_name")
    op.drop_column("app_settings", "email_sender_address")
    op.drop_column("app_settings", "email_client_secret_enc")
    op.drop_column("app_settings", "email_client_id")
    op.drop_column("app_settings", "email_tenant_id")
