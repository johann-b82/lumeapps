"""v1.15 Sensor Monitor schema — sensors, sensor_readings, sensor_poll_log + app_settings extensions + seed

Creates three new tables:
  - sensors (config, 1 row per physical device; community is BYTEA Fernet ciphertext)
  - sensor_readings (one row per successful poll; UNIQUE(sensor_id, recorded_at) for
    ON CONFLICT DO NOTHING dedupe; per-table autovacuum tuned for insert-heavy workload)
  - sensor_poll_log (one row per poll attempt — success OR failure; separates liveness
    from data per PITFALLS M-4)

Extends app_settings (singleton) with:
  - sensor_poll_interval_s INT NOT NULL DEFAULT 60
  - sensor_temperature_min/max NUMERIC(8,3) NULL
  - sensor_humidity_min/max    NUMERIC(8,3) NULL

Seeds one Produktion sensor row (192.9.201.27, OIDs from reference config.yaml) with
Fernet-encrypted community string so the scheduler has work from first tick.

Round-trip tested: upgrade -> downgrade -1 -> upgrade head on fresh DB succeeds.

Revision ID: v1_15_sensor
Revises: a1b2c3d4e5f7
Create Date: 2026-04-17
"""
import os
from decimal import Decimal

import sqlalchemy as sa
from alembic import op
from cryptography.fernet import Fernet

revision = "v1_15_sensor"
down_revision = "a1b2c3d4e5f7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- sensors ---
    op.create_table(
        "sensors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("host", sa.String(255), nullable=False),
        sa.Column("port", sa.Integer(), nullable=False, server_default="161"),
        # Fernet ciphertext — never plaintext (PITFALLS C-3). BYTEA matches BYTEA used
        # for personio_client_id_enc (singleton Fernet key shared across features).
        sa.Column("community", sa.LargeBinary(), nullable=False),
        sa.Column("temperature_oid", sa.String(255), nullable=True),
        sa.Column("humidity_oid", sa.String(255), nullable=True),
        sa.Column("temperature_scale", sa.Numeric(10, 4), nullable=False, server_default="1.0"),
        sa.Column("humidity_scale", sa.Numeric(10, 4), nullable=False, server_default="1.0"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # --- sensor_readings ---
    op.create_table(
        "sensor_readings",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "sensor_id",
            sa.Integer(),
            sa.ForeignKey("sensors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("temperature", sa.Numeric(8, 3), nullable=True),
        sa.Column("humidity", sa.Numeric(8, 3), nullable=True),
        sa.Column("error_code", sa.String(100), nullable=True),
        # PITFALLS C-5: dedupe scheduled + manual poll collision via ON CONFLICT
        sa.UniqueConstraint(
            "sensor_id", "recorded_at",
            name="uq_sensor_readings_sensor_recorded_at",
        ),
    )
    # DESC index for "most recent readings first" query pattern (dominant read shape
    # from /api/sensors/{id}/readings and the charts). Postgres 15+ supports DESC on
    # btree — at migration time the backend targets postgres:17-alpine.
    op.execute(
        "CREATE INDEX ix_sensor_readings_sensor_recorded_at_desc "
        "ON sensor_readings (sensor_id, recorded_at DESC)"
    )
    # PITFALLS M-7: per-table autovacuum tuned for insert-heavy workload.
    op.execute(
        "ALTER TABLE sensor_readings SET ("
        "autovacuum_vacuum_scale_factor = 0.05, "
        "autovacuum_analyze_scale_factor = 0.02, "
        "autovacuum_vacuum_insert_scale_factor = 0.1)"
    )

    # --- sensor_poll_log ---
    op.create_table(
        "sensor_poll_log",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column(
            "sensor_id",
            sa.Integer(),
            sa.ForeignKey("sensors.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_kind", sa.String(100), nullable=True),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
    )
    op.execute(
        "CREATE INDEX ix_sensor_poll_log_sensor_attempted_at_desc "
        "ON sensor_poll_log (sensor_id, attempted_at DESC)"
    )

    # --- app_settings extensions ---
    op.add_column(
        "app_settings",
        sa.Column(
            "sensor_poll_interval_s",
            sa.Integer(),
            nullable=False,
            server_default="60",
        ),
    )
    op.add_column(
        "app_settings",
        sa.Column("sensor_temperature_min", sa.Numeric(8, 3), nullable=True),
    )
    op.add_column(
        "app_settings",
        sa.Column("sensor_temperature_max", sa.Numeric(8, 3), nullable=True),
    )
    op.add_column(
        "app_settings",
        sa.Column("sensor_humidity_min", sa.Numeric(8, 3), nullable=True),
    )
    op.add_column(
        "app_settings",
        sa.Column("sensor_humidity_max", sa.Numeric(8, 3), nullable=True),
    )

    # --- seed: default Produktion sensor (community Fernet-encrypted) ---
    # PITFALLS C-3: encrypt the community string before writing. The migration runs
    # inside the same container as the app, so FERNET_KEY is set (same env var as
    # Personio credentials — DO NOT introduce a second key).
    fernet_key = os.environ.get("FERNET_KEY")
    if not fernet_key:
        raise RuntimeError(
            "FERNET_KEY env var is required for the v1.15 sensor seed migration "
            "(used to encrypt the default community string at rest). "
            "This is the same key that encrypts Personio credentials."
        )
    fernet = Fernet(fernet_key.encode() if isinstance(fernet_key, str) else fernet_key)
    community_ct = fernet.encrypt(b"public")

    op.execute(
        sa.text(
            """
            INSERT INTO sensors (
              name, host, port, community,
              temperature_oid, humidity_oid,
              temperature_scale, humidity_scale, enabled
            ) VALUES (
              :name, :host, :port, :community,
              :temp_oid, :hum_oid,
              :temp_scale, :hum_scale, TRUE
            )
            """
        ).bindparams(
            name="Produktion",
            host="192.9.201.27",
            port=161,
            community=community_ct,
            temp_oid="1.3.6.1.4.1.21796.4.9.3.1.5.2",
            hum_oid="1.3.6.1.4.1.21796.4.9.3.1.5.1",
            temp_scale=Decimal("10.0"),
            hum_scale=Decimal("10.0"),
        )
    )


def downgrade() -> None:
    # Drop in reverse dependency order. app_settings columns first (no FK),
    # then child tables (sensor_readings, sensor_poll_log reference sensors.id),
    # then sensors.
    op.drop_column("app_settings", "sensor_humidity_max")
    op.drop_column("app_settings", "sensor_humidity_min")
    op.drop_column("app_settings", "sensor_temperature_max")
    op.drop_column("app_settings", "sensor_temperature_min")
    op.drop_column("app_settings", "sensor_poll_interval_s")

    op.execute("DROP INDEX IF EXISTS ix_sensor_poll_log_sensor_attempted_at_desc")
    op.drop_table("sensor_poll_log")

    op.execute("DROP INDEX IF EXISTS ix_sensor_readings_sensor_recorded_at_desc")
    op.drop_table("sensor_readings")  # UniqueConstraint dropped with the table

    op.drop_table("sensors")
