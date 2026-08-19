"""Pydantic v2 schemas for the Seiten-Feedback module (v1.105).

The create side is a multipart form (see routers/feedback.py) — no request
model here. ``FeedbackRead`` is the admin list/detail model; it never carries
the screenshot bytes (those stream from a dedicated endpoint), only a
``has_screenshot`` flag + mime. ``FeedbackStatusUpdate`` is the PATCH payload.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict

FeedbackStatus = Literal["new", "resolved"]


class FeedbackRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    created_by_id: uuid.UUID | None
    reporter_email: str | None
    page_url: str
    description: str
    has_screenshot: bool
    screenshot_mime: str | None
    user_agent: str | None
    viewport: str | None
    status: FeedbackStatus


class FeedbackStatusUpdate(BaseModel):
    status: FeedbackStatus
