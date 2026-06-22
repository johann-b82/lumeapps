"""v1.61: WM-Tippspiel — tippspiel_tips schema + extend upload_batches.kind

One row per (match, department) score tip. Team names are stored as the
football-data feed names (mapped from the German Excel) so scoring can join a
tip to its real result. Idempotency key ``(home_team, away_team, department)``.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision = "v1_62_tippspiel"
down_revision = "v1_61_worldcup_playlist"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "tippspiel_tips",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "upload_batch_id",
            sa.Integer(),
            sa.ForeignKey("upload_batches.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gruppe", sa.String(length=10), nullable=True),
        sa.Column("home_team", sa.String(length=80), nullable=False),
        sa.Column("away_team", sa.String(length=80), nullable=False),
        sa.Column("match_date", sa.Date(), nullable=True),
        sa.Column("department", sa.String(length=80), nullable=False),
        sa.Column("tip_home", sa.Integer(), nullable=False),
        sa.Column("tip_away", sa.Integer(), nullable=False),
        sa.Column("raw", JSONB(), nullable=True),
        sa.UniqueConstraint(
            "home_team", "away_team", "department",
            name="uq_tippspiel_tips_match_dept",
        ),
    )
    op.create_index(
        "ix_tippspiel_tips_match", "tippspiel_tips", ["home_team", "away_team"]
    )

    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality','interessenten','offers',"
        "'revenues','auftraege','deliveries','delivery_reliability','tippspiel')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_upload_batches_kind", "upload_batches", type_="check")
    op.create_check_constraint(
        "ck_upload_batches_kind",
        "upload_batches",
        "kind IN ('orders','contacts','quality','interessenten','offers',"
        "'revenues','auftraege','deliveries','delivery_reliability')",
    )
    op.drop_index("ix_tippspiel_tips_match", table_name="tippspiel_tips")
    op.drop_table("tippspiel_tips")
