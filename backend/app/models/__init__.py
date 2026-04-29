"""Models package — re-exports Base and every ORM class.

Keeping `from app.models import X` stable for all existing callers
while allowing new modules (like `app.models.signage`) to be added
alongside `_base.py`.

Every class must be imported here so SQLAlchemy registers it with
Base.metadata before Alembic reads `target_metadata` in env.py.
"""
from app.database import Base  # noqa: F401 — re-exported for env.py

from app.models._base import (  # noqa: F401
    AppSettings,
    UploadBatch,
    SalesRecord,
    PersonioEmployee,
    PersonioAttendance,
    PersonioAbsence,
    PersonioSyncMeta,
    Sensor,
    SensorReading,
    SensorPollLog,
)

# Signage models (added in Task 2 of this plan)
from app.models.signage import (  # noqa: F401
    SignageMedia,
    SignagePlaylist,
    SignagePlaylistItem,
    SignageDevice,
    SignageDeviceTag,
    SignageDeviceTagMap,
    SignagePlaylistTagMap,
    SignagePairingSession,
    SignageSchedule,
    SignageHeartbeatEvent,
)

__all__ = [
    "Base",
    # Legacy
    "AppSettings", "UploadBatch", "SalesRecord",
    "PersonioEmployee", "PersonioAttendance", "PersonioAbsence", "PersonioSyncMeta",
    "Sensor", "SensorReading", "SensorPollLog",
    # Signage
    "SignageMedia", "SignagePlaylist", "SignagePlaylistItem",
    "SignageDevice", "SignageDeviceTag", "SignageDeviceTagMap",
    "SignagePlaylistTagMap", "SignagePairingSession",
    "SignageSchedule", "SignageHeartbeatEvent",
]
