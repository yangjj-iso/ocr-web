"""
Workflow Events — 档案整理工作流回调事件发送器。

Python 计算面在关键节点主动向 Java 控制面回传状态事件。
遵循 Develop.md §17.3 的事件类型与字段规范。

事件类型：
    WORKFLOW_STARTED      — 工作流已启动
    NODE_COMPLETED        — 某节点完成
    REVIEW_TASK_CREATED   — 审核任务已创建
    WORKFLOW_BLOCKED      — 工作流进入阻塞
    WORKFLOW_RESUMED      — 工作流从阻塞恢复
    EXPORT_READY          — 导出产物就绪
    WORKFLOW_FAILED       — 工作流失败

每个事件结构（Develop.md §17.3）：
    {
        "task_id": str,
        "batch_id": str,
        "tenant_id": str,
        "event_type": str,
        "stage": str,
        "status": str,
        "payload": dict,
        "occurred_at": str,  # ISO-8601 UTC
    }
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 事件类型常量
# ---------------------------------------------------------------------------

EVT_WORKFLOW_STARTED = "WORKFLOW_STARTED"
EVT_NODE_COMPLETED = "NODE_COMPLETED"
EVT_REVIEW_TASK_CREATED = "REVIEW_TASK_CREATED"
EVT_WORKFLOW_BLOCKED = "WORKFLOW_BLOCKED"
EVT_WORKFLOW_RESUMED = "WORKFLOW_RESUMED"
EVT_EXPORT_READY = "EXPORT_READY"
EVT_WORKFLOW_FAILED = "WORKFLOW_FAILED"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _build_event(
    *,
    task_id: str,
    batch_id: str,
    tenant_id: str,
    event_type: str,
    stage: str,
    status: str,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """构造符合 Develop.md §17.3 规范的事件 payload。"""
    return {
        "task_id": task_id,
        "batch_id": batch_id,
        "tenant_id": tenant_id,
        "event_type": event_type,
        "stage": stage,
        "status": status,
        "payload": payload or {},
        "occurred_at": _utc_now(),
    }


async def _send_event(event: dict[str, Any]) -> None:
    """向 Java 控制面 /internal/events/workflow 发送事件（fire-and-forget）。"""
    try:
        from config import (
            CONTROL_PLANE_BASE_URL,
            CONTROL_PLANE_INTERNAL_TOKEN,
            CONTROL_PLANE_VERIFY_TLS,
            CONTROL_PLANE_CALLBACK_TIMEOUT_SECONDS,
        )
    except ImportError:
        import os
        CONTROL_PLANE_BASE_URL = os.getenv("CONTROL_PLANE_BASE_URL", "")
        CONTROL_PLANE_INTERNAL_TOKEN = os.getenv("CONTROL_PLANE_INTERNAL_TOKEN", "")
        CONTROL_PLANE_VERIFY_TLS = True
        CONTROL_PLANE_CALLBACK_TIMEOUT_SECONDS = 10

    if not CONTROL_PLANE_BASE_URL:
        logger.debug("CONTROL_PLANE_BASE_URL not set, skip event %s", event.get("event_type"))
        return

    url = f"{CONTROL_PLANE_BASE_URL.rstrip('/')}/internal/events/workflow"
    headers = {"X-Internal-Token": CONTROL_PLANE_INTERNAL_TOKEN}

    try:
        async with httpx.AsyncClient(
            verify=CONTROL_PLANE_VERIFY_TLS,
            timeout=float(CONTROL_PLANE_CALLBACK_TIMEOUT_SECONDS),
        ) as client:
            resp = await client.post(url, json=event, headers=headers)
            if resp.status_code >= 400:
                logger.warning(
                    "Event send failed: event_type=%s status=%d body=%s",
                    event.get("event_type"),
                    resp.status_code,
                    resp.text[:200],
                )
            else:
                logger.debug(
                    "Event sent: event_type=%s batch_id=%s",
                    event.get("event_type"),
                    event.get("batch_id"),
                )
    except Exception:
        # 事件发送失败不中断主流程
        logger.exception(
            "Failed to send workflow event: event_type=%s batch_id=%s",
            event.get("event_type"),
            event.get("batch_id"),
        )


# ---------------------------------------------------------------------------
# 便捷发送函数
# ---------------------------------------------------------------------------

async def emit_workflow_started(
    *, task_id: str, batch_id: str, tenant_id: str, page_count: int = 0
) -> None:
    await _send_event(
        _build_event(
            task_id=task_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            event_type=EVT_WORKFLOW_STARTED,
            stage="ingest_batch",
            status="running",
            payload={"page_count": page_count},
        )
    )


async def emit_node_completed(
    *,
    task_id: str,
    batch_id: str,
    tenant_id: str,
    stage: str,
    extra: dict[str, Any] | None = None,
) -> None:
    await _send_event(
        _build_event(
            task_id=task_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            event_type=EVT_NODE_COMPLETED,
            stage=stage,
            status="done",
            payload=extra or {},
        )
    )


async def emit_review_task_created(
    *,
    task_id: str,
    batch_id: str,
    tenant_id: str,
    review_task_ids: list[str],
    task_count: int,
) -> None:
    await _send_event(
        _build_event(
            task_id=task_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            event_type=EVT_REVIEW_TASK_CREATED,
            stage="create_review_tasks",
            status="pending",
            payload={"review_task_ids": review_task_ids, "task_count": task_count},
        )
    )


async def emit_workflow_blocked(
    *,
    task_id: str,
    batch_id: str,
    tenant_id: str,
    stage: str,
    blocked_reasons: list[str],
) -> None:
    await _send_event(
        _build_event(
            task_id=task_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            event_type=EVT_WORKFLOW_BLOCKED,
            stage=stage,
            status="blocked",
            payload={"blocked_reasons": blocked_reasons},
        )
    )


async def emit_workflow_resumed(
    *,
    task_id: str,
    batch_id: str,
    tenant_id: str,
    reason: str,
) -> None:
    await _send_event(
        _build_event(
            task_id=task_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            event_type=EVT_WORKFLOW_RESUMED,
            stage="resume_from_review",
            status="running",
            payload={"reason": reason},
        )
    )


async def emit_export_ready(
    *,
    task_id: str,
    batch_id: str,
    tenant_id: str,
    artifact_type: str,
    storage_uri: str,
) -> None:
    await _send_event(
        _build_event(
            task_id=task_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            event_type=EVT_EXPORT_READY,
            stage="export_searchable_pdf_final",
            status="done",
            payload={"artifact_type": artifact_type, "storage_uri": storage_uri},
        )
    )


async def emit_workflow_failed(
    *,
    task_id: str,
    batch_id: str,
    tenant_id: str,
    stage: str,
    error_message: str,
) -> None:
    await _send_event(
        _build_event(
            task_id=task_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            event_type=EVT_WORKFLOW_FAILED,
            stage=stage,
            status="failed",
            payload={"error_message": error_message},
        )
    )
