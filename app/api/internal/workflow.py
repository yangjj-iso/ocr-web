"""
Internal Workflow API — 供 Java 控制面通过内部网络调用的工作流接口。

这些接口不对外暴露（不经过前端或公网），通过共享密钥校验调用方身份。
接口语义对应 Develop.md 第十七节的"Java 调 Python 的内部接口"。
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.db.models import BatchRecord, WorkflowRun, AuditLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/internal", tags=["internal"])


# ---------------------------------------------------------------------------
# 鉴权：内部调用使用共享密钥，不走 cookie/JWT
# ---------------------------------------------------------------------------

def _get_internal_token() -> str:
    return (os.getenv("CONTROL_PLANE_INTERNAL_TOKEN") or "").strip()


def verify_internal_token(x_internal_token: str = Header(default="")) -> None:
    expected = _get_internal_token()
    if expected and x_internal_token != expected:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid internal token")


# ---------------------------------------------------------------------------
# 请求/响应模型
# ---------------------------------------------------------------------------

class AffectedScope(BaseModel):
    page_ids: list[str] = Field(default_factory=list)
    doc_ids: list[str] = Field(default_factory=list)
    renumber_from_order_index: int | None = None
    regenerate_catalog: bool = False
    regenerate_pdf: bool = False


class WorkflowStartRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    batch_id: str
    tenant_id: str = "default"
    policy_snapshot_id: str | None = None
    source_file_uris: list[str] = Field(default_factory=list)
    page_count: int = 0
    submitted_by: str = ""
    extra: dict[str, Any] = Field(default_factory=dict)


class WorkflowResumeRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    task_id: str
    batch_id: str
    tenant_id: str = "default"
    reason: str = "review_resolved"
    resume_from_checkpoint: str | None = None
    affected_scope: AffectedScope = Field(default_factory=AffectedScope)


class WorkflowReworkRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    batch_id: str
    tenant_id: str = "default"
    rework_task_id: str
    rework_level: str = "partial"   # partial / full_rework
    affected_scope: AffectedScope = Field(default_factory=AffectedScope)
    resume_from_checkpoint: str | None = None


class ExportSearchablePdfRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    batch_id: str
    tenant_id: str = "default"
    export_type: str = "final"   # draft / final
    doc_ids: list[str] = Field(default_factory=list)   # 空表示全卷导出


class RecomputeAffectedScopeRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    batch_id: str
    tenant_id: str = "default"
    affected_scope: AffectedScope = Field(default_factory=AffectedScope)
    recompute_targets: list[str] = Field(
        default_factory=lambda: ["metadata", "catalog", "numbering"]
    )


class WorkflowResponse(BaseModel):
    success: bool
    run_id: str = ""
    batch_id: str = ""
    message: str = ""
    occurred_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


async def _find_latest_batch_run(db: AsyncSession, batch_id: str) -> WorkflowRun | None:
    result = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.batch_id == batch_id)
        .order_by(desc(WorkflowRun.created_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


def _normalize_affected_scope(scope: dict[str, Any] | None) -> dict[str, Any]:
    normalized = dict(scope or {})
    if normalized.get("regenerate_catalog"):
        normalized.setdefault("invalidate_catalog", True)
    if normalized.get("regenerate_pdf"):
        normalized.setdefault("invalidate_pdf", True)
    if normalized.get("renumber_from_order_index") is not None:
        normalized.setdefault("invalidate_numbering", True)
    return normalized


def _resolve_resume_checkpoint(scope: dict[str, Any], preferred: str | None = None) -> str | None:
    if preferred:
        return preferred
    normalized_scope = _normalize_affected_scope(scope)
    if not normalized_scope:
        return None
    from app.domains.rework.invalidation_service import earliest_invalidated_stage

    return earliest_invalidated_stage(normalized_scope)


# ---------------------------------------------------------------------------
# 路由实现
# ---------------------------------------------------------------------------

@router.post("/workflow/start", response_model=WorkflowResponse)
async def start_workflow(
    req: WorkflowStartRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
) -> WorkflowResponse:
    """
    Java 控制面调用：启动新的档案整理工作流。
    幂等：相同 request_id 重复调用直接返回已有 run_id。
    """
    # 幂等检查一：按 request_id 查询（Develop.md §17.4）
    # 避免 Java 重试时重复创建工作流
    if req.request_id:
        dup_result = await db.execute(
            select(WorkflowRun)
            .where(WorkflowRun.state_json["request_id"].astext == req.request_id)
            .limit(1)
        )
        dup_run = dup_result.scalar_one_or_none()
        if dup_run:
            return WorkflowResponse(
                success=True,
                run_id=dup_run.run_id,
                batch_id=req.batch_id,
                message="idempotent_request_id_already_processed",
            )

    # 幂等检查二：同一 batch_id 若已有运行中或完成的 run，则直接返回
    existing = await db.execute(
        select(WorkflowRun)
        .where(WorkflowRun.batch_id == req.batch_id)
        .where(WorkflowRun.run_status.in_(["running", "done"]))
        .limit(1)
    )
    existing_run = existing.scalar_one_or_none()
    if existing_run:
        return WorkflowResponse(
            success=True,
            run_id=existing_run.run_id,
            batch_id=req.batch_id,
            message="workflow_already_exists",
        )

    run_id = f"wf_{req.batch_id}_{uuid4().hex[:8]}"

    # 确保 BatchRecord 存在
    batch_result = await db.execute(
        select(BatchRecord).where(BatchRecord.batch_id == req.batch_id).limit(1)
    )
    batch_obj = batch_result.scalar_one_or_none()
    if not batch_obj:
        batch_obj = BatchRecord(
            batch_id=req.batch_id,
            tenant_id=req.tenant_id,
            page_count=req.page_count,
            policy_snapshot_id=req.policy_snapshot_id,
            status="processing",
            draft_status="running",
            final_status="pending",
        )
        db.add(batch_obj)
    else:
        batch_obj.status = "processing"
        batch_obj.draft_status = "running"

    wf_run = WorkflowRun(
        run_id=run_id,
        batch_id=req.batch_id,
        tenant_id=req.tenant_id,
        run_type="normal",
        run_status="running",
        current_stage="ingest_batch",
        policy_snapshot_id=req.policy_snapshot_id,
        state_json={
            "request_id": req.request_id,
            "source_file_uris": req.source_file_uris,
            "submitted_by": req.submitted_by,
            "extra": req.extra,
        },
    )
    db.add(wf_run)

    # AuditLog：记录工作流启动操作（Develop.md §19.3）
    audit = AuditLog(
        tenant_id=req.tenant_id,
        operator_user_id=req.submitted_by or "system",
        action="workflow_start",
        target_type="batch",
        target_id=req.batch_id,
        before_snapshot={},
        after_snapshot={
            "run_id": run_id,
            "request_id": req.request_id,
            "policy_snapshot_id": req.policy_snapshot_id,
        },
    )
    db.add(audit)
    await db.commit()

    # 异步派发工作流任务（通过队列）
    try:
        from app.infrastructure.queue.archive_publisher import enqueue_workflow_start
        extra_pages = req.extra.get("pages") if isinstance(req.extra.get("pages"), list) else []
        await enqueue_workflow_start(
            run_id=run_id,
            batch_id=req.batch_id,
            tenant_id=req.tenant_id,
            policy_snapshot_id=req.policy_snapshot_id,
            source_file_uris=req.source_file_uris,
            page_count=req.page_count,
            submitted_by=req.submitted_by,
            run_mode=str(req.extra.get("run_mode") or "normal"),
            request_id=req.request_id,
            pages=extra_pages,
            extra=req.extra,
        )
    except Exception:
        logger.exception("Failed to enqueue workflow start for run_id=%s", run_id)
        # 不回滚——run 记录已创建，可由补偿机制重试

    logger.info("Workflow started: run_id=%s batch_id=%s", run_id, req.batch_id)
    return WorkflowResponse(success=True, run_id=run_id, batch_id=req.batch_id, message="started")


@router.post("/workflow/resume", response_model=WorkflowResponse)
async def resume_workflow(
    req: WorkflowResumeRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
) -> WorkflowResponse:
    """
    Java 控制面调用：审核完成后恢复被阻塞的工作流，支持局部重跑。
    """
    from sqlalchemy import update

    # 幂等检查：同一 request_id 已处理过则直接返回（Develop.md §17.4）
    if req.request_id:
        dup_result = await db.execute(
            select(WorkflowRun)
            .where(WorkflowRun.state_json["request_id"].astext == req.request_id)
            .limit(1)
        )
        dup_run = dup_result.scalar_one_or_none()
        if dup_run:
            return WorkflowResponse(
                success=True,
                run_id=req.task_id,
                batch_id=req.batch_id,
                message="idempotent_request_id_already_processed",
            )

    run_result = await db.execute(
        select(WorkflowRun).where(WorkflowRun.run_id == req.task_id).limit(1)
    )
    wf_run = run_result.scalar_one_or_none()
    if not wf_run:
        raise HTTPException(status_code=404, detail=f"WorkflowRun not found: {req.task_id}")

    if wf_run.run_status not in ("blocked", "paused"):
        return WorkflowResponse(
            success=True,
            run_id=req.task_id,
            batch_id=req.batch_id,
            message=f"workflow_status_is_{wf_run.run_status}_no_resume_needed",
        )

    affected_scope = _normalize_affected_scope(req.affected_scope.model_dump())

    await db.execute(
        update(WorkflowRun)
        .where(WorkflowRun.run_id == req.task_id)
        .values(
            run_status="running",
            current_stage="resume_from_review",
            state_json={
                **wf_run.state_json,
                "request_id": req.request_id,
                "resume_reason": req.reason,
                "resume_from_checkpoint": req.resume_from_checkpoint,
                "affected_scope": affected_scope,
            },
        )
    )

    # AuditLog：记录工作流恢复操作（Develop.md §19.3）
    audit = AuditLog(
        tenant_id=req.tenant_id,
        operator_user_id="system",
        action="workflow_start",   # resume 记为 workflow_start（已创建的工作流重启）
        target_type="batch",
        target_id=req.batch_id,
        before_snapshot={"run_status": wf_run.run_status},
        after_snapshot={
            "run_status": "running",
            "resume_reason": req.reason,
            "request_id": req.request_id,
        },
    )
    db.add(audit)
    await db.commit()

    try:
        from app.infrastructure.queue.archive_publisher import enqueue_workflow_resume
        await enqueue_workflow_resume(
            run_id=req.task_id,
            batch_id=req.batch_id,
            reason=req.reason,
            affected_scope=affected_scope,
            resume_from_checkpoint=req.resume_from_checkpoint,
        )
    except Exception:
        logger.exception("Failed to enqueue workflow resume for run_id=%s", req.task_id)

    logger.info("Workflow resumed: run_id=%s batch_id=%s reason=%s", req.task_id, req.batch_id, req.reason)
    return WorkflowResponse(success=True, run_id=req.task_id, batch_id=req.batch_id, message="resumed")


@router.post("/workflow/rework", response_model=WorkflowResponse)
async def rework_workflow(
    req: WorkflowReworkRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
) -> WorkflowResponse:
    """
    Java 控制面调用：租户管理员受理返工申请后，触发局部或全卷返工。
    """
    batch_result = await db.execute(
        select(BatchRecord).where(BatchRecord.batch_id == req.batch_id).limit(1)
    )
    batch_obj = batch_result.scalar_one_or_none()
    if not batch_obj:
        raise HTTPException(status_code=404, detail=f"BatchRecord not found: {req.batch_id}")

    source_run = await _find_latest_batch_run(db, req.batch_id)
    if not source_run:
        raise HTTPException(status_code=404, detail=f"WorkflowRun not found for batch: {req.batch_id}")

    affected_scope = _normalize_affected_scope(req.affected_scope.model_dump())
    resume_from_checkpoint = _resolve_resume_checkpoint(affected_scope, req.resume_from_checkpoint)
    previous_final_status = batch_obj.final_status

    # 更新批次状态
    batch_obj.status = "processing"
    batch_obj.final_status = "pending"
    batch_obj.draft_status = "running"
    batch_obj.current_version = batch_obj.current_version + 1

    # AuditLog：记录返工操作（Develop.md §19.3 — rework_request）
    audit = AuditLog(
        tenant_id=req.tenant_id,
        operator_user_id="system",
        action="rework_request",
        target_type="batch",
        target_id=req.batch_id,
        before_snapshot={"final_status": previous_final_status},
        after_snapshot={
            "run_id": source_run.run_id,
            "source_run_id": source_run.run_id,
            "rework_level": req.rework_level,
            "rework_task_id": req.rework_task_id,
            "request_id": req.request_id,
            "resume_from_checkpoint": resume_from_checkpoint,
        },
    )
    db.add(audit)
    await db.commit()

    try:
        from app.infrastructure.queue.archive_publisher import enqueue_workflow_rework
        await enqueue_workflow_rework(
            run_id=source_run.run_id,
            batch_id=req.batch_id,
            tenant_id=req.tenant_id,
            source_run_id=source_run.run_id,
            reason="rework_requested",
            rework_level=req.rework_level,
            affected_scope=affected_scope,
            resume_from_checkpoint=resume_from_checkpoint,
        )
    except Exception:
        logger.exception("Failed to enqueue workflow rework for run_id=%s", source_run.run_id)

    logger.info(
        "Workflow rework: source_run_id=%s batch_id=%s level=%s checkpoint=%s",
        source_run.run_id,
        req.batch_id,
        req.rework_level,
        resume_from_checkpoint,
    )
    return WorkflowResponse(success=True, run_id=source_run.run_id, batch_id=req.batch_id, message="rework_started")


@router.post("/export/searchable-pdf", response_model=WorkflowResponse)
async def export_searchable_pdf(
    req: ExportSearchablePdfRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
) -> WorkflowResponse:
    """
    Java 控制面调用：触发 searchable PDF 导出任务。
    导出任务独立队列，不阻塞主工作流。
    """
    from sqlalchemy import select

    batch_result = await db.execute(
        select(BatchRecord).where(BatchRecord.batch_id == req.batch_id).limit(1)
    )
    batch_obj = batch_result.scalar_one_or_none()
    if not batch_obj:
        raise HTTPException(status_code=404, detail=f"BatchRecord not found: {req.batch_id}")

    if req.export_type == "final" and batch_obj.final_status != "done":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot export final PDF: final_status is not done",
        )

    run_id = f"export_{req.batch_id}_{uuid4().hex[:8]}"

    batch_obj.export_status = "generating"
    await db.commit()

    try:
        from app.infrastructure.queue.archive_publisher import enqueue_export_pdf
        await enqueue_export_pdf(
            run_id=run_id,
            batch_id=req.batch_id,
            tenant_id=req.tenant_id,
            export_type=req.export_type,
            doc_ids=req.doc_ids,
        )
    except Exception:
        logger.exception("Failed to enqueue export pdf for batch_id=%s", req.batch_id)

    return WorkflowResponse(success=True, run_id=run_id, batch_id=req.batch_id, message="export_enqueued")


@router.post("/recompute/affected-scope", response_model=WorkflowResponse)
async def recompute_affected_scope(
    req: RecomputeAffectedScopeRequest,
    db: AsyncSession = Depends(get_db),
    _: None = Depends(verify_internal_token),
) -> WorkflowResponse:
    """
    Java 控制面调用：人工改动后，重新计算受影响范围并触发局部重算。
    例如：改了字段 → 重算目录和索引，但不重跑 OCR 和分件。
    """
    source_run = await _find_latest_batch_run(db, req.batch_id)
    if not source_run:
        raise HTTPException(status_code=404, detail=f"WorkflowRun not found for batch: {req.batch_id}")

    affected_scope = _normalize_affected_scope(req.affected_scope.model_dump())
    resume_from_checkpoint = _resolve_resume_checkpoint(affected_scope)

    try:
        from app.infrastructure.queue.archive_publisher import enqueue_workflow_resume
        await enqueue_workflow_resume(
            run_id=source_run.run_id,
            batch_id=req.batch_id,
            reason="recompute_affected_scope",
            affected_scope={
                **affected_scope,
                "recompute_targets": req.recompute_targets,
            },
            resume_from_checkpoint=resume_from_checkpoint,
        )
    except Exception:
        logger.exception("Failed to enqueue recompute for batch_id=%s", req.batch_id)

    return WorkflowResponse(success=True, run_id=source_run.run_id, batch_id=req.batch_id, message="recompute_enqueued")
