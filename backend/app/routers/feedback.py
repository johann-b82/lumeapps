"""Seiten-Feedback router — global feedback / problem-report widget (v1.105).

Mixed-gate router (see CLAUDE.md "Auth gate placement"): the router-level
dependency only requires an authenticated user, because **submitting** feedback
must be open to every logged-in role (Viewer, QS, Admin). The review/manage
endpoints add ``require_admin`` per route.

Admin-only endpoints (all except the first):
    POST   /api/feedback                 create a report        (ANY logged-in role)
    GET    /api/feedback                 list reports           (admin)
    GET    /api/feedback/{id}/screenshot stream the screenshot  (admin)
    PATCH  /api/feedback/{id}            set status new/resolved (admin)
    DELETE /api/feedback/{id}            delete a report        (admin)

The ``POST /api/feedback`` viewer exception is registered in
``tests/test_admin_gate_audit.py`` ADMIN_GATE_ALLOWLIST.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Response,
    UploadFile,
    status,
)
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.models import PageFeedback
from app.schemas import (
    CurrentUser,
    FeedbackRead,
    FeedbackStatusUpdate,
    FeedbackUnreadCount,
)
from app.security.directus_auth import get_current_user, require_admin

router = APIRouter(
    prefix="/api/feedback",
    tags=["feedback"],
    dependencies=[Depends(get_current_user)],
)

# Screenshot upload guards.
_ALLOWED_MIME = {"image/png", "image/jpeg", "image/webp"}
_MAX_SCREENSHOT_BYTES = 5 * 1024 * 1024  # 5 MB
_MAX_DESCRIPTION_LEN = 5000


def _to_read(row: PageFeedback) -> FeedbackRead:
    return FeedbackRead(
        id=row.id,
        created_at=row.created_at,
        created_by_id=row.created_by_id,
        reporter_email=row.reporter_email,
        page_url=row.page_url,
        description=row.description,
        has_screenshot=row.screenshot_data is not None,
        screenshot_mime=row.screenshot_mime,
        user_agent=row.user_agent,
        viewport=row.viewport,
        status=row.status,
        viewed_at=row.viewed_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_feedback(
    description: str = Form(...),
    page_url: str = Form(...),
    user_agent: str | None = Form(None),
    viewport: str | None = Form(None),
    reporter_email: str | None = Form(None),
    screenshot: UploadFile | None = File(None),
    current_user: CurrentUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db_session),
) -> dict[str, uuid.UUID]:
    """Create a feedback report. Open to every authenticated role.

    The screenshot is optional (client capture can fail); text is required.
    """
    text = description.strip()
    if not text:
        raise HTTPException(status_code=422, detail="description must not be empty")
    if len(text) > _MAX_DESCRIPTION_LEN:
        raise HTTPException(
            status_code=422,
            detail=f"description exceeds {_MAX_DESCRIPTION_LEN} characters",
        )

    shot_bytes: bytes | None = None
    shot_mime: str | None = None
    if screenshot is not None:
        mime = (screenshot.content_type or "").lower()
        if mime not in _ALLOWED_MIME:
            raise HTTPException(
                status_code=422,
                detail=f"unsupported screenshot type: {mime or 'unknown'}",
            )
        # Read at most MAX+1 so we can reject oversize without buffering more.
        raw = await screenshot.read(_MAX_SCREENSHOT_BYTES + 1)
        if len(raw) > _MAX_SCREENSHOT_BYTES:
            raise HTTPException(
                status_code=422, detail="screenshot exceeds 5 MB size limit"
            )
        if raw:
            shot_bytes = raw
            shot_mime = mime

    row = PageFeedback(
        created_by_id=current_user.id,
        reporter_email=(reporter_email or None),
        page_url=page_url[:2000],
        description=text,
        screenshot_data=shot_bytes,
        screenshot_mime=shot_mime,
        user_agent=(user_agent or None),
        viewport=(viewport or None),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return {"id": row.id}


@router.get(
    "",
    response_model=list[FeedbackRead],
    dependencies=[Depends(require_admin)],
)
async def list_feedback(
    db: AsyncSession = Depends(get_async_db_session),
) -> list[FeedbackRead]:
    result = await db.execute(
        select(PageFeedback).order_by(PageFeedback.created_at.desc())
    )
    return [_to_read(r) for r in result.scalars().all()]


@router.get(
    "/{feedback_id}/screenshot",
    dependencies=[Depends(require_admin)],
)
async def get_feedback_screenshot(
    feedback_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    row = await db.get(PageFeedback, feedback_id)
    if row is None or row.screenshot_data is None:
        raise HTTPException(status_code=404, detail="no screenshot")
    return Response(
        content=row.screenshot_data,
        media_type=row.screenshot_mime or "application/octet-stream",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.get(
    "/unread-count",
    response_model=FeedbackUnreadCount,
    dependencies=[Depends(require_admin)],
)
async def get_unread_count(
    db: AsyncSession = Depends(get_async_db_session),
) -> FeedbackUnreadCount:
    """Number of feedback reports an admin has not viewed yet (viewed_at NULL)."""
    n = (
        await db.execute(
            select(func.count())
            .select_from(PageFeedback)
            .where(PageFeedback.viewed_at.is_(None))
        )
    ).scalar_one()
    return FeedbackUnreadCount(count=int(n))


@router.post(
    "/{feedback_id}/view",
    response_model=FeedbackRead,
    dependencies=[Depends(require_admin)],
)
async def mark_feedback_viewed(
    feedback_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> FeedbackRead:
    """Mark one feedback as viewed (idempotent) — decrements the unread badge."""
    row = await db.get(PageFeedback, feedback_id)
    if row is None:
        raise HTTPException(status_code=404, detail="feedback not found")
    if row.viewed_at is None:
        row.viewed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(row)
    return _to_read(row)


@router.patch(
    "/{feedback_id}",
    response_model=FeedbackRead,
    dependencies=[Depends(require_admin)],
)
async def update_feedback_status(
    feedback_id: uuid.UUID,
    payload: FeedbackStatusUpdate,
    db: AsyncSession = Depends(get_async_db_session),
) -> FeedbackRead:
    row = await db.get(PageFeedback, feedback_id)
    if row is None:
        raise HTTPException(status_code=404, detail="feedback not found")
    row.status = payload.status
    await db.commit()
    await db.refresh(row)
    return _to_read(row)


@router.delete(
    "/{feedback_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_admin)],
)
async def delete_feedback(
    feedback_id: uuid.UUID,
    db: AsyncSession = Depends(get_async_db_session),
) -> Response:
    result = await db.execute(
        delete(PageFeedback).where(PageFeedback.id == feedback_id)
    )
    await db.commit()
    if result.rowcount == 0:
        raise HTTPException(status_code=404, detail="feedback not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
