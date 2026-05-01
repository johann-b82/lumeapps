"""v1.39: sensors.chart_color (per-sensor chart color)

Revision ID: v1_39_sensor_chart_color
Revises: v1_24_tag_map_surrogate_id
Create Date: 2026-05-01

User feedback on /sensors: the time-series chart auto-assigns colors per
sensor by index (`sensorPalette[i % palette.length]`), so the same physical
sensor can change color when another sensor is added before it. Add an
optional `chart_color` column so the operator can pin a color per sensor
on the settings page; the chart prefers the explicit value and falls back
to the palette index for sensors that have NULL.

Format: `#rrggbb` 7-char hex string. Validation lives in the Pydantic
schema (regex) and on the frontend ColorPicker. NULL is the explicit
"use the palette" sentinel — never store a default.
"""
from alembic import op
import sqlalchemy as sa


revision = "v1_39_sensor_chart_color"
down_revision = "v1_24_tag_map_surrogate_id"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sensors",
        sa.Column("chart_color", sa.String(length=7), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("sensors", "chart_color")
