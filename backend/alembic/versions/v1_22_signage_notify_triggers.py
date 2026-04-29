"""v1.22 signage LISTEN/NOTIFY triggers

Revision ID: v1_22_signage_notify_triggers
Revises: v1_21_signage_calibration
Create Date: 2026-04-24

Six AFTER triggers call shared signage_notify() which emits
pg_notify('signage_change', {table, op, id}). signage_devices UPDATE
trigger is WHEN-gated on name-only (tags live in signage_device_tag_map,
not on signage_devices) so calibration updates (FastAPI-owned SSE path)
never double-fire. Payload is minimal JSON, well under the 8000-byte
pg_notify cap. Channel name: 'signage_change'.

Preflight: assert signage_devices has no 'tags' column. The reduced
WHEN clause (name-only) depends on this invariant. If a future migration
adds a denormalized tags column without updating this trigger, this
assertion fails loud instead of letting tag renames silently miss SSE.

Tag map tables (signage_device_tag_map, signage_playlist_tag_map) use
composite PKs (device_id+tag_id, playlist_id+tag_id) — no scalar 'id'
column. The function branches on TG_TABLE_NAME to emit the relevant FK
as the 'id' field: device_id for device_tag_map, playlist_id for
playlist_tag_map. The listener in signage_pg_listen.py expects this.

Downgrade drops all 8 triggers and the function cleanly.
"""
from alembic import op

revision = "v1_22_signage_notify_triggers"
down_revision = "v1_21_signage_calibration"
branch_labels = None
depends_on = None

PREFLIGHT_SQL = r"""
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'signage_devices'
      AND column_name = 'tags'
  ) THEN
    RAISE EXCEPTION
      'v1_22_signage_notify_triggers preflight failed: signage_devices.tags column exists. '
      'The reduced WHEN clause (name-only) assumes tags live in signage_device_tag_map. '
      'Either drop the tags column, or update this migration''s WHEN clause to include '
      'OLD.tags IS DISTINCT FROM NEW.tags before re-running.';
  END IF;
END $$;
"""

FUNCTION_SQL = r"""
CREATE OR REPLACE FUNCTION signage_notify() RETURNS trigger
  LANGUAGE plpgsql AS $$
DECLARE
  row_id text;
  payload jsonb;
BEGIN
  -- Tag map tables use composite PKs (device_id+tag_id, playlist_id+tag_id)
  -- with no scalar 'id' column. Emit the relevant FK so the listener can
  -- resolve affected devices without a full-table scan.
  IF TG_TABLE_NAME = 'signage_device_tag_map' THEN
    IF TG_OP = 'DELETE' THEN
      row_id := OLD.device_id::text;
    ELSE
      row_id := NEW.device_id::text;
    END IF;
  ELSIF TG_TABLE_NAME = 'signage_playlist_tag_map' THEN
    IF TG_OP = 'DELETE' THEN
      row_id := OLD.playlist_id::text;
    ELSE
      row_id := NEW.playlist_id::text;
    END IF;
  ELSE
    IF TG_OP = 'DELETE' THEN
      row_id := OLD.id::text;
    ELSE
      row_id := NEW.id::text;
    END IF;
  END IF;
  payload := jsonb_build_object(
    'table', TG_TABLE_NAME,
    'op',    TG_OP,
    'id',    row_id
  );
  PERFORM pg_notify('signage_change', payload::text);
  RETURN NULL;
END;
$$;
"""

# Individual trigger DDL — one CREATE TRIGGER per op.execute() call.
# asyncpg rejects multi-statement prepared statements, so TRIGGERS_SQL cannot
# be a single multi-stmt block.
#
# 5 tables: INSERT/UPDATE/DELETE, no WHEN guard.
# signage_devices: 3 triggers. INSERT+DELETE unguarded. UPDATE WHEN-gated on
# name-only (no denormalized tags column on this table, enforced by
# PREFLIGHT_SQL above; tag changes flow via signage_device_tag_map_notify).
# Calibration columns (rotation, hdmi_mode, audio_enabled, paired_at,
# last_heartbeat_at) are EXCLUDED — FastAPI calibration SSE stays the sole
# emitter for those.
TRIGGER_STATEMENTS = [
    """CREATE TRIGGER signage_playlists_notify
  AFTER INSERT OR UPDATE OR DELETE ON signage_playlists
  FOR EACH ROW EXECUTE FUNCTION signage_notify();""",
    """CREATE TRIGGER signage_playlist_items_notify
  AFTER INSERT OR UPDATE OR DELETE ON signage_playlist_items
  FOR EACH ROW EXECUTE FUNCTION signage_notify();""",
    """CREATE TRIGGER signage_playlist_tag_map_notify
  AFTER INSERT OR UPDATE OR DELETE ON signage_playlist_tag_map
  FOR EACH ROW EXECUTE FUNCTION signage_notify();""",
    """CREATE TRIGGER signage_device_tag_map_notify
  AFTER INSERT OR UPDATE OR DELETE ON signage_device_tag_map
  FOR EACH ROW EXECUTE FUNCTION signage_notify();""",
    """CREATE TRIGGER signage_schedules_notify
  AFTER INSERT OR UPDATE OR DELETE ON signage_schedules
  FOR EACH ROW EXECUTE FUNCTION signage_notify();""",
    """CREATE TRIGGER signage_devices_insert_notify
  AFTER INSERT ON signage_devices
  FOR EACH ROW EXECUTE FUNCTION signage_notify();""",
    """CREATE TRIGGER signage_devices_delete_notify
  AFTER DELETE ON signage_devices
  FOR EACH ROW EXECUTE FUNCTION signage_notify();""",
    """CREATE TRIGGER signage_devices_update_notify
  AFTER UPDATE ON signage_devices
  FOR EACH ROW
  WHEN (OLD.name IS DISTINCT FROM NEW.name)
  EXECUTE FUNCTION signage_notify();""",
]


def upgrade() -> None:
    op.execute(PREFLIGHT_SQL)
    op.execute(FUNCTION_SQL)
    for stmt in TRIGGER_STATEMENTS:
        op.execute(stmt)


def downgrade() -> None:
    for trg, tbl in [
        ("signage_playlists_notify", "signage_playlists"),
        ("signage_playlist_items_notify", "signage_playlist_items"),
        ("signage_playlist_tag_map_notify", "signage_playlist_tag_map"),
        ("signage_device_tag_map_notify", "signage_device_tag_map"),
        ("signage_schedules_notify", "signage_schedules"),
        ("signage_devices_insert_notify", "signage_devices"),
        ("signage_devices_delete_notify", "signage_devices"),
        ("signage_devices_update_notify", "signage_devices"),
    ]:
        op.execute(f"DROP TRIGGER IF EXISTS {trg} ON {tbl};")
    op.execute("DROP FUNCTION IF EXISTS signage_notify();")
