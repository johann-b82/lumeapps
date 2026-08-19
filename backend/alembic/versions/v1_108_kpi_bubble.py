"""v1.108: KPI-Bubble — verortete Bewertung auf dem Chart.

Erweitert ``kpi_comment`` um Bubble-Felder: eine fortlaufende ``number`` je KPI
und eine normierte Region (rx/ry/rw/rh, 0..1) relativ zum Chart-Container — wie
die FAIR-Balloons, nur auf dem KPI-Chart statt auf einer Zeichnung. Ein
Kommentar ohne Region bleibt gültig (reiner Kommentar ohne Bubble).

Revision ID: v1_108_kpi_bubble
Revises: v1_107_kpi_review
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "v1_108_kpi_bubble"
down_revision = "v1_107_kpi_review"
branch_labels = None
depends_on = None

_COORD = sa.Numeric(9, 6, asdecimal=False)


def upgrade() -> None:
    op.add_column("kpi_comment", sa.Column("number", sa.Integer(), nullable=True))
    op.add_column("kpi_comment", sa.Column("region_x", _COORD, nullable=True))
    op.add_column("kpi_comment", sa.Column("region_y", _COORD, nullable=True))
    op.add_column("kpi_comment", sa.Column("region_w", _COORD, nullable=True))
    op.add_column("kpi_comment", sa.Column("region_h", _COORD, nullable=True))


def downgrade() -> None:
    op.drop_column("kpi_comment", "region_h")
    op.drop_column("kpi_comment", "region_w")
    op.drop_column("kpi_comment", "region_y")
    op.drop_column("kpi_comment", "region_x")
    op.drop_column("kpi_comment", "number")
