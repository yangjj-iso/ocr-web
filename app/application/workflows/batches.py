"""Batch/AI extraction orchestration workflows."""

from __future__ import annotations

import os
from pathlib import Path
from time import time

from sqlalchemy import select, text as sa_text

from app.db.models import ArchiveRecord
from app.domains.archive import archive_service
from app.domains.batch_ai import batch_ai_service
from app.domains.extraction import field_service
from app.domains.ingestion import task_service
from app.services.document_boundary_feedback_service import (
    get_batch_boundary_truth as load_batch_boundary_truth,
    save_batch_boundary_truth as persist_batch_boundary_truth,
)
from app.services.batch_merge_extraction_service import get_batch_boundary_analysis_result


def scan_allowed_folder(folder: Path) -> dict:
    files = []
    for root, directories, filenames in os.walk(folder):
        directories.sort()
        for filename in sorted(filenames):
            full_path = Path(root) / filename
            extension = full_path.suffix.lower()
            if extension not in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".pdf"}:
                continue
            files.append(
                {
                    "name": filename,
                    "path": str(full_path),
                    "rel_path": str(full_path.relative_to(folder)),
                    "size": full_path.stat().st_size,
                }
            )
    return {"folder": str(folder), "count": len(files), "files": files}


async def ensure_batch_for_folder(*, folder: str, db) -> tuple[str, bool]:
    existing = (
        await db.execute(
            sa_text(
                "SELECT DISTINCT batch_id FROM archive_records "
                "WHERE batch_folder = :folder AND batch_id IS NOT NULL AND batch_id != ''"
            ).bindparams(folder=folder)
        )
    ).scalars().all()
    if existing:
        return existing[0], False

    rows = (
        await db.execute(
            sa_text(
                "SELECT id FROM archive_records "
                "WHERE batch_folder = :folder AND (batch_id IS NULL OR batch_id = '')"
            ).bindparams(folder=folder)
        )
    ).scalars().all()

    batch_id = f"batch_{int(time())}_{os.urandom(3).hex()}"
    if not rows:
        base = folder.rstrip("/\\")
        task_rows = (
            await db.execute(
                sa_text(
                    "SELECT id, file_path, full_text, result_json, page_count, status "
                    "FROM ocr_tasks WHERE status = 'done' AND ("
                    "  file_path LIKE :pat_fwd OR file_path LIKE :pat_back"
                    ")"
                ).bindparams(pat_fwd=base + "/%", pat_back=base + "\\%")
            )
        ).fetchall()
        if not task_rows:
            return "", False

        for task_id, file_path, full_text, result_json, page_count, _status in task_rows:
            fields = field_service.extract_fields(
                Path(file_path).name,
                full_text or "",
                result_json,
                page_count or 0,
            )
            await archive_service.save_archive_record(db, task_id, batch_id, folder, fields)
        return batch_id, True

    await db.execute(
        sa_text(
            "UPDATE archive_records SET batch_id = :bid "
            "WHERE batch_folder = :folder AND (batch_id IS NULL OR batch_id = '')"
        ).bindparams(bid=batch_id, folder=folder)
    )
    await db.commit()
    return batch_id, True


async def ai_extract_task_fields(
    *,
    task_id: int,
    include_evidence: bool,
    persist: bool,
    db,
):
    task = await task_service.get_task_detail(db, task_id)
    if not task:
        return None, "not_found"
    if task.status != "done":
        return None, "not_done"

    comparison = await field_service.compare_rule_and_llm_fields(task, include_evidence=include_evidence)
    if persist:
        if comparison["conflicts"]:
            return comparison, "conflicts"

        existing_record = (
            await db.execute(select(ArchiveRecord).where(ArchiveRecord.task_id == task.id))
        ).scalar_one_or_none()
        await archive_service.save_archive_record(
            db,
            task.id,
            existing_record.batch_id if existing_record else "",
            existing_record.batch_folder if existing_record else str(Path(task.file_path).parent),
            comparison["recommended_fields"],
        )
    return comparison, "ok"


async def ai_merge_extract_batch(
    *,
    batch_id: str,
    include_evidence: bool,
    force_refresh: bool,
    db,
):
    return await batch_ai_service.get_batch_merge_extract_result(
        db,
        batch_id=batch_id,
        include_evidence=include_evidence,
        force_refresh=force_refresh,
    )


async def get_batch_boundary_analysis(
    *,
    batch_id: str,
    force_refresh: bool,
    db,
):
    return await get_batch_boundary_analysis_result(
        db,
        batch_id=batch_id,
        force_refresh=force_refresh,
    )


async def get_batch_boundary_truth(*, batch_id: str, db):
    return await load_batch_boundary_truth(db, batch_id=batch_id)


async def save_batch_boundary_truth(*, batch_id: str, tasks: list[dict], db):
    return await persist_batch_boundary_truth(
        db,
        batch_id=batch_id,
        tasks=tasks,
    )
