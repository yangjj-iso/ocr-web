"""Archive domain operations."""

from __future__ import annotations

from typing import Any

from app.db.models import ArchiveRecord
from app.services import archive_service as legacy_archive_service


async def save_archive_record(db, task_id: int | None, batch_id: str, batch_folder: str, fields: dict, *, tenant_id: str = "default") -> ArchiveRecord:
    return await legacy_archive_service.save_archive_record(db, task_id, batch_id, batch_folder, fields, tenant_id=tenant_id)


async def resume_archive_workflow(
    *,
    task_id: str,
    batch_id: str,
    reason: str = "review_resolved",
    affected_scope: dict[str, Any] | None = None,
    resume_from_checkpoint: str | None = None,
    review_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """代理至 app.services.archive_workflow.resume_archive_workflow。"""
    from app.services.archive_workflow import resume_archive_workflow as _resume
    return await _resume(
        task_id=task_id,
        batch_id=batch_id,
        reason=reason,
        affected_scope=affected_scope,
        resume_from_checkpoint=resume_from_checkpoint,
        review_result=review_result,
    )


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
