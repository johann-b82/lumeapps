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
    SalesContact,
    QualityRecord,
    DeliveryRecord,
    AuftragPosition,
    DeliveryReliabilityRecord,
    GoodsReceiptRecord,
    TippspielTip,
    Interessent,
    Offer,
    Revenue,
    Auftrag,
    MaterialMovement,
    MaterialPrice,
    InspectionRecord,
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

# ATR module models (Phase A + Phase B)
from app.models.atr import AtrPart, AtrTemplate, AtrDelivery, AtrDeliveryItem  # noqa: F401

# FAIR models (v1.73 — drawing ballooning / Erstmusterprüfung)
from app.models.fair import FairProject, FairBalloon  # noqa: F401

# Maschinen-Wartung models (v1.82 — machine maintenance)
from app.models.maintenance import (  # noqa: F401
    Machine,
    MaintenanceTask,
    MaintenanceFile,
)

# Audit-Modul models (v1.84 — internal/external audit management)
from app.models.audit import (  # noqa: F401
    Audit,
    AuditCategoryLink,
    AuditNormLink,
    AuditNormReference,
    AuditPhase,
    AuditPhaseTemplate,
    AuditPhaseTemplateStep,
    AuditTrailEntry,
)

from app.models.schulung import (  # noqa: F401
    SchulungImport,
    SchulungKatalog,
    SchulungPflicht,
    SchulungRolle,
    OnboardingAbteilung,
    OnboardingDokument,
    OnboardingExtern,
    OnboardingPaketDownload,
    SchulungTeilnahme,
    SchulungUnterlage,
)
from app.models.kompetenz import (  # noqa: F401
    KompetenzBewertung,
    KompetenzKategorie,
    KompetenzMatrix,
    KompetenzPerson,
    KompetenzQualifikation,
)
from app.models.einarbeitung import (  # noqa: F401
    EinarbeitungDokument,
    EinarbeitungKatalog,
    EinarbeitungPflicht,
)

__all__ = [
    "Base",
    # Legacy
    "AppSettings", "UploadBatch", "SalesRecord",
    "PersonioEmployee", "PersonioAttendance", "PersonioAbsence", "PersonioSyncMeta",
    "Sensor", "SensorReading", "SensorPollLog",
    "SalesContact",
    "QualityRecord",
    "DeliveryRecord",
    "AuftragPosition",
    "DeliveryReliabilityRecord",
    "GoodsReceiptRecord",
    "TippspielTip",
    "Interessent",
    "Offer",
    "Revenue",
    "Auftrag",
    "MaterialMovement",
    "MaterialPrice",
    "InspectionRecord",
    # Signage
    "SignageMedia", "SignagePlaylist", "SignagePlaylistItem",
    "SignageDevice", "SignageDeviceTag", "SignageDeviceTagMap",
    "SignagePlaylistTagMap", "SignagePairingSession",
    "SignageSchedule", "SignageHeartbeatEvent",
    # ATR
    "AtrPart", "AtrTemplate",
    "AtrDelivery", "AtrDeliveryItem",
    # FAIR
    "FairProject", "FairBalloon",
    # Maschinen-Wartung
    "Machine", "MaintenanceTask", "MaintenanceFile",
    # Audit-Modul
    "AuditNormReference", "AuditPhaseTemplate", "AuditPhaseTemplateStep",
    "Audit", "AuditNormLink", "AuditCategoryLink", "AuditPhase", "AuditTrailEntry",
    # Schulungen
    "SchulungKatalog", "SchulungImport", "SchulungTeilnahme", "SchulungPflicht", "SchulungRolle",
    "SchulungUnterlage",
    "OnboardingAbteilung", "OnboardingDokument", "OnboardingExtern", "OnboardingPaketDownload",
    "KompetenzMatrix", "KompetenzQualifikation", "KompetenzPerson", "KompetenzBewertung",
    "KompetenzKategorie",
    "EinarbeitungDokument", "EinarbeitungKatalog", "EinarbeitungPflicht",
]
