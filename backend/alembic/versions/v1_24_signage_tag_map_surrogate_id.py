"""Quick task 260427-gwf: surrogate id PK on signage tag-map junction tables

Revision ID: v1_24_tag_map_surrogate_id
Revises: v1_23_signage_schedule_check
Create Date: 2026-04-27

NOTE: ``alembic_version.version_num`` is ``VARCHAR(32)``; the revision id
below is intentionally shortened (vs the file name) to fit within that
limit. The file name keeps the longer descriptive form for readability.

Directus 11 only introspects collections that have a single-column primary
key. ``signage_playlist_tag_map`` and ``signage_device_tag_map`` currently
use composite PKs ``(playlist_id, tag_id)`` / ``(device_id, tag_id)``, so
Directus silently drops them from its schema with a "doesn't have a primary
key column" WARN at boot. That blocks the v1.22 carry-forward
``schema:null`` collection metadata work (Phase 69 P06 / Phase 70 P05
xfails) and any future Directus-side admin/permission rows for tag mappings.

Strategy (per-table, applied to both junction tables):

1. ADD UNIQUE constraint on the original pair FIRST (so the no-duplicate-
   pairs invariant is never temporarily relaxed during the swap).
2. DROP the existing composite PK by its known name
   (``pk_signage_playlist_tag_map`` / ``pk_signage_device_tag_map``).
3. ADD ``id`` column as ``SERIAL PRIMARY KEY`` (32-bit, matching
   ``signage_device_tags.id`` / ``signage_playlists.id``-style sizing).

``downgrade()`` reverses cleanly in reverse order: drop ``id`` (its implicit
PK + sequence drop with the column), drop the unique, restore the original
composite PK with its original name.

All DDL is wrapped in idempotent ``DO $$`` guards (``IF (NOT) EXISTS``
against ``pg_constraint`` / ``information_schema.columns``) so re-running
upgrade/downgrade against partial states is safe — same pattern as
``v1_23_signage_schedule_check``.

The ``AFTER INSERT/UPDATE/DELETE`` triggers on each table reference the
pair columns (``playlist_id`` / ``device_id`` / ``tag_id``) by name via
``signage_notify()`` — they do NOT depend on the PK shape, so no trigger
DDL is touched here. LISTEN/NOTIFY semantics are preserved.
"""
from alembic import op

revision = "v1_24_tag_map_surrogate_id"
down_revision = "v1_23_signage_schedule_check"
branch_labels = None
depends_on = None


# (table, pair_col_a, pair_col_b, original_composite_pk_name)
TARGETS = [
    (
        "signage_playlist_tag_map",
        "playlist_id",
        "tag_id",
        "pk_signage_playlist_tag_map",
    ),
    (
        "signage_device_tag_map",
        "device_id",
        "tag_id",
        "pk_signage_device_tag_map",
    ),
]


def upgrade() -> None:
    for table, col_a, col_b, pk_name in TARGETS:
        unique_name = f"uq_{table}_pair"

        # 1. Add UNIQUE on the original pair BEFORE dropping the composite PK
        #    so the no-duplicate-pairs invariant never lapses.
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = '{unique_name}'
                ) THEN
                    ALTER TABLE {table}
                        ADD CONSTRAINT {unique_name}
                        UNIQUE ({col_a}, {col_b});
                END IF;
            END
            $$;
            """
        )

        # 2. Drop the composite PK (by its known name).
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = '{pk_name}'
                      AND contype = 'p'
                ) THEN
                    ALTER TABLE {table}
                        DROP CONSTRAINT {pk_name};
                END IF;
            END
            $$;
            """
        )

        # 3. Add surrogate ``id`` SERIAL PRIMARY KEY (idempotent on the
        #    column existence — re-runs no-op).
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = '{table}'
                      AND column_name = 'id'
                ) THEN
                    ALTER TABLE {table}
                        ADD COLUMN id SERIAL PRIMARY KEY;
                END IF;
            END
            $$;
            """
        )


def downgrade() -> None:
    for table, col_a, col_b, pk_name in TARGETS:
        unique_name = f"uq_{table}_pair"

        # 1. Drop the surrogate id column (implicit PK + sequence drop with it).
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.columns
                    WHERE table_name = '{table}'
                      AND column_name = 'id'
                ) THEN
                    ALTER TABLE {table}
                        DROP COLUMN id;
                END IF;
            END
            $$;
            """
        )

        # 2. Drop the UNIQUE constraint on the original pair.
        op.execute(
            f"""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = '{unique_name}'
                ) THEN
                    ALTER TABLE {table}
                        DROP CONSTRAINT {unique_name};
                END IF;
            END
            $$;
            """
        )

        # 3. Restore the composite PRIMARY KEY with its original name.
        op.execute(
            f"""
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint
                    WHERE conname = '{pk_name}'
                ) THEN
                    ALTER TABLE {table}
                        ADD CONSTRAINT {pk_name}
                        PRIMARY KEY ({col_a}, {col_b});
                END IF;
            END
            $$;
            """
        )
