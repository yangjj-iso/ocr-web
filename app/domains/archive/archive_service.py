"""Archive domain operations."""

from __future__ import annotations

from app.db.models import ArchiveRecord
from app.services import archive_service as legacy_archive_service


async def save_archive_record(db, task_id: int | None, batch_id: str, batch_folder: str, fields: dict) -> ArchiveRecord:
    return await legacy_archive_service.save_archive_record(db, task_id, batch_id, batch_folder, fields)


async def get_archive_records(db, folder: str = "", batch_id: str = "", page: int = 1, page_size: int = 200):
    return await legacy_archive_service.get_archive_records(
        db,
        folder=folder,
        batch_id=batch_id,
        page=page,
        page_size=page_size,
    )


def records_to_excel(records: list[ArchiveRecord], output_path: str) -> str:
    return legacy_archive_service.records_to_excel(records, output_path)


async def import_from_excel(db, file_path: str, batch_id: str = "") -> int:
    return await legacy_archive_service.import_from_excel(db, file_path, batch_id)


__all__ = [
    "get_archive_records",
    "import_from_excel",
    "records_to_excel",
    "save_archive_record",
]
