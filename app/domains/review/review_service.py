"""
Review Domain — 人工审核任务管理服务。

负责：
- 创建审核任务（分件/著录/放行）
- 任务认领与提交
- 审核结果回写，触发工作流恢复
- 审核动作日志

遵循 Develop.md 阶段 7 和第十三节。
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ReviewActionLog, ReviewTask, WorkflowRun

logger = logging.getLogger(__name__)


async def create_review_tasks(
    db: AsyncSession,
    *,
    batch_id: str,
    tenant_id: str,
    run_id: str,
    task_specs: list[dict[str, Any]],
) -> list[str]:
    """
    批量创建审核任务。

    task_specs 每项格式：
    {
        "task_type": "boundary" | "ordering" | "metadata" | "final_release",
        "affected_page_ids": [...],
        "affected_doc_ids": [...],
        "reason": "...",
        "evidence": {...},
        "confidence": 0.45,
    }
    返回创建的 review_task_id 列表。
    """
    created_ids: list[str] = []
    for spec in task_specs:
        review_task_id = f"rt_{batch_id}_{uuid4().hex[:8]}"
        task = ReviewTask(
            review_task_id=review_task_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            run_id=run_id,
            task_type=spec.get("task_type", "boundary"),
            affected_page_ids_json=spec.get("affected_page_ids", []),
            affected_doc_ids_json=spec.get("affected_doc_ids", []),
            reason=spec.get("reason", ""),
            evidence_json=spec.get("evidence", {}),
            confidence=spec.get("confidence", 0.0),
            status="pending",
        )
        db.add(task)
        created_ids.append(review_task_id)

    await db.commit()
    logger.info(
        "Created %d review tasks for batch_id=%s run_id=%s",
        len(created_ids),
        batch_id,
        run_id,
    )
    return created_ids


async def claim_review_task(
    db: AsyncSession,
    *,
    review_task_id: str,
    user_id: int,
) -> bool:
    """认领审核任务（将 status 改为 claimed，设置 assignee）。"""
    result = await db.execute(
        select(ReviewTask).where(ReviewTask.review_task_id == review_task_id).limit(1)
    )
    task = result.scalar_one_or_none()
    if not task or task.status != "pending":
        return False

    before_snapshot = {"status": task.status, "assignee_user_id": task.assignee_user_id}
    task.status = "claimed"
    task.assignee_user_id = user_id

    log = ReviewActionLog(
        review_task_id=review_task_id,
        batch_id=task.batch_id,
        operator_user_id=user_id,
        action="claim",
        before_snapshot_json=before_snapshot,
        after_snapshot_json={"status": "claimed", "assignee_user_id": user_id},
    )
    db.add(log)
    await db.commit()
    return True


async def submit_review_result(
    db: AsyncSession,
    *,
    review_task_id: str,
    user_id: int,
    result: dict[str, Any],
    note: str = "",
) -> bool:
    """
    提交审核结果。
    成功后标记任务为 submitted，并尝试检查同批次是否所有阻塞任务已解决。
    如果全部解决，恢复工作流的 blocked → running 状态。
    """
    task_result = await db.execute(
        select(ReviewTask).where(ReviewTask.review_task_id == review_task_id).limit(1)
    )
    task = task_result.scalar_one_or_none()
    if not task or task.status not in ("claimed", "pending"):
        return False

    before_snapshot = {"status": task.status, "result_json": task.result_json}
    task.status = "submitted"
    task.result_json = result

    log = ReviewActionLog(
        review_task_id=review_task_id,
        batch_id=task.batch_id,
        operator_user_id=user_id,
        action="submit",
        before_snapshot_json=before_snapshot,
        after_snapshot_json={"status": "submitted", "result_json": result},
        note=note,
    )
    db.add(log)
    await db.commit()

    # 检查批次是否所有审核任务均已解决
    await _try_resolve_batch_review(db, batch_id=task.batch_id, run_id=task.run_id or "")
    return True


async def _try_resolve_batch_review(
    db: AsyncSession,
    *,
    batch_id: str,
    run_id: str,
) -> None:
    """若批次所有审核任务已完成，则将工作流 run 标记为可恢复。"""
    pending_result = await db.execute(
        select(ReviewTask)
        .where(ReviewTask.batch_id == batch_id)
        .where(ReviewTask.status.in_(["pending", "claimed"]))
        .limit(1)
    )
    still_pending = pending_result.scalar_one_or_none()
    if still_pending:
        return  # 还有未完成的任务，不恢复

    # 所有任务完成：将 run 状态从 blocked 改为 running（等待队列消费者继续处理）
    if run_id:
        await db.execute(
            update(WorkflowRun)
            .where(WorkflowRun.run_id == run_id)
            .where(WorkflowRun.run_status == "blocked")
            .values(
                run_status="running",
                current_stage="resume_from_review",
                blocked_reasons_json=[],
            )
        )
        await db.commit()
        logger.info(
            "All review tasks resolved for batch_id=%s run_id=%s — workflow unblocked",
            batch_id,
            run_id,
        )


async def get_pending_review_tasks(
    db: AsyncSession,
    *,
    batch_id: str | None = None,
    task_type: str | None = None,
    assignee_user_id: int | None = None,
) -> list[dict[str, Any]]:
    """查询待处理的审核任务列表。"""
    stmt = select(ReviewTask).where(ReviewTask.status.in_(["pending", "claimed"]))
    if batch_id:
        stmt = stmt.where(ReviewTask.batch_id == batch_id)
    if task_type:
        stmt = stmt.where(ReviewTask.task_type == task_type)
    if assignee_user_id:
        stmt = stmt.where(ReviewTask.assignee_user_id == assignee_user_id)
    stmt = stmt.order_by(ReviewTask.created_at)

    result = await db.execute(stmt)
    tasks = result.scalars().all()
    return [
        {
            "review_task_id": t.review_task_id,
            "batch_id": t.batch_id,
            "task_type": t.task_type,
            "affected_page_ids": t.affected_page_ids_json,
            "affected_doc_ids": t.affected_doc_ids_json,
            "reason": t.reason,
            "confidence": t.confidence,
            "status": t.status,
            "assignee_user_id": t.assignee_user_id,
            "created_at": t.created_at.isoformat() if t.created_at else None,
        }
        for t in tasks
    ]
