"""Schemas package — re-exports every Pydantic v2 class.

Keeps ``from app.schemas import X`` stable for all existing callers
(legacy classes live in ``_base.py``; signage classes live in ``signage.py``).
"""
from app.schemas._base import *  # noqa: F401,F403 — re-export legacy classes
from app.schemas.atr import (  # noqa: F401
    AtrImportPartPreview,
    AtrImportPreview,
    AtrImportResult,
    AtrPartCreate,
    AtrPartRead,
    AtrPartUpdate,
    AtrTemplateRead,
    AtrTemplateUpdate,
)
from app.schemas.atr_delivery import (  # noqa: F401
    AtrDeliveryItemRead, AtrDeliveryItemUpdate, AtrDeliveryRead,
    AtrDeliverySummary, AtrDeliveryUpdate, AtrGenerateManifest,
)
from app.schemas.signage import (  # noqa: F401
    SignageDeviceBase,
    SignageDeviceRead,
    SignageMediaBase,
    SignageMediaRead,
    SignagePairingClaimRequest,
    SignagePairingRequestResponse,
    SignagePairingSessionRead,
    SignagePairingStatusResponse,
    SignagePlaylistBase,
    SignagePlaylistItemBase,
    SignagePlaylistItemCreate,
    SignagePlaylistItemRead,
    SignagePlaylistRead,
)
from app.schemas.feedback import (  # noqa: F401
    FeedbackRead,
    FeedbackStatus,
    FeedbackStatusUpdate,
)
