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
    AuftragPosition,
    DeliveryRecord,
    DeliveryReliabilityRecord,
    GoodsReceiptRecord,
    InspectionRecord,
    Interessent,
    MaterialMovement,
    MaterialPrice,
    Offer,
    QualityRecord,
    Revenue,
    SalesContact,
    SalesRecord,
    TippspielTip,
    UploadBatch,
)
from app.parsing.angebote_parser import parse_angebote_file
from app.parsing.auftraege_parser import parse_auftraege_file
from app.parsing.auftrag_positionen_parser import parse_auftrag_positionen_file
from app.parsing.delivery_parser import parse_delivery_file
from app.parsing.delivery_reliability_parser import (
    parse_delivery_reliability_file,
)
from app.parsing.erp_parser import parse_erp_file
from app.parsing.goods_receipt_parser import parse_goods_receipt_file
from app.parsing.inspection_parser import parse_inspection_file
from app.parsing.material_prices_parser import parse_material_prices_file
from app.parsing.material_movements_parser import parse_material_movements_file
from app.parsing.interessenten_parser import parse_interessenten_file
from app.parsing.kontakte_parser import parse_kontakte_file
from app.parsing.quality_parser import parse_quality_file
from app.parsing.tippspiel_parser import parse_tippspiel_file
from app.parsing.revenue_parser import parse_revenue_file
from app.schemas import (
    AngeboteUploadResponse,
    AuftraegeUploadResponse,
    AuftragPositionenUploadResponse,
    ContactsUploadResponse,
    DeliveryReliabilityUploadResponse,
    DeliveryUploadResponse,
    GoodsReceiptUploadResponse,
    InspectionsUploadResponse,
    InteressentenUploadResponse,
    MaterialMovementsUploadResponse,
    MaterialPricesUploadResponse,
    QualityUploadResponse,
    RevenueUploadResponse,
    TippspielUploadResponse,
    UploadResponse,
    ValidationErrorDetail,
)

admin_router = APIRouter(
    prefix="/api",
    dependencies=[Depends(get_current_user), Depends(require_admin)],
)

ALLOWED_EXTENSIONS = {".csv", ".txt"}

# Batch size for composite-key upserts + their existing-key counts. Kept small
# so neither a multi-row VALUES nor a (a,b,c) IN ((...)) tuple-list over a large
# export (10k+ rows) overflows Postgres' max_stack_depth.
_UPSERT_BATCH = 500


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

    # Count how many incoming (vorgang, pos, upos) tuples already exist. Done in
    # batches: a one-shot (a,b,c) IN ((...)) over thousands of tuples expands to
    # an OR-tree that overflows Postgres' max_stack_depth on large exports.
    incoming_keys = [(r["vorgang_nr"], r["pos"], r["upos"]) for r in rows]
    key_tuple = sa.tuple_(
        DeliveryRecord.vorgang_nr,
        DeliveryRecord.pos,
        DeliveryRecord.upos,
    )
    rows_updated = 0
    for start in range(0, len(incoming_keys), _UPSERT_BATCH):
        batch_keys = incoming_keys[start : start + _UPSERT_BATCH]
        rows_updated += (
            await db.execute(
                sa.select(sa.func.count(DeliveryRecord.id)).where(
                    key_tuple.in_(batch_keys)
                )
            )
        ).scalar_one() or 0
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
    chunk_size = max(1, min(_UPSERT_BATCH, 32767 // cols_per_row))
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
    "/upload-auftrag-positionen",
    response_model=AuftragPositionenUploadResponse,
)
async def upload_auftrag_positionen(
    file: UploadFile,
    db: AsyncSession = Depends(get_async_db_session),
) -> AuftragPositionenUploadResponse:
    """Upsert of the position-level AswKpf_AUF.txt export (Auftragspositionen).

    Composite business key ``(vorgang_nr, pos, upos)``; ``ON CONFLICT DO
    UPDATE`` makes a re-upload of an edited export idempotent. Mirrors the
    Lieferschein upload. Feeds the Produktion "Aufträge in Verzug" KPI.
    """
    filename = file.filename or ""
    if not filename.lower().endswith(".txt"):
        raise HTTPException(
            status_code=422,
            detail="Only .txt files are accepted for Auftragspositionen uploads.",
        )
    contents = await file.read()
    rows, errors = parse_auftrag_positionen_file(contents, filename)
    now = datetime.now(timezone.utc)

    if not rows:
        db.add(
            UploadBatch(
                filename=filename,
                uploaded_at=now,
                row_count=0,
                error_count=len(errors),
                status="failed" if errors else "success",
                kind="auftrag_positionen",
            )
        )
        await db.commit()
        return AuftragPositionenUploadResponse(
            rows_inserted=0,
            rows_updated=0,
            errors=[ValidationErrorDetail(**e) for e in errors],
        )

    # Count pre-existing keys in batches. A single (a,b,c) IN ((...)) over
    # thousands of tuples expands to an OR-tree that overflows Postgres'
    # max_stack_depth (the 10k-row AUF export tripped a one-shot IN).
    incoming_keys = [(r["vorgang_nr"], r["pos"], r["upos"]) for r in rows]
    key_tuple = sa.tuple_(
        AuftragPosition.vorgang_nr,
        AuftragPosition.pos,
        AuftragPosition.upos,
    )
    rows_updated = 0
    for start in range(0, len(incoming_keys), _UPSERT_BATCH):
        batch_keys = incoming_keys[start : start + _UPSERT_BATCH]
        rows_updated += (
            await db.execute(
                sa.select(sa.func.count(AuftragPosition.id)).where(
                    key_tuple.in_(batch_keys)
                )
            )
        ).scalar_one() or 0
    rows_inserted = len(rows) - rows_updated

    batch = UploadBatch(
        filename=filename,
        uploaded_at=now,
        row_count=0,
        error_count=len(errors),
        status="success",
        kind="auftrag_positionen",
    )
    db.add(batch)
    await db.flush()

    for r in rows:
        r["upload_batch_id"] = batch.id

    table = AuftragPosition.__table__
    update_cols = [
        c.name
        for c in table.columns
        if c.name not in ("id", "vorgang_nr", "pos", "upos")
    ]

    cols_per_row = max(1, len(rows[0]))
    # Batch the upsert too — same max_stack_depth guard, and stays under the
    # 32767 bind-param cap.
    chunk_size = max(1, min(_UPSERT_BATCH, 32767 // cols_per_row))
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        stmt = pg_insert(AuftragPosition).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_auftrag_positionen_vorgang_pos",
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        await db.execute(stmt)

    batch.row_count = rows_inserted + rows_updated
    if errors and batch.row_count == 0:
        batch.status = "failed"
    elif errors:
        batch.status = "partial"
    await db.commit()

    return AuftragPositionenUploadResponse(
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        errors=[ValidationErrorDetail(**e) for e in errors],
    )


# ── v1.67 — Goods receipts (AswKpf_WE Wareneingänge) ───────────────────


@admin_router.post(
    "/upload-goods-receipts", response_model=GoodsReceiptUploadResponse
)
async def upload_goods_receipts(
    file: UploadFile,
    db: AsyncSession = Depends(get_async_db_session),
) -> GoodsReceiptUploadResponse:
    """Upsert of a Wareneingang .txt export (AswKpf_WE).

    Same composite-key upsert pattern as ``/upload-deliveries`` — only the
    target table (and the parser) differ.
    """
    filename = file.filename or ""
    if not filename.lower().endswith((".txt", ".tsv", ".csv")):
        raise HTTPException(
            status_code=422,
            detail="Only .txt / .tsv / .csv files are accepted for goods-receipt uploads.",
        )
    contents = await file.read()
    rows, errors = parse_goods_receipt_file(contents, filename)
    now = datetime.now(timezone.utc)

    if not rows:
        db.add(
            UploadBatch(
                filename=filename,
                uploaded_at=now,
                row_count=0,
                error_count=len(errors),
                status="failed" if errors else "success",
                kind="goods_receipts",
            )
        )
        await db.commit()
        return GoodsReceiptUploadResponse(
            rows_inserted=0,
            rows_updated=0,
            errors=[ValidationErrorDetail(**e) for e in errors],
        )

    incoming_keys = [(r["vorgang_nr"], r["pos"], r["upos"]) for r in rows]
    existing_stmt = sa.select(sa.func.count(GoodsReceiptRecord.id)).where(
        sa.tuple_(
            GoodsReceiptRecord.vorgang_nr,
            GoodsReceiptRecord.pos,
            GoodsReceiptRecord.upos,
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
        kind="goods_receipts",
    )
    db.add(batch)
    await db.flush()

    for r in rows:
        r["upload_batch_id"] = batch.id

    table = GoodsReceiptRecord.__table__
    update_cols = [
        c.name
        for c in table.columns
        if c.name not in ("id", "vorgang_nr", "pos", "upos")
    ]

    cols_per_row = max(1, len(rows[0]))
    chunk_size = max(1, 32767 // cols_per_row)
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        stmt = pg_insert(GoodsReceiptRecord).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_goods_receipt_records_vorgang_pos",
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        await db.execute(stmt)

    batch.row_count = rows_inserted + rows_updated
    if errors and batch.row_count == 0:
        batch.status = "failed"
    elif errors:
        batch.status = "partial"
    await db.commit()

    return GoodsReceiptUploadResponse(
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


@admin_router.post("/upload-tippspiel", response_model=TippspielUploadResponse)
async def upload_tippspiel(
    file: UploadFile,
    db: AsyncSession = Depends(get_async_db_session),
) -> TippspielUploadResponse:
    """Upsert of the WM-Tippspiel xlsx — one row per (match, department).

    Composite key ``(home_team, away_team, department)``; team names are stored
    as the football-data feed names so scoring can join to real results.
    """
    filename = file.filename or ""
    if not filename.lower().endswith((".xlsx", ".xls")):
        raise HTTPException(
            status_code=422,
            detail="Only .xlsx files are accepted for Tippspiel uploads.",
        )
    contents = await file.read()
    rows, errors, departments = parse_tippspiel_file(contents, filename)
    now = datetime.now(timezone.utc)

    if not rows:
        db.add(
            UploadBatch(
                filename=filename,
                uploaded_at=now,
                row_count=0,
                error_count=len(errors),
                status="failed" if errors else "success",
                kind="tippspiel",
            )
        )
        await db.commit()
        return TippspielUploadResponse(
            rows_inserted=0,
            rows_updated=0,
            departments=departments,
            errors=[ValidationErrorDetail(**e) for e in errors],
        )

    incoming = [(r["home"], r["away"], r["department"]) for r in rows]
    existing_stmt = sa.select(sa.func.count(TippspielTip.id)).where(
        sa.tuple_(
            TippspielTip.home_team,
            TippspielTip.away_team,
            TippspielTip.department,
        ).in_(incoming)
    )
    rows_updated = (await db.execute(existing_stmt)).scalar_one() or 0
    rows_inserted = len(rows) - rows_updated

    batch = UploadBatch(
        filename=filename,
        uploaded_at=now,
        row_count=0,
        error_count=len(errors),
        status="success",
        kind="tippspiel",
    )
    db.add(batch)
    await db.flush()

    values = [
        {
            "upload_batch_id": batch.id,
            "gruppe": r["gruppe"],
            "home_team": r["home"],
            "away_team": r["away"],
            "match_date": r["match_date"],
            "department": r["department"],
            "tip_home": r["tip_home"],
            "tip_away": r["tip_away"],
            "raw": r["raw"],
        }
        for r in rows
    ]
    table = TippspielTip.__table__
    update_cols = [
        c.name
        for c in table.columns
        if c.name not in ("id", "home_team", "away_team", "department")
    ]
    cols_per_row = max(1, len(values[0]))
    chunk_size = max(1, 32767 // cols_per_row)
    for start in range(0, len(values), chunk_size):
        chunk = values[start : start + chunk_size]
        stmt = pg_insert(TippspielTip).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_tippspiel_tips_match_dept",
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        await db.execute(stmt)

    batch.row_count = rows_inserted + rows_updated
    if errors and batch.row_count == 0:
        batch.status = "failed"
    elif errors:
        batch.status = "partial"
    await db.commit()

    return TippspielUploadResponse(
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        departments=departments,
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


# ── v1.70 — Finanzperspektive: Materialkostenquote ──────────────────────


@admin_router.post(
    "/upload-material-movements",
    response_model=MaterialMovementsUploadResponse,
)
async def upload_material_movements(
    file: UploadFile,
    db: AsyncSession = Depends(get_async_db_session),
) -> MaterialMovementsUploadResponse:
    """Replace-by-date-range insert of an AswLagBew.txt Lagerbewegung dump.

    The source has no clean business key, so idempotency mirrors the Kontakte
    pattern: every existing ``material_movements`` row whose ``buch_datum``
    falls inside the uploaded file's date range is deleted first, then the new
    rows are bulk-inserted. Re-uploading the same file is a no-op.
    """
    filename = file.filename or ""
    if not filename.lower().endswith(".txt"):
        raise HTTPException(
            status_code=422,
            detail="Only .txt files are accepted for material-movements uploads.",
        )
    contents = await file.read()
    rows, errors = parse_material_movements_file(contents, filename)
    now = datetime.now(timezone.utc)

    if not rows:
        db.add(
            UploadBatch(
                filename=filename,
                uploaded_at=now,
                row_count=0,
                error_count=len(errors),
                status="failed" if errors else "success",
                kind="material_movements",
            )
        )
        await db.commit()
        return MaterialMovementsUploadResponse(
            rows_inserted=0,
            rows_replaced=0,
            date_range_from=None,
            date_range_to=None,
            errors=[ValidationErrorDetail(**e) for e in errors],
        )

    date_from = min(r["buch_datum"] for r in rows)
    date_to = max(r["buch_datum"] for r in rows)

    deleted = await db.execute(
        sa.delete(MaterialMovement).where(
            MaterialMovement.buch_datum >= date_from,
            MaterialMovement.buch_datum <= date_to,
        )
    )
    rows_replaced = deleted.rowcount or 0

    batch = UploadBatch(
        filename=filename,
        uploaded_at=now,
        row_count=0,
        error_count=len(errors),
        status="success",
        kind="material_movements",
    )
    db.add(batch)
    await db.flush()

    for r in rows:
        r["upload_batch_id"] = batch.id
        r["imported_at"] = now

    cols_per_row = max(1, len(rows[0]))
    chunk_size = max(1, 32767 // cols_per_row)
    inserted_total = 0
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        result = await db.execute(pg_insert(MaterialMovement).values(chunk))
        inserted_total += result.rowcount or 0

    batch.row_count = inserted_total
    if errors and inserted_total == 0:
        batch.status = "failed"
    elif errors:
        batch.status = "partial"
    await db.commit()

    return MaterialMovementsUploadResponse(
        rows_inserted=inserted_total,
        rows_replaced=rows_replaced,
        date_range_from=date_from,
        date_range_to=date_to,
        errors=[ValidationErrorDetail(**e) for e in errors],
    )


@admin_router.post(
    "/upload-material-prices",
    response_model=MaterialPricesUploadResponse,
)
async def upload_material_prices(
    file: UploadFile,
    db: AsyncSession = Depends(get_async_db_session),
) -> MaterialPricesUploadResponse:
    """Upsert of an AswKpf_WE.txt Wareneingang dump (finance-scoped prices).

    Composite business key ``(vorgang_nr, pos, upos)`` identifies one WE
    position; ``ON CONFLICT DO UPDATE`` overwrites all data columns on
    re-upload. Supplies the purchase price for the Materialkostenquote.
    """
    filename = file.filename or ""
    if not filename.lower().endswith(".txt"):
        raise HTTPException(
            status_code=422,
            detail="Only .txt files are accepted for material-prices uploads.",
        )
    contents = await file.read()
    rows, errors = parse_material_prices_file(contents, filename)
    now = datetime.now(timezone.utc)

    if not rows:
        db.add(
            UploadBatch(
                filename=filename,
                uploaded_at=now,
                row_count=0,
                error_count=len(errors),
                status="failed" if errors else "success",
                kind="material_prices",
            )
        )
        await db.commit()
        return MaterialPricesUploadResponse(
            rows_inserted=0,
            rows_updated=0,
            errors=[ValidationErrorDetail(**e) for e in errors],
        )

    incoming_keys = [(r["vorgang_nr"], r["pos"], r["upos"]) for r in rows]
    existing_stmt = sa.select(sa.func.count(MaterialPrice.id)).where(
        sa.tuple_(
            MaterialPrice.vorgang_nr,
            MaterialPrice.pos,
            MaterialPrice.upos,
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
        kind="material_prices",
    )
    db.add(batch)
    await db.flush()

    for r in rows:
        r["upload_batch_id"] = batch.id

    table = MaterialPrice.__table__
    update_cols = [
        c.name
        for c in table.columns
        if c.name not in ("id", "vorgang_nr", "pos", "upos")
    ]

    cols_per_row = max(1, len(rows[0]))
    chunk_size = max(1, 32767 // cols_per_row)
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        stmt = pg_insert(MaterialPrice).values(chunk)
        stmt = stmt.on_conflict_do_update(
            constraint="uq_material_prices_vorgang_pos",
            set_={col: stmt.excluded[col] for col in update_cols},
        )
        await db.execute(stmt)

    batch.row_count = rows_inserted + rows_updated
    if errors and batch.row_count == 0:
        batch.status = "failed"
    elif errors:
        batch.status = "partial"
    await db.commit()

    return MaterialPricesUploadResponse(
        rows_inserted=rows_inserted,
        rows_updated=rows_updated,
        errors=[ValidationErrorDetail(**e) for e in errors],
    )


# ── v1.79 — Qualitätsprüfung (AswQs2151 inspection log) ────────────────


@admin_router.post(
    "/upload-inspections", response_model=InspectionsUploadResponse
)
async def upload_inspections(
    file: UploadFile,
    db: AsyncSession = Depends(get_async_db_session),
) -> InspectionsUploadResponse:
    """Replace-by-date-range insert of an AswQs2151.txt Qualitätsprüfung dump.

    The source has no clean business key (identical booking rows are
    legitimate — same date/time/user/FA/artikel booking 16 STK twice
    counts as 32 inspected), so idempotency mirrors the
    ``material_movements`` pattern: every existing ``inspection_records``
    row whose ``pruef_datum`` falls inside the uploaded file's date range
    is deleted first, then the new rows are bulk-inserted. Re-uploading
    the same file is a no-op.
    """
    filename = file.filename or ""
    if not filename.lower().endswith(".txt"):
        raise HTTPException(
            status_code=422,
            detail="Only .txt files are accepted for inspection uploads.",
        )
    contents = await file.read()
    rows, errors = parse_inspection_file(contents, filename)
    now = datetime.now(timezone.utc)

    if not rows:
        db.add(
            UploadBatch(
                filename=filename,
                uploaded_at=now,
                row_count=0,
                error_count=len(errors),
                status="failed" if errors else "success",
                kind="inspections",
            )
        )
        await db.commit()
        return InspectionsUploadResponse(
            rows_inserted=0,
            rows_replaced=0,
            small_count=0,
            large_count=0,
            date_range_from=None,
            date_range_to=None,
            errors=[ValidationErrorDetail(**e) for e in errors],
        )

    date_from = min(r["pruef_datum"] for r in rows)
    date_to = max(r["pruef_datum"] for r in rows)

    deleted = await db.execute(
        sa.delete(InspectionRecord).where(
            InspectionRecord.pruef_datum >= date_from,
            InspectionRecord.pruef_datum <= date_to,
        )
    )
    rows_replaced = deleted.rowcount or 0

    batch = UploadBatch(
        filename=filename,
        uploaded_at=now,
        row_count=0,
        error_count=len(errors),
        status="success",
        kind="inspections",
    )
    db.add(batch)
    await db.flush()

    for r in rows:
        r["upload_batch_id"] = batch.id

    # Base the chunk on the real Insertable column count, not len(rows[0]):
    # SQLAlchemy adds every model column with a server_default (e.g.
    # ``excluded``) to the INSERT even when the row dict omits it, so
    # counting keys undercounts and asyncpg's 32767 param cap is hit
    # (35100 params on the raw AswQs2151 file).
    cols_per_row = max(1, len(InspectionRecord.__table__.columns))
    chunk_size = max(1, 32767 // cols_per_row)
    inserted_total = 0
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        result = await db.execute(pg_insert(InspectionRecord).values(chunk))
        inserted_total += result.rowcount or 0

    batch.row_count = inserted_total
    if errors and inserted_total == 0:
        batch.status = "failed"
    elif errors:
        batch.status = "partial"
    await db.commit()

    small_count = sum(1 for r in rows if r["size_class"] == "small")
    large_count = sum(1 for r in rows if r["size_class"] == "large")

    return InspectionsUploadResponse(
        rows_inserted=inserted_total,
        rows_replaced=rows_replaced,
        small_count=small_count,
        large_count=large_count,
        date_range_from=date_from,
        date_range_to=date_to,
        errors=[ValidationErrorDetail(**e) for e in errors],
    )
