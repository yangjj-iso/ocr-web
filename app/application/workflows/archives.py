"""Archive use-case orchestration."""

from __future__ import annotations

import os
import tempfile

from sqlalchemy import delete as sa_delete
from sqlalchemy import select

from app.db.models import ArchiveRecord
from app.domains.archive import archive_service
from app.domains.batch_ai import batch_ai_service


async def list_archive_records(*, folder: str, batch_id: str, page: int, page_size: int, db):
    return await archive_service.get_archive_records(
        db,
        folder=folder,
        batch_id=batch_id,
        page=page,
        page_size=page_size,
    )


async def export_archive_records_to_temp_file(*, folder: str, batch_id: str, db) -> str | None:
    records, _total = await archive_service.get_archive_records(
        db,
        folder=folder,
        batch_id=batch_id,
        page=1,
        page_size=10000,
    )
    if not records:
        return None

    fd, temp_path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    archive_service.records_to_excel(list(records), temp_path)
    return temp_path


async def import_archive_records(*, file_path: str, batch_id: str, db) -> int:
    return await archive_service.import_from_excel(db, file_path, batch_id)


async def delete_archive_records(*, folder: str, batch_id: str, db) -> int:
    stmt = select(ArchiveRecord.batch_id).where(
        ArchiveRecord.batch_id.is_not(None),
        ArchiveRecord.batch_id != "",
    )
    if folder:
        stmt = stmt.where(ArchiveRecord.batch_folder == folder)
    if batch_id:
        stmt = stmt.where(ArchiveRecord.batch_id == batch_id)
    rows = (await db.execute(stmt.distinct())).scalars().all()
    affected_batch_ids = batch_ai_service.normalize_batch_ids(rows)

    query = sa_delete(ArchiveRecord)
    if folder:
        query = query.where(ArchiveRecord.batch_folder == folder)
    if batch_id:
        query = query.where(ArchiveRecord.batch_id == batch_id)
    result = await db.execute(query)
    await db.commit()

    if result.rowcount:
        batch_ai_service.invalidate_batch_ai_cache(affected_batch_ids)
    return result.rowcount

