"""Uploads router (admin-only after v1.23 C-1).

v1.23 C-1: ``GET /api/uploads`` migrated to Directus ``upload_batches``
collection (Admin + Viewer read). The ``read_router`` is therefore removed;
only ``admin_router`` remains, holding the compute-justified write paths
(file parsing, cascade delete).

Admin-only:      POST /api/upload, DELETE /api/uploads/{batch_id}
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.security.directus_auth import get_current_user, require_admin
from app.models import SalesRecord, UploadBatch
from app.parsing.erp_parser import parse_erp_file
from app.schemas import UploadResponse, ValidationErrorDetail

admin_router = APIRouter(
    prefix="/api",
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)

ALLOWED_EXTENSIONS = {".csv", ".txt"}


@admin_router.post("/upload", response_model=UploadResponse)
async def upload_file(
    file: UploadFile,
    db: AsyncSession = Depends(get_async_db_session),
) -> UploadResponse:
    """Accept a .csv or .txt file, parse it, and store valid rows in the database."""
    # Validate file extension
    filename = file.filename or ""
    ext = ""
    if "." in filename:
        ext = "." + filename.rsplit(".", 1)[-1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Unsupported file type: {filename}. "
                "Only .csv and .txt files are accepted."
            ),
        )

    # Read and parse file
    contents = await file.read()
    valid_rows, errors = parse_erp_file(contents, filename)

    # Determine status per D-11
    if errors and not valid_rows:
        status = "failed"
    elif errors and valid_rows:
        status = "partial"
    else:
        status = "success"

    # Create UploadBatch record
    batch = UploadBatch(
        filename=filename,
        uploaded_at=datetime.now(timezone.utc),
        row_count=len(valid_rows),
        error_count=len(errors),
        status=status,
    )
    db.add(batch)
    await db.flush()  # Get batch.id without committing

    # Insert valid rows with ON CONFLICT DO NOTHING for idempotent re-uploads
    if valid_rows:
        for row in valid_rows:
            row["upload_batch_id"] = batch.id

        stmt = pg_insert(SalesRecord).values(valid_rows).on_conflict_do_nothing(
            index_elements=["order_number"]
        )
        result = await db.execute(stmt)
        # Update row_count to reflect actual insertions (skips deduped rows)
        batch.row_count = result.rowcount

    await db.commit()
    await db.refresh(batch)

    return UploadResponse(
        id=batch.id,
        filename=batch.filename,
        row_count=batch.row_count,
        error_count=batch.error_count,
        status=batch.status,
        errors=[ValidationErrorDetail(**e) for e in errors],
    )


@admin_router.delete("/uploads/{batch_id}")
async def delete_upload(
    batch_id: int,
    db: AsyncSession = Depends(get_async_db_session),
) -> dict:
    """Delete an upload batch and all associated sales records via cascade."""
    batch = await db.get(UploadBatch, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Upload batch not found")

    await db.delete(batch)
    await db.commit()

    return {"detail": "deleted", "id": batch_id}
