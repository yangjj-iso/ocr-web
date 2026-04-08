import asyncio
import logging
from dataclasses import dataclass

from app.core.redis_cache import TASK_TTL, cache_delete, cache_set, invalidate_lists
from app.db.database import async_session
from app.schemas.tasks import OCRTaskDetail
from app.services.agent_ocr_workflow import run_hierarchical_ocr_task
from app.services.ocr_service import finalize_task_outputs, get_task_detail, run_ocr_task
from config import ENABLE_HIERARCHICAL_AGENT


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class OCRJob:
    task_id: int
    mode: str
    excel_path: str = ""
    excel_init: int = 0
    output_dir: str = ""
    batch_id: str = ""


_queue: asyncio.Queue[OCRJob] | None = None
_worker_task: asyncio.Task | None = None


async def start_task_worker() -> None:
    """
    启动本地异步任务队列消费 worker (单线程 asyncio event loop 并发)。
    
    【架构瓶颈与并发缺陷说明】
    当前系统将重度的 CPU/GPU 密集型 OCR 任务 (PaddleOCR / Vision LLM) 与 FastAPI Web 服务器
    跑在了同一个 Python 进程的 Asyncio 事件循环中（通过 `asyncio.to_thread` 委托给了默认的 ThreadPoolExecutor）。
    
    1. GIL 锁限制：Python 的全局解释器锁 (GIL) 会导致多线程在 CPU 密集型任务上无法实现真正的并行。
    2. Event Loop 阻塞：`asyncio.to_thread` 虽然能释放事件循环执行其他极轻量 I/O，但底层底层 C/C++ 绑定的 
       CV 库（如 OpenCV, Paddle）如果未正确释放 GIL，仍然会间歇性卡死整个 Web 服务器，导致 API 接口无响应。
    3. 显存 OOM：直接在单个进程排队调用 GPU 显存，极易导致显存碎片化或瞬间打满。

    【推荐的并发升级方案】
    如果要支持高并发，强烈建议废弃当前这个“玩具级”的本地 `asyncio.Queue`：
    1. 引入 Celery 或 RQ 分布式任务队列 + Redis/RabbitMQ 作为 Broker。
    2. 将 OCR 执行逻辑 (`run_ocr_task`) 抽离为独立的独立 Worker 进程。
    3. FastAPI 只负责接收任务，将任务 ID 存库并丢入消息队列，快速返回 202 Accepted。
    4. 可以水平横向扩展多个 Worker 服务器专门跑 OCR/LLM。
    """
    global _queue, _worker_task
    if _queue is None:
        _queue = asyncio.Queue()
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker_loop(), name="ocr-task-worker")
        logger.info("OCR task worker started.")


async def stop_task_worker() -> None:
    global _worker_task
    if _worker_task is None:
        return
    _worker_task.cancel()
    try:
        await _worker_task
    except asyncio.CancelledError:
        pass
    logger.info("OCR task worker stopped.")
    _worker_task = None


async def enqueue_task(job: OCRJob) -> None:
    if _queue is None:
        await start_task_worker()
    assert _queue is not None
    await _queue.put(job)
    logger.info(
        "enqueue_task queued job: task_id=%s, mode=%s, queue_size=%s",
        job.task_id,
        job.mode,
        _queue.qsize(),
    )
    cache_delete(f"task:{job.task_id}")
    invalidate_lists()


async def _worker_loop() -> None:
    assert _queue is not None
    while True:
        job = await _queue.get()
        logger.info(
            "OCR worker dequeued job: task_id=%s, mode=%s, remaining_queue=%s",
            job.task_id,
            job.mode,
            _queue.qsize(),
        )
        try:
            await _process_job(job)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Failed to process OCR task %s.", job.task_id)
        finally:
            _queue.task_done()


async def _process_job(job: OCRJob) -> None:
    async with async_session() as db:
        logger.info("OCR worker processing job: task_id=%s, mode=%s", job.task_id, job.mode)
        cache_delete(f"task:{job.task_id}")
        workflow_result: dict = {}
        if ENABLE_HIERARCHICAL_AGENT:
            task, workflow_result = await run_hierarchical_ocr_task(
                db,
                job.task_id,
                mode=job.mode,
                batch_id=job.batch_id,
            )
        else:
            task = await run_ocr_task(db, job.task_id, mode=job.mode)
        task = await finalize_task_outputs(
            db,
            task,
            excel_path=job.excel_path,
            excel_init=job.excel_init,
            output_dir=job.output_dir,
            batch_id=job.batch_id,
            archive_fields=workflow_result.get("final_fields") if workflow_result else None,
            persist_archive=(
                (not bool(workflow_result.get("archive_saved")))
                and (not bool(workflow_result.get("human_review")))
            ) if workflow_result else True,
        )
        detail = await get_task_detail(db, task.id)
        if detail is None:
            return
        payload = OCRTaskDetail.model_validate(detail).model_dump(mode="json")
        if detail.status in {"done", "failed"}:
            cache_set(f"task:{detail.id}", payload, TASK_TTL)
        else:
            cache_delete(f"task:{detail.id}")
        invalidate_lists()
        logger.info(
            "OCR worker finished job: task_id=%s, mode=%s, status=%s",
            job.task_id,
            job.mode,
            detail.status,
        )
