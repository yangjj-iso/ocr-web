"""
Archive Workflow Queue Publisher — 档案整理工作流队列发布器。

负责向各专用队列发送工作流控制消息（启动/恢复/返工/导出/重算）。
队列名称遵循 Develop.md 第十八节的队列拆分方案。
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)

# 队列名称常量
QUEUE_INGEST = "ingest_queue"
QUEUE_PAGE_PREPROCESS = "page_preprocess_queue"
QUEUE_OCR = "ocr_queue"
QUEUE_PAGE_FEATURE = "page_feature_queue"
QUEUE_RELATION_ANALYSIS = "relation_analysis_queue"
QUEUE_DRAFT_PIPELINE = "draft_pipeline_queue"
QUEUE_FINAL_PIPELINE = "final_pipeline_queue"
QUEUE_REVIEW_RESUME = "review_resume_queue"
QUEUE_REWORK = "rework_queue"
QUEUE_EXPORT = "export_queue"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _publish_to_queue(queue_name: str, message: dict[str, Any]) -> None:
    """向指定队列发布消息（通过 RabbitMQ aio-pika），复用连接池。"""
    try:
        import aio_pika
        from config import MQ_BROKER_URL
    except ImportError:
        logger.warning("aio_pika not available, skipping queue publish to %s", queue_name)
        return

    try:
        connection = await _get_shared_connection(MQ_BROKER_URL)
        channel = await connection.channel()
        await channel.declare_queue(queue_name, durable=True)
        await channel.default_exchange.publish(
            aio_pika.Message(
                body=json.dumps(message, ensure_ascii=False).encode(),
                content_type="application/json",
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
            ),
            routing_key=queue_name,
        )
        logger.debug("Published to %s: run_id=%s", queue_name, message.get("run_id", ""))
    except Exception:
        logger.exception("Failed to publish message to queue %s", queue_name)
        # Reset connection pool on error so next call reconnects
        _shared_connections.pop(MQ_BROKER_URL, None)
        raise


# Connection pool for archive publisher (reuse across fan-out publishes)
_shared_connections: dict[str, Any] = {}


async def _get_shared_connection(broker_url: str) -> Any:
    """Get or create a shared robust connection for the given broker URL."""
    import aio_pika
    conn = _shared_connections.get(broker_url)
    if conn is not None and not conn.is_closed:
        return conn
    conn = await aio_pika.connect_robust(broker_url, reconnect_interval=5)
    _shared_connections[broker_url] = conn
    return conn


async def enqueue_workflow_start(
    *,
    run_id: str,
    batch_id: str,
    tenant_id: str,
    policy_snapshot_id: str | None = None,
    source_file_uris: list[str] | None = None,
    page_count: int = 0,
    submitted_by: str = "",
    run_mode: str = "normal",
    request_id: str | None = None,
    pages: list[dict[str, Any]] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """将工作流启动命令投入接入队列。"""
    await _publish_to_queue(
        QUEUE_INGEST,
        {
            "command": "WORKFLOW_START",
            "run_id": run_id,
            "request_id": request_id or "",
            "batch_id": batch_id,
            "tenant_id": tenant_id,
            "policy_snapshot_id": policy_snapshot_id,
            "source_file_uris": list(source_file_uris or []),
            "page_count": max(0, int(page_count or 0)),
            "submitted_by": submitted_by,
            "run_mode": run_mode,
            "pages": list(pages or []),
            "extra": dict(extra or {}),
            "published_at": _utc_now(),
        },
    )


async def enqueue_workflow_resume(
    *,
    run_id: str,
    batch_id: str,
    reason: str,
    affected_scope: dict[str, Any],
    resume_from_checkpoint: str | None,
    review_result: dict[str, Any] | None = None,
) -> None:
    """将审核恢复命令投入高优先级审核恢复队列。"""
    await _publish_to_queue(
        QUEUE_REVIEW_RESUME,
        {
            "command": "WORKFLOW_RESUME",
            "run_id": run_id,
            "batch_id": batch_id,
            "reason": reason,
            "affected_scope": affected_scope,
            "resume_from_checkpoint": resume_from_checkpoint,
            "review_result": dict(review_result or {}),
            "published_at": _utc_now(),
        },
    )


async def enqueue_workflow_rework(
    *,
    run_id: str,
    batch_id: str,
    tenant_id: str = "default",
    source_run_id: str | None = None,
    reason: str = "rework_requested",
    rework_level: str,
    affected_scope: dict[str, Any],
    resume_from_checkpoint: str | None,
) -> None:
    """将返工命令投入返工队列。"""
    await _publish_to_queue(
        QUEUE_REWORK,
        {
            "command": "WORKFLOW_REWORK",
            "run_id": run_id,
            "source_run_id": source_run_id or run_id,
            "batch_id": batch_id,
            "tenant_id": tenant_id,
            "reason": reason,
            "rework_level": rework_level,
            "affected_scope": affected_scope,
            "rework_scope": affected_scope,
            "resume_from_checkpoint": resume_from_checkpoint,
            "published_at": _utc_now(),
        },
    )


async def enqueue_export_pdf(
    *,
    run_id: str,
    batch_id: str,
    tenant_id: str,
    export_type: str,
    doc_ids: list[str],
) -> None:
    """将 PDF 导出任务投入导出队列（独立，不阻塞主流程）。"""
    await _publish_to_queue(
        QUEUE_EXPORT,
        {
            "command": "EXPORT_SEARCHABLE_PDF",
            "run_id": run_id,
            "batch_id": batch_id,
            "tenant_id": tenant_id,
            "export_type": export_type,
            "doc_ids": doc_ids,
            "published_at": _utc_now(),
        },
    )


async def enqueue_recompute(
    *,
    run_id: str,
    batch_id: str,
    tenant_id: str = "default",
    source_run_id: str | None = None,
    affected_scope: dict[str, Any],
    recompute_targets: list[str],
    resume_from_checkpoint: str | None = None,
) -> None:
    """将局部重算任务投入 Draft 流水线队列。"""
    await _publish_to_queue(
        QUEUE_DRAFT_PIPELINE,
        {
            "command": "RECOMPUTE_AFFECTED_SCOPE",
            "run_id": run_id,
            "source_run_id": source_run_id or run_id,
            "batch_id": batch_id,
            "tenant_id": tenant_id,
            "affected_scope": affected_scope,
            "recompute_targets": recompute_targets,
            "resume_from_checkpoint": resume_from_checkpoint,
            "published_at": _utc_now(),
        },
    )


async def enqueue_page_preprocess(*, run_id: str, batch_id: str, page_ids: list[str]) -> None:
    """将页面预处理任务批量投入预处理队列。"""
    await _publish_to_queue(
        QUEUE_PAGE_PREPROCESS,
        {
            "command": "PREPROCESS_PAGES",
            "run_id": run_id,
            "batch_id": batch_id,
            "page_ids": page_ids,
            "published_at": _utc_now(),
        },
    )


async def enqueue_ocr_pages(*, run_id: str, batch_id: str, page_ids: list[str]) -> None:
    """将 OCR 任务批量投入 OCR 队列。"""
    await _publish_to_queue(
        QUEUE_OCR,
        {
            "command": "RUN_OCR",
            "run_id": run_id,
            "batch_id": batch_id,
            "page_ids": page_ids,
            "published_at": _utc_now(),
        },
    )


async def enqueue_page_features(*, run_id: str, batch_id: str, page_ids: list[str]) -> None:
    """将页面特征提取任务投入特征队列。"""
    await _publish_to_queue(
        QUEUE_PAGE_FEATURE,
        {
            "command": "EXTRACT_PAGE_FEATURES",
            "run_id": run_id,
            "batch_id": batch_id,
            "page_ids": page_ids,
            "published_at": _utc_now(),
        },
    )


async def enqueue_relation_analysis(*, run_id: str, batch_id: str) -> None:
    """将页面关系分析任务投入分析队列。"""
    await _publish_to_queue(
        QUEUE_RELATION_ANALYSIS,
        {
            "command": "ANALYZE_PAGE_RELATIONS",
            "run_id": run_id,
            "batch_id": batch_id,
            "published_at": _utc_now(),
        },
    )


async def enqueue_draft_pipeline(
    *,
    run_id: str,
    batch_id: str,
    tenant_id: str = "default",
    current_stage: str = "run_draft_subgraph",
    source_run_id: str | None = None,
    affected_scope: dict[str, Any] | None = None,
    resume_from_checkpoint: str | None = None,
    recompute_targets: list[str] | None = None,
) -> None:
    """将 Draft 轨流水线任务投入 Draft 队列。"""
    await _publish_to_queue(
        QUEUE_DRAFT_PIPELINE,
        {
            "command": "RUN_DRAFT_PIPELINE",
            "run_id": run_id,
            "source_run_id": source_run_id or run_id,
            "batch_id": batch_id,
            "tenant_id": tenant_id,
            "current_stage": current_stage,
            "affected_scope": dict(affected_scope or {}),
            "resume_from_checkpoint": resume_from_checkpoint,
            "recompute_targets": list(recompute_targets or []),
            "published_at": _utc_now(),
        },
    )


async def enqueue_final_pipeline(
    *,
    run_id: str,
    batch_id: str,
    tenant_id: str = "default",
    current_stage: str = "sort_documents_final",
    source_run_id: str | None = None,
    affected_scope: dict[str, Any] | None = None,
    resume_from_checkpoint: str | None = None,
) -> None:
    """将 Final 轨流水线任务投入 Final 队列。"""
    await _publish_to_queue(
        QUEUE_FINAL_PIPELINE,
        {
            "command": "RUN_FINAL_PIPELINE",
            "run_id": run_id,
            "source_run_id": source_run_id or run_id,
            "batch_id": batch_id,
            "tenant_id": tenant_id,
            "current_stage": current_stage,
            "affected_scope": dict(affected_scope or {}),
            "resume_from_checkpoint": resume_from_checkpoint,
            "published_at": _utc_now(),
        },
    )


# ---------------------------------------------------------------------------
# Fan-out helpers — 将大批量拆分为多条消息并行投递
# ---------------------------------------------------------------------------

DEFAULT_PAGE_CHUNK_SIZE = 10


async def fanout_page_preprocess(
    *,
    run_id: str,
    batch_id: str,
    page_ids: list[str],
    chunk_size: int = DEFAULT_PAGE_CHUNK_SIZE,
) -> int:
    """将页面预处理按 chunk_size 拆分投入多条消息，返回投递的消息数。"""
    import asyncio
    chunks = [page_ids[i:i + chunk_size] for i in range(0, len(page_ids), chunk_size)]
    tasks = [
        enqueue_page_preprocess(run_id=run_id, batch_id=batch_id, page_ids=chunk)
        for chunk in chunks
    ]
    await asyncio.gather(*tasks)
    logger.debug("Fan-out page_preprocess: batch_id=%s, %d chunks of ≤%d pages", batch_id, len(chunks), chunk_size)
    return len(chunks)


async def fanout_ocr_pages(
    *,
    run_id: str,
    batch_id: str,
    page_ids: list[str],
    chunk_size: int = DEFAULT_PAGE_CHUNK_SIZE,
) -> int:
    """将 OCR 按 chunk_size 拆分投入多条消息并行处理，返回投递的消息数。"""
    import asyncio
    chunks = [page_ids[i:i + chunk_size] for i in range(0, len(page_ids), chunk_size)]
    tasks = [
        enqueue_ocr_pages(run_id=run_id, batch_id=batch_id, page_ids=chunk)
        for chunk in chunks
    ]
    await asyncio.gather(*tasks)
    logger.debug("Fan-out ocr_pages: batch_id=%s, %d chunks", batch_id, len(chunks))
    return len(chunks)


async def fanout_page_features(
    *,
    run_id: str,
    batch_id: str,
    page_ids: list[str],
    chunk_size: int = DEFAULT_PAGE_CHUNK_SIZE,
) -> int:
    """将特征提取按 chunk_size 拆分投入多条消息并行处理，返回投递的消息数。"""
    import asyncio
    chunks = [page_ids[i:i + chunk_size] for i in range(0, len(page_ids), chunk_size)]
    tasks = [
        enqueue_page_features(run_id=run_id, batch_id=batch_id, page_ids=chunk)
        for chunk in chunks
    ]
    await asyncio.gather(*tasks)
    logger.debug("Fan-out page_features: batch_id=%s, %d chunks", batch_id, len(chunks))
    return len(chunks)


async def fanout_full_pipeline(
    *,
    run_id: str,
    batch_id: str,
    page_ids: list[str],
    chunk_size: int = DEFAULT_PAGE_CHUNK_SIZE,
) -> dict[str, int]:
    """
    依次对一批页面做 fan-out：预处理 → OCR → 特征提取。
    每阶段的消息量独立并行，各阶段之间顺序执行。
    返回 {'preprocess': N, 'ocr': N, 'features': N} 消息投递数。
    """
    n_pre = await fanout_page_preprocess(run_id=run_id, batch_id=batch_id, page_ids=page_ids, chunk_size=chunk_size)
    n_ocr = await fanout_ocr_pages(run_id=run_id, batch_id=batch_id, page_ids=page_ids, chunk_size=chunk_size)
    n_feat = await fanout_page_features(run_id=run_id, batch_id=batch_id, page_ids=page_ids, chunk_size=chunk_size)
    return {"preprocess": n_pre, "ocr": n_ocr, "features": n_feat}
