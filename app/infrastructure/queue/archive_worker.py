"""
Archive Workflow Queue Worker — 档案整理工作流队列消费者。

消费来自 Java 控制面的档案工作流控制命令：
  - ingest_queue           → 新批次启动工作流
  - review_resume_queue    → 审核完成后恢复工作流
  - rework_queue           → 返工任务重跑
  - export_queue           → 生成 searchable PDF 导出
  - page_preprocess_queue  → 页面预处理（并行）
  - ocr_queue              → 页面 OCR（并行）
  - page_feature_queue     → 页面特征提取（并行）

架构遵循 Develop.md 第十八节（队列消费模式）。
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import uuid
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    PROJECT_ROOT = Path(__file__).resolve().parents[3]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 消息处理器
# ---------------------------------------------------------------------------

async def _handle_ingest(message_body: dict[str, Any]) -> None:
    """处理 ingest_queue 消息 — 启动新工作流。"""
    from app.services.archive_workflow import run_archive_workflow

    task_id = message_body.get("run_id") or str(uuid.uuid4())
    batch_id: str = message_body["batch_id"]
    tenant_id: str = message_body.get("tenant_id", "default")
    policy_snapshot_id: str | None = message_body.get("policy_snapshot_id")
    pages: list[dict[str, Any]] = message_body.get("pages", [])
    run_mode: str = message_body.get("run_mode", "normal")

    logger.info("[archive_worker] ingest: task_id=%s batch_id=%s pages=%d", task_id, batch_id, len(pages))

    try:
        final_state = await run_archive_workflow(
            task_id=task_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            policy_snapshot_id=policy_snapshot_id,
            pages=pages,
            run_mode=run_mode,
        )
        logger.info(
            "[archive_worker] ingest done: batch_id=%s final_status=%s",
            batch_id,
            final_state.get("final_status"),
        )
    except Exception:
        logger.exception("[archive_worker] ingest failed: batch_id=%s", batch_id)
        raise


async def _handle_review_resume(message_body: dict[str, Any]) -> None:
    """处理 review_resume_queue 消息 — 审核完成后恢复工作流。"""
    from app.services.archive_workflow import resume_archive_workflow

    task_id: str = message_body["run_id"]
    batch_id: str = message_body["batch_id"]
    reason: str = message_body.get("reason", "review_resolved")
    affected_scope: dict[str, Any] = message_body.get("affected_scope", {})
    resume_from_checkpoint: str | None = message_body.get("resume_from_checkpoint")

    logger.info("[archive_worker] resume: task_id=%s reason=%s", task_id, reason)

    try:
        final_state = await resume_archive_workflow(
            task_id=task_id,
            batch_id=batch_id,
            reason=reason,
            affected_scope=affected_scope,
            resume_from_checkpoint=resume_from_checkpoint,
        )
        logger.info(
            "[archive_worker] resume done: batch_id=%s final_status=%s",
            batch_id,
            final_state.get("final_status"),
        )
    except Exception:
        logger.exception("[archive_worker] resume failed: task_id=%s", task_id)
        raise


async def _handle_rework(message_body: dict[str, Any]) -> None:
    """处理 rework_queue 消息 — 返工任务（从检录员发起的局部重跑）。"""
    from app.services.archive_workflow import resume_archive_workflow

    task_id: str = message_body["run_id"]
    batch_id: str = message_body["batch_id"]
    rework_scope: dict[str, Any] = message_body.get("rework_scope", {})
    reason: str = message_body.get("reason", "rework_requested")

    logger.info("[archive_worker] rework: task_id=%s scope=%s", task_id, rework_scope)

    try:
        final_state = await resume_archive_workflow(
            task_id=task_id,
            batch_id=batch_id,
            reason=reason,
            affected_scope=rework_scope,
        )
        logger.info(
            "[archive_worker] rework done: batch_id=%s final_status=%s",
            batch_id,
            final_state.get("final_status"),
        )
    except Exception:
        logger.exception("[archive_worker] rework failed: task_id=%s", task_id)
        raise


async def _handle_export(message_body: dict[str, Any]) -> None:
    """处理 export_queue 消息 — 生成 searchable PDF。"""
    batch_id: str = message_body["batch_id"]
    tenant_id: str = message_body.get("tenant_id", "default")
    export_type: str = message_body.get("export_type", "final")
    doc_ids: list[str] = message_body.get("doc_ids", [])

    logger.info(
        "[archive_worker] export_pdf: batch_id=%s docs=%d",
        batch_id,
        len(doc_ids),
    )

    try:
        # 导出服务：遍历 doc_ids，组合底图+文字层，上传到 MinIO
        from app.services.export_service import export_searchable_pdf
        pdf_path = await export_searchable_pdf(
            batch_id=batch_id,
            tenant_id=tenant_id,
            doc_ids=doc_ids,
            export_type="draft" if export_type == "draft" else "final",
        )
        logger.info("[archive_worker] export_pdf done: path=%s", pdf_path)
    except ImportError:
        logger.warning("[archive_worker] export_service not yet implemented, skipping export")
    except Exception:
        logger.exception("[archive_worker] export_pdf failed: batch_id=%s", batch_id)
        raise


# ---------------------------------------------------------------------------
# 并行页面处理器
# ---------------------------------------------------------------------------

async def _handle_page_preprocess(message_body: dict[str, Any]) -> None:
    """处理 page_preprocess_queue 消息 — 页面预处理（去噪、旋转校正、对比度增强）。"""
    batch_id: str = message_body["batch_id"]
    page_ids: list[str] = message_body.get("page_ids", [])

    logger.info("[archive_worker] page_preprocess: batch_id=%s pages=%d", batch_id, len(page_ids))

    try:
        from app.domains.page_processing.page_service import preprocess_pages
        await preprocess_pages(batch_id=batch_id, page_ids=page_ids)
        logger.info("[archive_worker] page_preprocess done: batch_id=%s", batch_id)
    except ImportError:
        logger.warning("[archive_worker] page_service.preprocess_pages not implemented, skipping")
    except Exception:
        logger.exception("[archive_worker] page_preprocess failed: batch_id=%s", batch_id)
        raise


async def _handle_ocr(message_body: dict[str, Any]) -> None:
    """处理 ocr_queue 消息 — 对指定页面执行 OCR。"""
    batch_id: str = message_body["batch_id"]
    page_ids: list[str] = message_body.get("page_ids", [])

    logger.info("[archive_worker] run_ocr: batch_id=%s pages=%d", batch_id, len(page_ids))

    try:
        from app.domains.page_processing.page_service import run_ocr_pages
        await run_ocr_pages(batch_id=batch_id, page_ids=page_ids)
        logger.info("[archive_worker] run_ocr done: batch_id=%s", batch_id)
    except ImportError:
        logger.warning("[archive_worker] page_service.run_ocr_pages not implemented, skipping")
    except Exception:
        logger.exception("[archive_worker] run_ocr failed: batch_id=%s", batch_id)
        raise


async def _handle_page_features(message_body: dict[str, Any]) -> None:
    """处理 page_feature_queue 消息 — 页面特征提取（候选字段、pHash 等）。"""
    batch_id: str = message_body["batch_id"]
    page_ids: list[str] = message_body.get("page_ids", [])

    logger.info("[archive_worker] page_features: batch_id=%s pages=%d", batch_id, len(page_ids))

    try:
        from app.domains.page_processing.page_service import extract_page_features
        await extract_page_features(batch_id=batch_id, page_ids=page_ids)
        logger.info("[archive_worker] page_features done: batch_id=%s", batch_id)
    except ImportError:
        logger.warning("[archive_worker] page_service.extract_page_features not implemented, skipping")
    except Exception:
        logger.exception("[archive_worker] page_features failed: batch_id=%s", batch_id)
        raise


# ---------------------------------------------------------------------------
# 队列路由表
# ---------------------------------------------------------------------------

_QUEUE_HANDLERS: dict[str, Any] = {
    "ingest_queue": _handle_ingest,
    "review_resume_queue": _handle_review_resume,
    "rework_queue": _handle_rework,
    "export_queue": _handle_export,
    "page_preprocess_queue": _handle_page_preprocess,
    "ocr_queue": _handle_ocr,
    "page_feature_queue": _handle_page_features,
}


# ---------------------------------------------------------------------------
# 单队列消费循环
# ---------------------------------------------------------------------------

async def _consume_queue(queue_name: str, handler: Any, broker_url: str) -> None:
    """持续消费单个队列，支持重试计数和优雅错误处理。"""
    import aio_pika

    MAX_REQUEUE_COUNT = 3

    logger.info("[archive_worker] start consuming queue: %s", queue_name)

    connection = await aio_pika.connect_robust(broker_url, reconnect_interval=5)
    async with connection:
        channel = await connection.channel()
        await channel.set_qos(prefetch_count=1)
        queue = await channel.declare_queue(queue_name, durable=True)

        async with queue.iterator() as queue_iter:
            async for message in queue_iter:
                headers = message.headers or {}
                retry_count = int(headers.get("x-retry-count", 0))
                try:
                    body = json.loads(message.body.decode("utf-8"))
                    await handler(body)
                    await message.ack()
                except json.JSONDecodeError as exc:
                    logger.error(
                        "[archive_worker] invalid JSON in %s: %s", queue_name, exc
                    )
                    await message.reject(requeue=False)
                except Exception:
                    logger.exception(
                        "[archive_worker] error in %s handler (retry %d/%d)",
                        queue_name,
                        retry_count,
                        MAX_REQUEUE_COUNT,
                    )
                    if retry_count < MAX_REQUEUE_COUNT:
                        await message.reject(requeue=True)
                    else:
                        logger.error(
                            "[archive_worker] message exhausted retries in %s, rejecting permanently",
                            queue_name,
                        )
                        await message.reject(requeue=False)


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

async def run_archive_worker(broker_url: str) -> None:
    """并发消费所有档案队列。"""
    import aio_pika  # noqa: F401 - verify import early

    tasks = [
        asyncio.create_task(_consume_queue(queue_name, handler, broker_url))
        for queue_name, handler in _QUEUE_HANDLERS.items()
    ]

    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("[archive_worker] shutting down")
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


def main() -> None:
    """直接运行 archive worker（开发模式 / Dockerfile CMD）。"""
    import os
    from config import MQ_BROKER_URL

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger.info("Starting archive worker, broker=%s", MQ_BROKER_URL)
    asyncio.run(run_archive_worker(MQ_BROKER_URL))


if __name__ == "__main__":
    main()
