import asyncio
import faulthandler
import gc
import json
import logging
import threading
import uuid
from pathlib import Path

from sqlalchemy import delete as sa_delete
from sqlalchemy import desc, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.path_security import is_managed_upload_path
from app.core.result_validation import normalize_result_pages, serialize_pages_text
from app.db.models import ArchiveRecord, OCRTask
from app.services.archive_service import save_archive_record
from app.services.excel_export import (
    append_to_excel,
    clear_excel_data,
    extract_fields,
    init_excel,
    resolve_excel_output_path,
)
from config import ALLOWED_EXTENSIONS, UPLOAD_DIR


logger = logging.getLogger(__name__)


def _ensure_vl_dtype_support() -> None:
    try:
        import ml_dtypes  # noqa: F401
        import numpy as np

        np.dtype("bfloat16")
    except Exception as exc:
        raise RuntimeError("VL 模式依赖 ml_dtypes 提供 bfloat16 支持，请安装/修复 ml_dtypes 后重试。") from exc


def _run_ocr_document(file_path: str, mode: str):
    """
    底层同步的 OCR 执行函数。
    
    这是造成“后端力不从心，不支持并发”的罪魁祸首。
    - PaddleOCR, PP-Structure, Qwen-VL 等模型库不仅占据巨大的内存/显存。
    - 而且如果在当前 FastAPI Web 进程下直接拉起，极大概率因为并发调度问题和 GIL 而无法横向缩放（Scale out）。
    
    建议将其抽离为一个完全独立的微服务 / RPC / Celery Worker 供调用。
    """
    logger.info("_run_ocr_document entered: mode=%s, file=%s, thread=%s", mode, Path(file_path).name, threading.get_ident())
    # Delay importing the OCR engine until a task is actually processed so
    # the API can finish startup before heavy OCR dependencies are touched.
    try:
        from app.core.ocr_engine import ocr_document, should_require_local_vl_runtime

        use_local_vl_runtime = should_require_local_vl_runtime(mode)
        if use_local_vl_runtime:
            _ensure_vl_dtype_support()
            try:
                faulthandler.enable()
                faulthandler.dump_traceback_later(120, repeat=True)
            except Exception:
                pass

        logger.info(
            "_run_ocr_document imported ocr_document: mode=%s, file=%s, use_local_vl_runtime=%s",
            mode,
            Path(file_path).name,
            use_local_vl_runtime,
        )
        return ocr_document(file_path, mode)
    finally:
        if mode == "vl":
            try:
                faulthandler.cancel_dump_traceback_later()
            except Exception:
                pass


async def save_upload_file(filename: str, file_content: bytes, relative_path: str = "") -> tuple[str, str]:
    base_name = Path(filename).name
    ext = Path(base_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}. Allowed: {', '.join(sorted(ALLOWED_EXTENSIONS))}")

    rel_parts = []
    for part in Path((relative_path or "").replace("\\", "/")).parts:
        if part in {"", ".", ".."}:
            continue
        if len(part) == 2 and part[1] == ":":
            continue
        rel_parts.append(part)

    save_dir = UPLOAD_DIR.joinpath(*rel_parts[:-1]) if rel_parts else UPLOAD_DIR
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"{uuid.uuid4().hex}_{base_name}"
    save_path.write_bytes(file_content)
    return str(save_path), ext


async def create_task(
    db: AsyncSession,
    filename: str,
    file_path: str,
    file_type: str,
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


_MODE_TIMEOUT: dict[str, int] = {
    "baidu_vl": 600,
    "vl": 600,
    "layout": 300,
    "ocr": 120,
}


async def run_ocr_task(db: AsyncSession, task_id: int, mode: str = "layout") -> OCRTask:
    """
    执行 OCR 解析并落地数据库的核心任务管线。

    【并发与卡死原因揭秘】
    当前的设计直接在 FastAPI 进程内部，通过 `asyncio.to_thread(_run_ocr_document, ...)` 将任务
    丢到系统默认的线程池执行。

    但问题在于 `_run_ocr_document` 调用的是底层的 PaddleOCR (Python 封装 C++ 算子)，
    这是一个超级重型的 CPU/GPU 密集型任务。
    虽然放在了新线程里（释放了主线程用来跑 FastAPI Event Loop），但在 Python 全局解释器锁（GIL）机制下，
    如果是做密集的张量矩阵运算/图像预处理且没有释放 GIL 时，或者由于显卡驱动、OpenCV 同步锁等原因，
    仍然可能造成 FastAPI 主线程出现严重的争用与卡顿。

    【重构建议】
    如果需要真正的并发支持和高吞吐：
    1. 不要用 `asyncio.to_thread`。
    2. 改用 `concurrent.futures.ProcessPoolExecutor` 进程池。进程之间没有 GIL 竞争，可以实现多核并行。
    3. 最好引入 Celery / RQ 这样的分布式任务框架。
    """
    task = await db.get(OCRTask, task_id)
    if not task:
        raise ValueError(f"Task not found: {task_id}")

    logger.info(
        "run_ocr_task begin: task_id=%s, mode=%s, file=%s, current_status=%s",
        task.id,
        mode,
        Path(task.file_path).name,
        task.status,
    )

    task.status = "processing"
    task.error_message = None
    await db.commit()

    timeout = _MODE_TIMEOUT.get(mode, 300)
    try:
        logger.info("run_ocr_task dispatching to worker thread: task_id=%s, mode=%s, timeout=%ss", task.id, mode, timeout)
        result = await asyncio.wait_for(
            asyncio.to_thread(_run_ocr_document, task.file_path, mode),
            timeout=timeout,
        )
        pages = normalize_result_pages(result["pages"])
        task.result_json = pages
        task.full_text = serialize_pages_text(pages)
        task.page_count = result["page_count"]
        task.status = "done"
        await db.commit()
        await db.refresh(task)
        logger.info("Task %s OCR finished with %s page(s).", task.id, task.page_count)
    except asyncio.TimeoutError:
        logger.error("Task %s OCR timed out after %ss (mode=%s).", task.id, timeout, mode)
        task.status = "failed"
        task.error_message = f"识别超时（>{timeout}s），请重新提交或改用其他识别模式。"
        await db.commit()
        await db.refresh(task)
    except Exception as exc:
        logger.exception("Task %s OCR failed.", task.id)
        task.status = "failed"
        task.error_message = str(exc)
        await db.commit()
        await db.refresh(task)
    finally:
        gc.collect()
        try:
            import paddle

            paddle.device.cuda.empty_cache()
        except Exception:
            pass

    return task


async def finalize_task_outputs(
    db: AsyncSession,
    task: OCRTask,
    *,
    excel_path: str = "",
    excel_init: int = 0,
    output_dir: str = "",
    batch_id: str = "",
    archive_fields: dict[str, str] | None = None,
    persist_archive: bool = True,
) -> OCRTask:
    if task.status != "done":
        return task

    fields = archive_fields or extract_fields(task.filename, task.full_text or "", task.result_json, task.page_count)
    fields = {str(key): str(value or "") for key, value in (fields or {}).items()}
    if not fields.get("页数"):
        fields["页数"] = str(task.page_count or "")

    if output_dir:
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        stem = Path(task.filename or task.file_path).stem
        (out_dir / f"{stem}.json").write_text(
            json.dumps(task.result_json, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (out_dir / f"{stem}.txt").write_text(task.full_text or "", encoding="utf-8")

    if excel_path:
        actual_excel_path = resolve_excel_output_path(excel_path)
        excel_file = Path(actual_excel_path)
        if not excel_file.exists():
            init_excel(actual_excel_path)
        elif excel_init:
            clear_excel_data(actual_excel_path)
        append_to_excel(actual_excel_path, fields)

    if persist_archive:
        await save_archive_record(db, task.id, batch_id, str(Path(task.file_path).parent), fields)
        await db.refresh(task)
    return task


async def get_task_list(
    db: AsyncSession,
    page: int = 1,
    page_size: int = 20,
    folder: str = "",
) -> tuple[list[OCRTask], int]:
    from sqlalchemy import and_

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
        count_stmt = count_stmt.where(and_(*conditions))
    total = (await db.execute(count_stmt)).scalar() or 0

    stmt = (
        select(OCRTask)
        .order_by(desc(OCRTask.created_at))
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    if conditions:
        stmt = stmt.where(and_(*conditions))
    tasks = list((await db.execute(stmt)).scalars().all())
    return tasks, total


async def get_task_detail(db: AsyncSession, task_id: int) -> OCRTask | None:
    return await db.get(OCRTask, task_id)


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


def _safe_unlink(file_path: str) -> None:
    if not is_managed_upload_path(file_path):
        return
    try:
        Path(file_path).unlink(missing_ok=True)
    except Exception:
        logger.warning("Failed to remove managed upload file: %s", file_path, exc_info=True)


async def delete_task(db: AsyncSession, task_id: int) -> bool:
    task = await db.get(OCRTask, task_id)
    if not task:
        return False

    _safe_unlink(task.file_path)
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
        _safe_unlink(task.file_path)
        await db.delete(task)

    await db.execute(sa_delete(ArchiveRecord).where(ArchiveRecord.task_id.in_(task_ids)))
    await db.commit()
    return len(task_ids)
