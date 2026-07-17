"""v1.83: E-Mail background module — Office 365 (Microsoft Graph) config

Adds the shared e-mail/notification service configuration to the ``app_settings``
singleton. The service can send mail via the Microsoft Graph API in two modes:

- ``app`` (client-credentials): Azure app-registration + ``Mail.Send`` application
  permission + admin consent; sends from ``email_sender_address`` via
  ``/users/{sender}/sendMail``. Uses ``email_client_secret_enc``.
- ``delegated`` (device-code): the admin signs in interactively with their own
  M365 account and self-consents to delegated ``Mail.Send`` (no admin consent,
  no application permission); sends as the signed-in user via ``/me/sendMail``.
  A rotating refresh token is stored encrypted in
  ``email_delegated_refresh_token_enc``; the signed-in UPN in
  ``email_delegated_account``.

``email_auth_mode`` selects the active mode ('app' | 'delegated'). Secrets/tokens
are Fernet-encrypted BYTEA — same pattern as the other credential columns.
``email_enabled`` is a master switch so other modules can cheaply check whether
mailing is turned on before building a message.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "v1_83_email_office365"
# Prod is already at v1_82_maintenance (Wartung module, deployed 2026-07-15), so
# this migration chains after it — NOT after v1_81 — to keep a single linear
# head. The v1_82_maintenance file lives on the maintenance branch / main; this
# branch must be merged on top of it (see docs/modules/email.md).
down_revision = "v1_82_maintenance"
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
    # Auth mode + delegated (device-code) fields.
    op.add_column(
        "app_settings",
        sa.Column("email_auth_mode", sa.String(16), nullable=False, server_default="app"),
    )
    op.add_column("app_settings", sa.Column("email_delegated_refresh_token_enc", postgresql.BYTEA, nullable=True))
    op.add_column("app_settings", sa.Column("email_delegated_account", sa.String(320), nullable=True))


def downgrade() -> None:
    op.drop_column("app_settings", "email_delegated_account")
    op.drop_column("app_settings", "email_delegated_refresh_token_enc")
    op.drop_column("app_settings", "email_auth_mode")
    op.drop_column("app_settings", "email_enabled")
    op.drop_column("app_settings", "email_sender_name")
    op.drop_column("app_settings", "email_sender_address")
    op.drop_column("app_settings", "email_client_secret_enc")
    op.drop_column("app_settings", "email_client_id")
    op.drop_column("app_settings", "email_tenant_id")
