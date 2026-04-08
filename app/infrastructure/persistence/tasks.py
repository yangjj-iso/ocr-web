"""Task persistence helpers."""

from __future__ import annotations

from sqlalchemy import delete as sa_delete
from sqlalchemy import desc, func, or_, select, text as sa_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ArchiveRecord, OCRTask
from app.infrastructure.storage.uploads import remove_managed_upload_file


async def create_task(
    db: AsyncSession,
    filename: str,
    file_path: str,
    file_type: str,
    *,
    mode: str = "layout",
) -> OCRTask:
    task = OCRTask(
        filename=filename,
        file_path=file_path,
        file_type=file_type,
        mode=mode,
        status="pending",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return task


async def get_task_detail(db: AsyncSession, task_id: int) -> OCRTask | None:
    return await db.get(OCRTask, task_id)


async def get_task_list(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    *,
    folder: str = "",
) -> tuple[list[OCRTask], int]:
    conditions = []
    if folder:
        base = folder.rstrip("/\\")
        conditions.append(
            or_(
                func.starts_with(OCRTask.file_path, base + "\\"),
                func.starts_with(OCRTask.file_path, base + "/"),
            )
        )

    count_stmt = select(func.count(OCRTask.id))
    if conditions:
        count_stmt = count_stmt.where(*conditions)
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(OCRTask)
        .order_by(desc(OCRTask.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if conditions:
        stmt = stmt.where(*conditions)
    tasks = list((await db.execute(stmt)).scalars().all())
    return tasks, total


async def search_tasks(
    db: AsyncSession,
    keyword: str,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[OCRTask], int]:
    from sqlalchemy import String as SAString
    from sqlalchemy import cast

    like_pattern = f"%{keyword}%"
    condition = or_(
        OCRTask.filename.ilike(like_pattern),
        OCRTask.full_text.ilike(like_pattern),
        cast(OCRTask.result_json, SAString).ilike(like_pattern),
    )

    total = (await db.execute(select(func.count(OCRTask.id)).where(condition))).scalar() or 0
    stmt = (
        select(OCRTask)
        .where(condition)
        .order_by(desc(OCRTask.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    tasks = list((await db.execute(stmt)).scalars().all())
    return tasks, total


async def delete_task(db: AsyncSession, task_id: int) -> bool:
    task = await db.get(OCRTask, task_id)
    if not task:
        return False

    remove_managed_upload_file(task.file_path)
    await db.execute(sa_delete(ArchiveRecord).where(ArchiveRecord.task_id == task.id))
    await db.delete(task)
    await db.commit()
    return True


async def delete_tasks_by_folder(db: AsyncSession, folder: str) -> int:
    base = folder.rstrip("/\\")
    tasks_stmt = select(OCRTask).where(
        or_(
            func.starts_with(OCRTask.file_path, base + "\\"),
            func.starts_with(OCRTask.file_path, base + "/"),
        )
    )
    tasks = list((await db.execute(tasks_stmt)).scalars().all())
    if not tasks:
        return 0

    task_ids = [task.id for task in tasks]
    for task in tasks:
        remove_managed_upload_file(task.file_path)
        await db.delete(task)

    await db.execute(sa_delete(ArchiveRecord).where(ArchiveRecord.task_id.in_(task_ids)))
    await db.commit()
    return len(task_ids)


async def list_terminal_folders(db: AsyncSession) -> list[tuple[int, str, object]]:
    return (
        await db.execute(
            sa_text(
                "SELECT id, file_path, created_at "
                "FROM ocr_tasks "
                "WHERE status IN ('done', 'failed') "
                "ORDER BY created_at DESC"
            )
        )
    ).fetchall()


async def list_folder_batch_pairs(db: AsyncSession) -> list[tuple[str, str]]:
    return (
        await db.execute(
            sa_text(
                "SELECT DISTINCT batch_folder, batch_id "
                "FROM archive_records "
                "WHERE batch_id IS NOT NULL AND batch_id != ''"
            )
        )
    ).fetchall()


async def get_progress_tasks(db: AsyncSession, task_ids: list[int]) -> list[OCRTask]:
    if not task_ids:
        return []
    return list((await db.execute(select(OCRTask).where(OCRTask.id.in_(task_ids)))).scalars().all())


async def list_task_ids_by_folder(db: AsyncSession, folder: str) -> list[int]:
    base = folder.rstrip("/\\")
    if not base:
        return []
    return list(
        (
            await db.execute(
                select(OCRTask.id).where(
                    or_(
                        func.starts_with(OCRTask.file_path, base + "\\"),
                        func.starts_with(OCRTask.file_path, base + "/"),
                    )
                )
            )
        ).scalars().all()
    )

