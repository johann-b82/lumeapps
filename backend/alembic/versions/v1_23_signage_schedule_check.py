"""Phase 68 MIG-SIGN-02: CHECK (start_hhmm < end_hhmm) on signage_schedules

Revision ID: v1_23_signage_schedule_check
Revises: v1_22_signage_notify_triggers
Create Date: 2026-04-25

Plan 68-02 declares the canonical CHECK-constraint name as
``ck_signage_schedules_start_before_end``. Phase 51 (v1_18_signage_schedules)
already created an equivalent CHECK with the older name
``ck_signage_schedules_no_midnight_span``. This migration RENAMES that
existing constraint to the canonical name so both layers (DB CHECK + Directus
Flow) reference the same identifier going forward, without introducing a
redundant duplicate constraint on the same predicate.

Rationale (deviation from plan, Rule 1 / Rule 2):
- Adding a second CHECK with identical predicate would be a structural bug
  (two constraints firing on every INSERT/UPDATE for the same condition).
- Renaming preserves the plan's must_haves truths #1 (DB rejects with
  sqlstate 23514) and the artifact key_link pattern (start_hhmm < end_hhmm)
  while producing the constraint name the Directus error mapper can rely on.

If the older constraint is somehow absent (e.g. a partial Alembic state from
an aborted earlier upgrade), the upgrade falls back to ADD CONSTRAINT so the
migration is idempotent against either starting state.
"""
from alembic import op

revision = "v1_23_signage_schedule_check"
down_revision = "v1_22_signage_notify_triggers"
branch_labels = None
depends_on = None

OLD_CONSTRAINT_NAME = "ck_signage_schedules_no_midnight_span"
NEW_CONSTRAINT_NAME = "ck_signage_schedules_start_before_end"


def upgrade() -> None:
    # Idempotent upgrade: rename the v1.18 constraint if present, else add it.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = '{OLD_CONSTRAINT_NAME}'
            ) THEN
                ALTER TABLE signage_schedules
                    RENAME CONSTRAINT {OLD_CONSTRAINT_NAME}
                                  TO {NEW_CONSTRAINT_NAME};
            ELSIF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = '{NEW_CONSTRAINT_NAME}'
            ) THEN
                ALTER TABLE signage_schedules
                    ADD CONSTRAINT {NEW_CONSTRAINT_NAME}
                    CHECK (start_hhmm < end_hhmm);
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    # Symmetric reverse: rename back if the new constraint is present.
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = '{NEW_CONSTRAINT_NAME}'
            ) THEN
                ALTER TABLE signage_schedules
                    RENAME CONSTRAINT {NEW_CONSTRAINT_NAME}
                                  TO {OLD_CONSTRAINT_NAME};
            END IF;
        END
        $$;
        """
    )
