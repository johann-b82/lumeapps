"""Uploads router (admin-only after v1.23 C-1).

v1.23 C-1: ``GET /api/uploads`` migrated to Directus ``upload_batches``
collection (Admin + Viewer read). The ``read_router`` is therefore removed;
only ``admin_router`` remains, holding the compute-justified write paths
(file parsing, cascade delete).

Admin-only:      POST /api/upload, DELETE /api/uploads/{batch_id}

Compute-justified: clause 1 (file parsing) + clause 3 (cascade delete).
"""
from datetime import datetime, timezone

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_async_db_session
from app.security.directus_auth import get_current_user, require_admin
from app.models import (
    Auftrag,
    DeliveryRecord,
    DeliveryReliabilityRecord,
    Interessent,
    Offer,
    QualityRecord,
    Revenue,
    SalesContact,
    SalesRecord,
    UploadBatch,
)
from app.parsing.angebote_parser import parse_angebote_file
from app.parsing.auftraege_parser import parse_auftraege_file
from app.parsing.delivery_parser import parse_delivery_file
from app.parsing.delivery_reliability_parser import (
    parse_delivery_reliability_file,
)
from app.parsing.erp_parser import parse_erp_file
from app.parsing.interessenten_parser import parse_interessenten_file
from app.parsing.kontakte_parser import parse_kontakte_file
from app.parsing.quality_parser import parse_quality_file
from app.parsing.revenue_parser import parse_revenue_file
from app.schemas import (
    AngeboteUploadResponse,
    AuftraegeUploadResponse,
    ContactsUploadResponse,
    DeliveryReliabilityUploadResponse,
    DeliveryUploadResponse,
    InteressentenUploadResponse,
    QualityUploadResponse,
    RevenueUploadResponse,
    UploadResponse,
    ValidationErrorDetail,
)

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
        kind="orders",
    )
    db.add(batch)
    await db.flush()  # Get batch.id without committing

    # Insert valid rows with ON CONFLICT DO NOTHING for idempotent re-uploads.
    # asyncpg caps a single statement at 32767 query parameters, so chunk by
    # rows-per-statement = floor(32767 / cols_per_row). cols_per_row is read
    # from the first row at runtime so the chunk size adapts if the column
    # mapping is widened later. v1.26: ~21 cols → 1560 rows/chunk.
    if valid_rows:
        for row in valid_rows:
            row["upload_batch_id"] = batch.id

        cols_per_row = max(1, len(valid_rows[0]))
        chunk_size = max(1, 32767 // cols_per_row)
        inserted_total = 0
        for start in range(0, len(valid_rows), chunk_size):
            chunk = valid_rows[start : start + chunk_size]
            stmt = pg_insert(SalesRecord).values(chunk).on_conflict_do_nothing(
                index_elements=["order_number"]
            )
            chunk_result = await db.execute(stmt)
            inserted_total += chunk_result.rowcount or 0
        # Update row_count to reflect actual insertions (skips deduped rows)
        batch.row_count = inserted_total

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


# ── v1.41 — Kontakte (sales contact log) ────────────────────────────────


@admin_router.post("/upload-contacts", response_model=ContactsUploadResponse)
async def upload_contacts(
    file: UploadFile,
    db: AsyncSession = Depends(get_async_db_session),
) -> ContactsUploadResponse:
    """Replace-by-date-range insert of a Kontakte (.txt) tab-separated dump.

    Idempotent: any existing ``sales_contacts`` row whose ``contact_date``
    falls inside the uploaded file's date range is deleted first, so
    re-uploading the same file is a no-op.
    """
    filename = file.filename or ""
    if not filename.lower().endswith(".txt"):
        raise HTTPException(
            status_code=422,
            detail="Only .txt files are accepted for Kontakte uploads.",
        )
    contents = await file.read()
    rows, errors = parse_kontakte_file(contents, filename)
    now = datetime.now(timezone.utc)
    if not rows:
        # Still log the failed attempt to upload history.
        db.add(
            UploadBatch(
                filename=filename,
                uploaded_at=now,
                row_count=0,
                error_count=len(errors),
                status="failed" if errors else "success",
                kind="contacts",
            )
        )
        await db.commit()
        return ContactsUploadResponse(
            rows_inserted=0,
            rows_replaced=0,
            date_range_from=None,
            date_range_to=None,
        )

    date_from = min(r["contact_date"] for r in rows)
    date_to = max(r["contact_date"] for r in rows)

    deleted = await db.execute(
        sa.delete(SalesContact).where(
            SalesContact.contact_date >= date_from,
            SalesContact.contact_date <= date_to,
        )
    )
    rows_replaced = deleted.rowcount or 0

    for r in rows:
        r["imported_at"] = now
    cols_per_row = max(1, len(rows[0]))
    chunk_size = max(1, 32767 // cols_per_row)
    inserted_total = 0
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        result = await db.execute(pg_insert(SalesContact).values(chunk))
        inserted_total += result.rowcount or 0

    db.add(
        UploadBatch(
            filename=filename,
            uploaded_at=now,
            row_count=inserted_total,
            error_count=len(errors),
            status=(
                "failed"
                if errors and inserted_total == 0
                else ("partial" if errors else "success")
            ),
            kind="contacts",
        )
    )
    await db.commit()

    return ContactsUploadResponse(
        rows_inserted=inserted_total,
        rows_replaced=rows_replaced,
        date_range_from=date_from,
        date_range_to=date_to,
    )


# ── v1.49 — Quality (8D audit findings + later complaints) ──────────────


@admin_router.post("/upload-quality", response_model=QualityUploadResponse)
async def upload_quality(
    file: UploadFile,
    db: AsyncSession = Depends(get_async_db_session),
) -> QualityUploadResponse:
    """Upsert of an 8D report dump (.txt, tab-separated, cp1252).

    Each row carries a unique ``Nr.`` from the source ERP. ``ON CONFLICT
    (report_nr) DO UPDATE`` overwrites every data column except the
    business key — so the user can edit a 8D report's status / level /
    customer / etc. in the ERP, re-export the file, re-upload it, and see
    the dashboard reflect the new state without first deleting anything.

    Re-pointing ``upload_batch_id`` to the latest batch keeps the
    upload-history audit log consistent: any cascade-delete of a batch
    only removes the rows that were not later re-uploaded.
    """
    filename = file.filename or ""
    if not filename.lower().endswith(".txt"):
        raise HTTPException(
            status_code=422,
            detail="Only .txt files are accepted for Quality / 8D uploads.",
        )
    contents = await file.read()
    rows, errors = parse_quality_file(contents, filename)
    now = datetime.now(timezone.utc)

    if not rows:
        db.add(
            UploadBatch(
                filename=filename,
                uploaded_at=now,
                row_count=0,
                error_count=len(errors),
                status="failed" if errors else "success",
                kind="quality",
            )
        )
        await db.commit()
        return QualityUploadResponse(
            rows_inserted=0,
            rows_updated=0,
            errors=[ValidationErrorDetail(**e) for e in errors],
        )

    # Count which report_nrs already exist BEFORE the upsert — that's the
    # number of UPDATEs the next statement will perform. Single COUNT
    # query, scales fine to the ~1k-rows-per-file 8D volume.
    incoming_nrs = [r["report_nr"] for r in rows]
    existing_stmt = sa.select(sa.func.count(QualityRecord.id)).where(
        QualityRecord.report_nr.in_(incoming_nrs)
    )
    rows_updated = (await db.execute(existing_stmt)).scalar_one() or 0
    rows_inserted = len(rows) - rows_updated

    batch = UploadBatch(
        filename=filename,
        uploaded_at=now,
        row_count=0,
        error_count=len(errors),
        status="success",
        kind="quality",
    )
    db.add(batch)
    await db.flush()  # need batch.id before insert

    for r in rows:
        r["upload_batch_id"] = batch.id

    # Columns to overwrite on conflict. Everything except the conflict
    # key (report_nr) and the synthetic PK (id). upload_batch_id is also
    # refreshed so an edited row's audit trail points at the latest file.
    table = QualityRecord.__table__
    update_cols = [
        c.name for c in table.columns if c.name not in ("id", "report_nr")
    ]

    # asyncpg statement cap: floor(32767 / cols_per_row) rows per chunk.
    cols_per_row = max(1, len(rows[0]))
    chunk_size = max(1, 32767 // cols_per_row)
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        stmt = pg_insert(QualityRecord).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["report_nr"],
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        await db.execute(stmt)

    batch.row_count = rows_inserted + rows_updated
    if errors and batch.row_count == 0:
        batch.status = "failed"
    elif errors:
        batch.status = "partial"
    await db.commit()

    return QualityUploadResponse(
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        errors=[ValidationErrorDetail(**e) for e in errors],
    )


# ── v1.58 — Deliveries (AswKpf_LS.xlsx Lieferschein export) ────────────


@admin_router.post("/upload-deliveries", response_model=DeliveryUploadResponse)
async def upload_deliveries(
    file: UploadFile,
    db: AsyncSession = Depends(get_async_db_session),
) -> DeliveryUploadResponse:
    """Upsert of a Lieferschein xlsx export.

    Composite business key ``(vorgang_nr, pos, upos)`` identifies a single
    LS line; ``ON CONFLICT DO UPDATE`` overwrites all data columns when
    the user re-exports an edited file. Re-pointing ``upload_batch_id``
    to the latest batch matches the v1.49 Quality pattern.
    """
    filename = file.filename or ""
    if not filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=422,
            detail="Only .xlsx files are accepted for delivery uploads.",
        )
    contents = await file.read()
    rows, errors = parse_delivery_file(contents, filename)
    now = datetime.now(timezone.utc)

    if not rows:
        db.add(
            UploadBatch(
                filename=filename,
                uploaded_at=now,
                row_count=0,
                error_count=len(errors),
                status="failed" if errors else "success",
                kind="deliveries",
            )
        )
        await db.commit()
        return DeliveryUploadResponse(
            rows_inserted=0,
            rows_updated=0,
            errors=[ValidationErrorDetail(**e) for e in errors],
        )

    # Count how many incoming (vorgang, pos, upos) tuples already exist —
    # one EXISTS-style query using a value-list join.
    incoming_keys = [(r["vorgang_nr"], r["pos"], r["upos"]) for r in rows]
    # Postgres tuple-IN: SELECT count(*) FROM ... WHERE (a,b,c) IN ((...)).
    # asyncpg + SQLAlchemy support this via sa.tuple_(...).in_.
    existing_stmt = sa.select(sa.func.count(DeliveryRecord.id)).where(
        sa.tuple_(
            DeliveryRecord.vorgang_nr,
            DeliveryRecord.pos,
            DeliveryRecord.upos,
        ).in_(incoming_keys)
    )
    rows_updated = (await db.execute(existing_stmt)).scalar_one() or 0
    rows_inserted = len(rows) - rows_updated

    batch = UploadBatch(
        filename=filename,
        uploaded_at=now,
        row_count=0,
        error_count=len(errors),
        status="success",
        kind="deliveries",
    )
    db.add(batch)
    await db.flush()

    for r in rows:
        r["upload_batch_id"] = batch.id

    table = DeliveryRecord.__table__
    update_cols = [
        c.name
        for c in table.columns
        if c.name not in ("id", "vorgang_nr", "pos", "upos")
    ]

    cols_per_row = max(1, len(rows[0]))
    chunk_size = max(1, 32767 // cols_per_row)
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        stmt = pg_insert(DeliveryRecord).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_delivery_records_vorgang_pos",
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        await db.execute(stmt)

    batch.row_count = rows_inserted + rows_updated
    if errors and batch.row_count == 0:
        batch.status = "failed"
    elif errors:
        batch.status = "partial"
    await db.commit()

    return DeliveryUploadResponse(
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        errors=[ValidationErrorDetail(**e) for e in errors],
    )


@admin_router.post(
    "/upload-delivery-reliability",
    response_model=DeliveryReliabilityUploadResponse,
)
async def upload_delivery_reliability(
    file: UploadFile,
    db: AsyncSession = Depends(get_async_db_session),
) -> DeliveryReliabilityUploadResponse:
    """Upsert of the dev_excel_Liefertreue_Einkauf.txt export.

    Composite business key ``(auftrag, pos, upos)`` identifies one delivery
    position; ``ON CONFLICT DO UPDATE`` overwrites all data columns on
    re-upload. The Auswertung period parsed from the file title is echoed
    back so the dashboard can show the data-coverage range.
    """
    filename = file.filename or ""
    if not filename.lower().endswith(".txt"):
        raise HTTPException(
            status_code=422,
            detail="Only .txt files are accepted for delivery-reliability uploads.",
        )
    contents = await file.read()
    rows, errors, period = parse_delivery_reliability_file(contents, filename)
    period_from = period[0].isoformat() if period else None
    period_to = period[1].isoformat() if period else None
    now = datetime.now(timezone.utc)

    if not rows:
        db.add(
            UploadBatch(
                filename=filename,
                uploaded_at=now,
                row_count=0,
                error_count=len(errors),
                status="failed" if errors else "success",
                kind="delivery_reliability",
            )
        )
        await db.commit()
        return DeliveryReliabilityUploadResponse(
            rows_inserted=0,
            rows_updated=0,
            period_from=period_from,
            period_to=period_to,
            errors=[ValidationErrorDetail(**e) for e in errors],
        )

    incoming_keys = [(r["auftrag"], r["pos"], r["upos"]) for r in rows]
    existing_stmt = sa.select(sa.func.count(DeliveryReliabilityRecord.id)).where(
        sa.tuple_(
            DeliveryReliabilityRecord.auftrag,
            DeliveryReliabilityRecord.pos,
            DeliveryReliabilityRecord.upos,
        ).in_(incoming_keys)
    )
    rows_updated = (await db.execute(existing_stmt)).scalar_one() or 0
    rows_inserted = len(rows) - rows_updated

    batch = UploadBatch(
        filename=filename,
        uploaded_at=now,
        row_count=0,
        error_count=len(errors),
        status="success",
        kind="delivery_reliability",
    )
    db.add(batch)
    await db.flush()

    for r in rows:
        r["upload_batch_id"] = batch.id

    table = DeliveryReliabilityRecord.__table__
    update_cols = [
        c.name
        for c in table.columns
        if c.name not in ("id", "auftrag", "pos", "upos")
    ]

    cols_per_row = max(1, len(rows[0]))
    chunk_size = max(1, 32767 // cols_per_row)
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        stmt = pg_insert(DeliveryReliabilityRecord).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_delivery_reliability_auftrag_pos",
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        await db.execute(stmt)

    batch.row_count = rows_inserted + rows_updated
    if errors and batch.row_count == 0:
        batch.status = "failed"
    elif errors:
        batch.status = "partial"
    await db.commit()

    return DeliveryReliabilityUploadResponse(
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        period_from=period_from,
        period_to=period_to,
        errors=[ValidationErrorDetail(**e) for e in errors],
    )


# ── v1.51 — Interessenten (prospect master-data) ───────────────────────


@admin_router.post("/upload-interessenten", response_model=InteressentenUploadResponse)
async def upload_interessenten(
    file: UploadFile,
    db: AsyncSession = Depends(get_async_db_session),
) -> InteressentenUploadResponse:
    """Upsert of the Adressen/Interessenten master-data dump (88-col .txt).

    Idempotent: ``ON CONFLICT (adress_nr) DO UPDATE`` so re-uploading the
    same file is a no-op on body and only refreshes ``upload_batch_id``
    and ``imported_at``.
    """
    filename = file.filename or ""
    if not filename.lower().endswith(".txt"):
        raise HTTPException(
            status_code=422,
            detail="Only .txt files are accepted for Interessenten uploads.",
        )

    contents = await file.read()
    rows, errors = parse_interessenten_file(contents, filename)
    now = datetime.now(timezone.utc)

    if not rows:
        db.add(
            UploadBatch(
                filename=filename,
                uploaded_at=now,
                row_count=0,
                error_count=len(errors),
                status="failed" if errors else "success",
                kind="interessenten",
            )
        )
        await db.commit()
        return InteressentenUploadResponse(
            rows_inserted=0,
            rows_updated=0,
            errors=[ValidationErrorDetail(row=e.get("row", 0),
                                           column=e.get("field", ""),
                                           message=e.get("message", "")) for e in errors],
        )

    incoming_nrs = [r["adress_nr"] for r in rows]
    existing_stmt = sa.select(sa.func.count()).select_from(Interessent).where(
        Interessent.adress_nr.in_(incoming_nrs)
    )
    rows_updated = (await db.execute(existing_stmt)).scalar_one() or 0
    rows_inserted = len(rows) - rows_updated

    batch = UploadBatch(
        filename=filename,
        uploaded_at=now,
        row_count=0,
        error_count=len(errors),
        status="success",
        kind="interessenten",
    )
    db.add(batch)
    await db.flush()

    for r in rows:
        r["upload_batch_id"] = batch.id
        r["imported_at"] = now

    update_cols = [
        c.name for c in Interessent.__table__.columns if c.name != "adress_nr"
    ]
    cols_per_row = max(1, len(rows[0]))
    chunk_size = max(1, 32767 // cols_per_row)
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        stmt = pg_insert(Interessent).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["adress_nr"],
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        await db.execute(stmt)

    batch.row_count = rows_inserted + rows_updated
    if errors and batch.row_count == 0:
        batch.status = "failed"
    elif errors:
        batch.status = "partial"
    await db.commit()

    return InteressentenUploadResponse(
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        errors=[ValidationErrorDetail(row=e.get("row", 0),
                                       column=e.get("field", ""),
                                       message=e.get("message", "")) for e in errors],
    )


# ── v1.52 — Angebote (sales-offer line) ingestion ──────────────────────


@admin_router.post("/upload-angebote", response_model=AngeboteUploadResponse)
async def upload_angebote(
    file: UploadFile,
    db: AsyncSession = Depends(get_async_db_session),
) -> AngeboteUploadResponse:
    """Upsert of the AswKpf_ANG.txt sales-offer dump (18-col .txt).

    Idempotent: ``ON CONFLICT (vorgang_nr) DO UPDATE`` so re-uploading
    the same file is a no-op on body and only refreshes
    ``upload_batch_id`` and ``imported_at``.
    """
    filename = file.filename or ""
    if not filename.lower().endswith(".txt"):
        raise HTTPException(
            status_code=422,
            detail="Only .txt files are accepted for Angebote uploads.",
        )

    contents = await file.read()
    rows, errors = parse_angebote_file(contents, filename)
    now = datetime.now(timezone.utc)

    if not rows:
        db.add(
            UploadBatch(
                filename=filename,
                uploaded_at=now,
                row_count=0,
                error_count=len(errors),
                status="failed" if errors else "success",
                kind="offers",
            )
        )
        await db.commit()
        return AngeboteUploadResponse(
            rows_inserted=0,
            rows_updated=0,
            errors=[ValidationErrorDetail(row=e.get("row", 0),
                                           column=e.get("field", ""),
                                           message=e.get("message", "")) for e in errors],
        )

    incoming = [r["vorgang_nr"] for r in rows]
    existing_stmt = sa.select(sa.func.count()).select_from(Offer).where(
        Offer.vorgang_nr.in_(incoming)
    )
    rows_updated = (await db.execute(existing_stmt)).scalar_one() or 0
    rows_inserted = len(rows) - rows_updated

    batch = UploadBatch(
        filename=filename,
        uploaded_at=now,
        row_count=0,
        error_count=len(errors),
        status="success",
        kind="offers",
    )
    db.add(batch)
    await db.flush()

    for r in rows:
        r["upload_batch_id"] = batch.id
        r["imported_at"] = now

    update_cols = [
        c.name for c in Offer.__table__.columns if c.name != "vorgang_nr"
    ]
    cols_per_row = max(1, len(rows[0]))
    chunk_size = max(1, 32767 // cols_per_row)
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        stmt = pg_insert(Offer).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["vorgang_nr"],
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        await db.execute(stmt)

    batch.row_count = rows_inserted + rows_updated
    if errors and batch.row_count == 0:
        batch.status = "failed"
    elif errors:
        batch.status = "partial"
    await db.commit()

    return AngeboteUploadResponse(
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        errors=[ValidationErrorDetail(row=e.get("row", 0),
                                       column=e.get("field", ""),
                                       message=e.get("message", "")) for e in errors],
    )


# ── v1.53 — Umsatz (Rechnungsausgang RG/GS) ingestion ───────────────────


@admin_router.post("/upload-umsatz", response_model=RevenueUploadResponse)
async def upload_umsatz(
    file: UploadFile,
    db: AsyncSession = Depends(get_async_db_session),
) -> RevenueUploadResponse:
    """Upsert of the AswKpf_RG.txt revenue / credit-note dump.

    Idempotent: ``ON CONFLICT (vorgang_nr) DO UPDATE`` so a re-upload of
    the same file is a no-op on the data and only refreshes
    ``upload_batch_id`` and ``imported_at``.
    """
    filename = file.filename or ""
    if not filename.lower().endswith(".txt"):
        raise HTTPException(
            status_code=422,
            detail="Only .txt files are accepted for Umsatz uploads.",
        )

    contents = await file.read()
    rows, errors = parse_revenue_file(contents, filename)
    now = datetime.now(timezone.utc)

    if not rows:
        db.add(
            UploadBatch(
                filename=filename,
                uploaded_at=now,
                row_count=0,
                error_count=len(errors),
                status="failed" if errors else "success",
                kind="revenues",
            )
        )
        await db.commit()
        return RevenueUploadResponse(
            rows_inserted=0,
            rows_updated=0,
            errors=[ValidationErrorDetail(row=e.get("row", 0),
                                           column=e.get("field", ""),
                                           message=e.get("message", "")) for e in errors],
        )

    incoming = [r["vorgang_nr"] for r in rows]
    existing_stmt = sa.select(sa.func.count()).select_from(Revenue).where(
        Revenue.vorgang_nr.in_(incoming)
    )
    rows_updated = (await db.execute(existing_stmt)).scalar_one() or 0
    rows_inserted = len(rows) - rows_updated

    batch = UploadBatch(
        filename=filename,
        uploaded_at=now,
        row_count=0,
        error_count=len(errors),
        status="success",
        kind="revenues",
    )
    db.add(batch)
    await db.flush()

    for r in rows:
        r["upload_batch_id"] = batch.id
        r["imported_at"] = now

    update_cols = [
        c.name for c in Revenue.__table__.columns if c.name != "vorgang_nr"
    ]
    cols_per_row = max(1, len(rows[0]))
    chunk_size = max(1, 32767 // cols_per_row)
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        stmt = pg_insert(Revenue).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["vorgang_nr"],
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        await db.execute(stmt)

    batch.row_count = rows_inserted + rows_updated
    if errors and batch.row_count == 0:
        batch.status = "failed"
    elif errors:
        batch.status = "partial"
    await db.commit()

    return RevenueUploadResponse(
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        errors=[ValidationErrorDetail(row=e.get("row", 0),
                                       column=e.get("field", ""),
                                       message=e.get("message", "")) for e in errors],
    )


# ── v1.54 — Aufträge (AswKpf_AUF.txt order book) ────────────────────────


@admin_router.post("/upload-auftraege", response_model=AuftraegeUploadResponse)
async def upload_auftraege(
    file: UploadFile,
    db: AsyncSession = Depends(get_async_db_session),
) -> AuftraegeUploadResponse:
    """Upsert of the AswKpf_AUF.txt order-book dump (18-col .txt).

    Idempotent: ``ON CONFLICT (vorgang_nr) DO UPDATE`` so a re-upload of
    the same file is a no-op on the data and only refreshes
    ``upload_batch_id`` and ``imported_at``.

    Supersedes the legacy 60-col ``POST /api/upload`` (sales_records) as
    the data source for the Sales-dashboard order-side KPIs.
    """
    filename = file.filename or ""
    if not filename.lower().endswith(".txt"):
        raise HTTPException(
            status_code=422,
            detail="Only .txt files are accepted for Aufträge uploads.",
        )

    contents = await file.read()
    rows, errors = parse_auftraege_file(contents, filename)
    now = datetime.now(timezone.utc)

    if not rows:
        db.add(
            UploadBatch(
                filename=filename,
                uploaded_at=now,
                row_count=0,
                error_count=len(errors),
                status="failed" if errors else "success",
                kind="auftraege",
            )
        )
        await db.commit()
        return AuftraegeUploadResponse(
            rows_inserted=0,
            rows_updated=0,
            errors=[ValidationErrorDetail(row=e.get("row", 0),
                                           column=e.get("field", ""),
                                           message=e.get("message", "")) for e in errors],
        )

    incoming = [r["vorgang_nr"] for r in rows]
    existing_stmt = sa.select(sa.func.count()).select_from(Auftrag).where(
        Auftrag.vorgang_nr.in_(incoming)
    )
    rows_updated = (await db.execute(existing_stmt)).scalar_one() or 0
    rows_inserted = len(rows) - rows_updated

    batch = UploadBatch(
        filename=filename,
        uploaded_at=now,
        row_count=0,
        error_count=len(errors),
        status="success",
        kind="auftraege",
    )
    db.add(batch)
    await db.flush()

    for r in rows:
        r["upload_batch_id"] = batch.id
        r["imported_at"] = now

    update_cols = [
        c.name for c in Auftrag.__table__.columns if c.name != "vorgang_nr"
    ]
    cols_per_row = max(1, len(rows[0]))
    chunk_size = max(1, 32767 // cols_per_row)
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        stmt = pg_insert(Auftrag).values(chunk)
        stmt = stmt.on_conflict_do_update(
            index_elements=["vorgang_nr"],
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        await db.execute(stmt)

    batch.row_count = rows_inserted + rows_updated
    if errors and batch.row_count == 0:
        batch.status = "failed"
    elif errors:
        batch.status = "partial"
    await db.commit()

    return AuftraegeUploadResponse(
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        errors=[ValidationErrorDetail(row=e.get("row", 0),
                                       column=e.get("field", ""),
                                       message=e.get("message", "")) for e in errors],
    )
