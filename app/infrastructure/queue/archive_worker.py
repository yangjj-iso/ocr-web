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
    - relation_analysis_queue → 页间关系分析 + 分件风险评估
    - draft_pipeline_queue    → Draft 子图消费与审核门控
    - final_pipeline_queue    → Final 子图消费与最终落库

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

_DRAFT_PIPELINE_STAGES = {"run_draft_subgraph", "create_review_tasks", "gate_final_subgraph", "wait_for_review"}
_FINAL_PIPELINE_STAGES = {
    "sort_documents_final",
    "assign_archive_numbers",
    "extract_metadata_final",
    "build_catalog_final",
    "export_searchable_pdf_final",
    "persist_record_and_index",
    "done",
}
_PORTABLE_WORKFLOW_STATE_KEYS = {
    "task_id",
    "batch_id",
    "tenant_id",
    "policy_snapshot_id",
    "run_mode",
    "current_stage",
    "draft_status",
    "final_status",
    "review_status",
    "pages",
    "draft_docs",
    "final_docs",
    "review_tasks",
    "blocked_reasons",
    "affected_scope",
    "resume_from_checkpoint",
    "resume_reason",
    "checkpoints",
    "artifacts",
    "metrics",
    "policy_rules",
    "review_result",
}


def _workflow_config(run_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": run_id}}


def _default_workflow_state(
    *,
    run_id: str,
    batch_id: str,
    tenant_id: str,
    current_stage: str,
) -> dict[str, Any]:
    return {
        "task_id": run_id,
        "batch_id": batch_id,
        "tenant_id": tenant_id,
        "current_stage": current_stage,
        "draft_status": "pending",
        "final_status": "pending",
        "review_status": "none",
        "pages": [],
        "draft_docs": [],
        "final_docs": [],
        "review_tasks": [],
        "blocked_reasons": [],
        "affected_scope": {},
        "resume_from_checkpoint": None,
        "resume_reason": "",
        "checkpoints": {},
        "artifacts": {},
        "metrics": {},
        "policy_rules": {},
        "review_result": None,
    }


def _portable_workflow_state(state: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in state.items() if key in _PORTABLE_WORKFLOW_STATE_KEYS}


async def _load_state_from_workflow_run(
    *,
    run_id: str,
    batch_id: str,
    tenant_id: str,
    current_stage: str,
) -> dict[str, Any]:
    from sqlalchemy import select

    from app.db.database import async_session as AsyncSessionLocal
    from app.db.models import WorkflowRun

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(WorkflowRun).where(WorkflowRun.run_id == run_id).limit(1))
        wf_run = result.scalar_one_or_none()

    if not wf_run:
        return {}

    state = _default_workflow_state(
        run_id=run_id,
        batch_id=batch_id,
        tenant_id=tenant_id,
        current_stage=wf_run.current_stage or current_stage,
    )
    state.update(dict(wf_run.state_json or {}))
    state.setdefault("batch_id", batch_id)
    state.setdefault("tenant_id", tenant_id)
    state.setdefault("task_id", run_id)
    if wf_run.blocked_reasons_json and not state.get("blocked_reasons"):
        state["blocked_reasons"] = list(wf_run.blocked_reasons_json or [])
    return state


async def _build_state_from_page_records(
    *,
    run_id: str,
    batch_id: str,
    tenant_id: str,
    current_stage: str,
) -> dict[str, Any]:
    from app.domains.page_processing.page_service import _load_batch_pages, build_page_schema

    page_rows = await _load_batch_pages(batch_id)
    if not page_rows:
        return {}

    pages = [
        build_page_schema(
            page_id=page.page_id,
            batch_id=page.batch_id,
            page_index=page.page_index,
            image_uri=page.preview_uri or page.image_uri or "",
            ocr_text=page.ocr_text or "",
            ocr_blocks=page.ocr_blocks_json or {},
            layout_type=page.layout_type,
            phash=page.phash,
            first_page_score=float(page.first_page_score or 0.0),
            duplicate_score=float(page.duplicate_score or 0.0),
            candidates=page.candidates_json or {},
        )
        for page in page_rows
    ]
    state = _default_workflow_state(
        run_id=run_id,
        batch_id=batch_id,
        tenant_id=tenant_id,
        current_stage=current_stage,
    )
    state["pages"] = pages
    return state


async def _load_workflow_state(
    *,
    run_id: str,
    batch_id: str,
    tenant_id: str = "default",
    current_stage: str = "ingest_batch",
) -> tuple[dict[str, Any], dict[str, Any]]:
    from app.services.archive_workflow import archive_main_graph

    config = _workflow_config(run_id)
    state: dict[str, Any] = {}
    aget_state = getattr(archive_main_graph, "aget_state", None)

    if callable(aget_state):
        try:
            snapshot = await aget_state(config)
            values = getattr(snapshot, "values", None) or {}
            if isinstance(values, dict) and values:
                state = _default_workflow_state(
                    run_id=run_id,
                    batch_id=batch_id,
                    tenant_id=tenant_id,
                    current_stage=current_stage,
                )
                state.update(values)
        except Exception:
            logger.debug("[archive_worker] checkpoint state unavailable for run_id=%s", run_id, exc_info=True)

    if not state:
        state = await _load_state_from_workflow_run(
            run_id=run_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            current_stage=current_stage,
        )

    if not state:
        state = await _build_state_from_page_records(
            run_id=run_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            current_stage=current_stage,
        )

    if not state:
        raise RuntimeError(f"Workflow state not found for run_id={run_id} batch_id={batch_id}")

    state.setdefault("task_id", run_id)
    state.setdefault("batch_id", batch_id)
    state.setdefault("tenant_id", tenant_id)
    state.setdefault("current_stage", current_stage)
    return config, state


async def _upsert_page_records(*, batch_id: str, pages: list[dict[str, Any]]) -> list[str]:
    from sqlalchemy import select

    from app.db.database import async_session as AsyncSessionLocal
    from app.db.models import PageRecord

    normalized_pages: list[dict[str, Any]] = []
    for index, raw_page in enumerate(pages):
        page = dict(raw_page or {})
        page_id = str(page.get("page_id") or f"{batch_id}-page-{index + 1}").strip()
        if not page_id:
            continue
        page_index = int(page.get("page_index") if page.get("page_index") is not None else index)
        normalized_pages.append(
            {
                "page_id": page_id,
                "page_index": page_index,
                "image_uri": str(page.get("image_uri") or "").strip() or None,
                "preview_uri": str(page.get("preview_uri") or "").strip() or None,
                "ocr_text": str(page.get("ocr_text") or "").strip() or None,
                "ocr_blocks_json": page.get("ocr_blocks") if isinstance(page.get("ocr_blocks"), dict) else (
                    page.get("ocr_blocks_json") if isinstance(page.get("ocr_blocks_json"), dict) else None
                ),
                "layout_type": str(page.get("layout_type") or "").strip() or None,
                "phash": str(page.get("phash") or "").strip() or None,
                "first_page_score": float(page.get("first_page_score") or 0.0),
                "duplicate_score": float(page.get("duplicate_score") or 0.0),
                "candidates_json": page.get("candidates") if isinstance(page.get("candidates"), dict) else (
                    page.get("candidates_json") if isinstance(page.get("candidates_json"), dict) else None
                ),
            }
        )

    if not normalized_pages:
        return []

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(PageRecord).where(PageRecord.batch_id == batch_id))
        existing_rows = {row.page_id: row for row in result.scalars().all()}

        for page in normalized_pages:
            row = existing_rows.get(page["page_id"])
            if row is None:
                row = PageRecord(
                    page_id=page["page_id"],
                    batch_id=batch_id,
                    page_index=page["page_index"],
                    image_uri=page["image_uri"],
                    preview_uri=page["preview_uri"],
                    ocr_text=page["ocr_text"],
                    ocr_blocks_json=page["ocr_blocks_json"],
                    layout_type=page["layout_type"],
                    phash=page["phash"],
                    first_page_score=page["first_page_score"],
                    duplicate_score=page["duplicate_score"],
                    candidates_json=page["candidates_json"],
                )
                db.add(row)
                existing_rows[page["page_id"]] = row
            else:
                row.page_index = page["page_index"]
                row.image_uri = page["image_uri"] or row.image_uri
                row.preview_uri = page["preview_uri"] or row.preview_uri
                row.ocr_text = page["ocr_text"] or row.ocr_text
                row.ocr_blocks_json = page["ocr_blocks_json"] or row.ocr_blocks_json
                row.layout_type = page["layout_type"] or row.layout_type
                row.phash = page["phash"] or row.phash
                row.first_page_score = page["first_page_score"] if page["first_page_score"] else row.first_page_score
                row.duplicate_score = page["duplicate_score"] if page["duplicate_score"] else row.duplicate_score
                row.candidates_json = page["candidates_json"] or row.candidates_json

        await db.commit()

    return [page["page_id"] for page in sorted(normalized_pages, key=lambda item: item["page_index"])]


async def _set_workflow_state_flag_if_absent(*, run_id: str, flag: str) -> bool:
    from sqlalchemy import select

    from app.db.database import async_session as AsyncSessionLocal
    from app.db.models import WorkflowRun

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WorkflowRun).where(WorkflowRun.run_id == run_id).with_for_update()
        )
        wf_run = result.scalar_one_or_none()
        if not wf_run:
            return False

        state_json = dict(wf_run.state_json or {})
        if state_json.get(flag):
            return False
        state_json[flag] = True
        wf_run.state_json = state_json
        await db.commit()
        return True


async def _mutate_workflow_state_json(run_id: str, mutator: Any) -> dict[str, Any] | None:
    from sqlalchemy import select

    from app.db.database import async_session as AsyncSessionLocal
    from app.db.models import WorkflowRun

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(WorkflowRun).where(WorkflowRun.run_id == run_id).with_for_update()
        )
        wf_run = result.scalar_one_or_none()
        if not wf_run:
            return None

        state_json = dict(wf_run.state_json or {})
        mutator(state_json)
        wf_run.state_json = state_json
        await db.commit()
        return state_json


async def _initialize_queue_progress(*, run_id: str, total_pages: int) -> None:
    def mutate(state_json: dict[str, Any]) -> None:
        state_json["queue_progress"] = {
            "page_preprocess": {"total": total_pages, "completed": 0, "status": "processing" if total_pages else "pending"},
            "ocr": {"total": total_pages, "completed": 0, "status": "pending"},
            "page_features": {"total": total_pages, "completed": 0, "status": "pending"},
            "relation_analysis": {"total": 1, "completed": 0, "status": "pending"},
        }

    await _mutate_workflow_state_json(run_id, mutate)


async def _advance_queue_progress(
    *,
    run_id: str,
    stage: str,
    completed_delta: int = 0,
    status: str | None = None,
    total: int | None = None,
) -> dict[str, Any] | None:
    def mutate(state_json: dict[str, Any]) -> None:
        queue_progress = dict(state_json.get("queue_progress") or {})
        progress = dict(queue_progress.get(stage) or {})
        current_total = int(progress.get("total") or 0)
        if total is not None:
            current_total = max(0, int(total))
        current_completed = int(progress.get("completed") or 0) + max(0, int(completed_delta or 0))
        if current_total:
            current_completed = min(current_completed, current_total)
        progress["total"] = current_total
        progress["completed"] = current_completed
        if status is not None:
            progress["status"] = status
        elif current_total and current_completed >= current_total:
            progress["status"] = "done"
        elif current_completed > 0:
            progress["status"] = "processing"
        else:
            progress["status"] = progress.get("status") or "pending"
        queue_progress[stage] = progress
        state_json["queue_progress"] = queue_progress

    return await _mutate_workflow_state_json(run_id, mutate)


async def _maybe_enqueue_relation_analysis(*, run_id: str, batch_id: str, tenant_id: str) -> bool:
    from app.domains.page_processing.page_service import _load_batch_pages
    from app.infrastructure.queue.archive_publisher import enqueue_relation_analysis

    page_rows = await _load_batch_pages(batch_id)
    if not page_rows:
        return False

    all_ready = all(page.candidates_json is not None for page in page_rows)
    if not all_ready:
        return False

    should_publish = await _set_workflow_state_flag_if_absent(
        run_id=run_id,
        flag="relation_analysis_enqueued",
    )
    if not should_publish:
        return False

    await _advance_queue_progress(
        run_id=run_id,
        stage="relation_analysis",
        status="processing",
        total=1,
    )
    await enqueue_relation_analysis(run_id=run_id, batch_id=batch_id)
    logger.info("[archive_worker] relation_analysis queued: run_id=%s batch_id=%s", run_id, batch_id)
    return True


async def _save_checkpoint_state(config: dict[str, Any], state: dict[str, Any]) -> None:
    from app.services.archive_workflow import archive_main_graph

    aupdate_state = getattr(archive_main_graph, "aupdate_state", None)
    if not callable(aupdate_state):
        return
    try:
        await aupdate_state(config, state)
    except Exception:
        logger.debug("[archive_worker] failed to persist checkpoint state", exc_info=True)


async def _persist_workflow_progress(
    *,
    run_id: str,
    current_stage: str,
    run_status: str,
    state: dict[str, Any],
    blocked_reasons: list[str] | None = None,
) -> None:
    from sqlalchemy import select

    from app.db.database import async_session as AsyncSessionLocal
    from app.db.models import WorkflowRun

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(WorkflowRun).where(WorkflowRun.run_id == run_id).limit(1))
        wf_run = result.scalar_one_or_none()
        if not wf_run:
            return

        wf_run.current_stage = current_stage
        wf_run.run_status = run_status
        wf_run.blocked_reasons_json = list(blocked_reasons or state.get("blocked_reasons") or [])
        wf_run.state_json = {
            **dict(wf_run.state_json or {}),
            **_portable_workflow_state(state),
        }
        await db.commit()


async def _mark_workflow_blocked(
    *,
    run_id: str,
    batch_id: str,
    tenant_id: str,
    state: dict[str, Any],
) -> None:
    blocked_reasons = list(state.get("blocked_reasons") or [])
    await _persist_workflow_progress(
        run_id=run_id,
        current_stage="wait_for_review",
        run_status="blocked",
        state=state,
        blocked_reasons=blocked_reasons,
    )

    try:
        from app.infrastructure.callback.workflow_events import emit_workflow_blocked

        await emit_workflow_blocked(
            task_id=run_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            stage="wait_for_review",
            blocked_reasons=blocked_reasons,
        )
    except Exception:
        logger.exception("[archive_worker] failed to emit WORKFLOW_BLOCKED for run_id=%s", run_id)

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
    source_file_uris: list[str] = message_body.get("source_file_uris", [])
    page_count_hint = int(message_body.get("page_count") or 0)

    logger.info(
        "[archive_worker] ingest: task_id=%s batch_id=%s pages=%d source_files=%d page_count_hint=%d",
        task_id,
        batch_id,
        len(pages),
        len(source_file_uris),
        page_count_hint,
    )

    try:
        if pages:
            from app.infrastructure.queue.archive_publisher import fanout_page_preprocess

            page_ids = await _upsert_page_records(batch_id=batch_id, pages=pages)
            initial_state = _default_workflow_state(
                run_id=task_id,
                batch_id=batch_id,
                tenant_id=tenant_id,
                current_stage="preprocess_pages",
            )
            initial_state.update(
                {
                    "policy_snapshot_id": policy_snapshot_id,
                    "run_mode": run_mode,
                    "pages": [dict(page) for page in pages],
                }
            )
            await _persist_workflow_progress(
                run_id=task_id,
                current_stage="preprocess_pages",
                run_status="running",
                state=initial_state,
            )
            await _initialize_queue_progress(run_id=task_id, total_pages=len(page_ids))
            await fanout_page_preprocess(run_id=task_id, batch_id=batch_id, page_ids=page_ids)
            logger.info(
                "[archive_worker] ingest fan-out started: batch_id=%s page_count=%d",
                batch_id,
                len(page_ids),
            )
            return

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

    task_id: str = message_body.get("source_run_id") or message_body["run_id"]
    batch_id: str = message_body["batch_id"]
    rework_scope: dict[str, Any] = message_body.get("affected_scope") or message_body.get("rework_scope", {})
    reason: str = message_body.get("reason", "rework_requested")
    resume_from_checkpoint: str | None = message_body.get("resume_from_checkpoint")

    logger.info(
        "[archive_worker] rework: task_id=%s scope_keys=%s checkpoint=%s",
        task_id,
        sorted(rework_scope.keys()),
        resume_from_checkpoint,
    )

    try:
        final_state = await resume_archive_workflow(
            task_id=task_id,
            batch_id=batch_id,
            reason=reason,
            affected_scope=rework_scope,
            resume_from_checkpoint=resume_from_checkpoint,
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
        from app.infrastructure.queue.archive_publisher import enqueue_ocr_pages

        await preprocess_pages(batch_id=batch_id, page_ids=page_ids)
        await _advance_queue_progress(
            run_id=str(message_body.get("source_run_id") or message_body.get("run_id") or batch_id),
            stage="page_preprocess",
            completed_delta=len(page_ids),
        )
        await _advance_queue_progress(
            run_id=str(message_body.get("source_run_id") or message_body.get("run_id") or batch_id),
            stage="ocr",
            status="processing",
        )
        if page_ids:
            await enqueue_ocr_pages(
                run_id=str(message_body.get("source_run_id") or message_body.get("run_id") or batch_id),
                batch_id=batch_id,
                page_ids=page_ids,
            )
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
        from app.infrastructure.queue.archive_publisher import enqueue_page_features

        await run_ocr_pages(batch_id=batch_id, page_ids=page_ids)
        await _advance_queue_progress(
            run_id=str(message_body.get("source_run_id") or message_body.get("run_id") or batch_id),
            stage="ocr",
            completed_delta=len(page_ids),
        )
        await _advance_queue_progress(
            run_id=str(message_body.get("source_run_id") or message_body.get("run_id") or batch_id),
            stage="page_features",
            status="processing",
        )
        if page_ids:
            await enqueue_page_features(
                run_id=str(message_body.get("source_run_id") or message_body.get("run_id") or batch_id),
                batch_id=batch_id,
                page_ids=page_ids,
            )
        logger.info("[archive_worker] run_ocr done: batch_id=%s", batch_id)
    except ImportError:
        logger.warning("[archive_worker] page_service.run_ocr_pages not implemented, skipping")
    except Exception:
        logger.exception("[archive_worker] run_ocr failed: batch_id=%s", batch_id)
        raise


async def _handle_page_features(message_body: dict[str, Any]) -> None:
    """处理 page_feature_queue 消息 — 页面特征提取（候选字段、pHash 等）。"""
    batch_id: str = message_body["batch_id"]
    run_id: str = str(message_body.get("source_run_id") or message_body.get("run_id") or batch_id)
    tenant_id: str = message_body.get("tenant_id", "default")
    page_ids: list[str] = message_body.get("page_ids", [])

    logger.info("[archive_worker] page_features: batch_id=%s pages=%d", batch_id, len(page_ids))

    try:
        from app.domains.page_processing.page_service import extract_page_features
        await extract_page_features(batch_id=batch_id, page_ids=page_ids)
        await _advance_queue_progress(
            run_id=run_id,
            stage="page_features",
            completed_delta=len(page_ids),
        )
        await _maybe_enqueue_relation_analysis(run_id=run_id, batch_id=batch_id, tenant_id=tenant_id)
        logger.info("[archive_worker] page_features done: batch_id=%s", batch_id)
    except ImportError:
        logger.warning("[archive_worker] page_service.extract_page_features not implemented, skipping")
    except Exception:
        logger.exception("[archive_worker] page_features failed: batch_id=%s", batch_id)
        raise


async def _handle_relation_analysis(message_body: dict[str, Any]) -> None:
    """处理 relation_analysis_queue 消息 — 关系分析 + 分件 + 分件风险评估。"""
    from app.infrastructure.queue.archive_publisher import enqueue_draft_pipeline
    from app.services.archive_workflow import (
        node_analyze_page_relations,
        node_assess_split_risk,
        node_split_documents,
    )

    run_id: str = message_body.get("source_run_id") or message_body["run_id"]
    batch_id: str = message_body["batch_id"]
    tenant_id: str = message_body.get("tenant_id", "default")

    logger.info("[archive_worker] relation_analysis: run_id=%s batch_id=%s", run_id, batch_id)

    config, state = await _load_workflow_state(
        run_id=run_id,
        batch_id=batch_id,
        tenant_id=tenant_id,
        current_stage="analyze_page_relations",
    )
    state["current_stage"] = "analyze_page_relations"

    for step in (node_analyze_page_relations, node_split_documents, node_assess_split_risk):
        delta = await step(state)
        state.update(delta)

    await _advance_queue_progress(run_id=run_id, stage="relation_analysis", completed_delta=1)
    await _save_checkpoint_state(config, state)
    await _persist_workflow_progress(
        run_id=run_id,
        current_stage=str(state.get("current_stage") or "run_draft_subgraph"),
        run_status="running",
        state=state,
    )
    await enqueue_draft_pipeline(
        run_id=run_id,
        source_run_id=run_id,
        batch_id=batch_id,
        tenant_id=tenant_id,
        current_stage=str(state.get("current_stage") or "run_draft_subgraph"),
    )


async def _handle_draft_pipeline(message_body: dict[str, Any]) -> None:
    """处理 draft_pipeline_queue 消息 — 运行 Draft 子图并在需要时衔接 Final 队列。"""
    from app.infrastructure.queue.archive_publisher import enqueue_final_pipeline
    from app.services.archive_workflow import archive_draft_subgraph

    run_id: str = message_body.get("source_run_id") or message_body["run_id"]
    batch_id: str = message_body["batch_id"]
    tenant_id: str = message_body.get("tenant_id", "default")
    current_stage: str = (
        message_body.get("resume_from_checkpoint")
        or message_body.get("current_stage")
        or "run_draft_subgraph"
    )

    if current_stage in _FINAL_PIPELINE_STAGES:
        await _handle_final_pipeline({**message_body, "run_id": run_id, "source_run_id": run_id})
        return

    logger.info("[archive_worker] draft_pipeline: run_id=%s stage=%s", run_id, current_stage)

    config, state = await _load_workflow_state(
        run_id=run_id,
        batch_id=batch_id,
        tenant_id=tenant_id,
        current_stage=current_stage,
    )
    state["current_stage"] = current_stage
    state["affected_scope"] = dict(message_body.get("affected_scope") or state.get("affected_scope") or {})
    state["resume_from_checkpoint"] = message_body.get("resume_from_checkpoint") or state.get("resume_from_checkpoint")
    recompute_targets = list(message_body.get("recompute_targets") or [])
    if recompute_targets:
        state["affected_scope"] = {
            **dict(state.get("affected_scope") or {}),
            "recompute_targets": recompute_targets,
        }

    result = await archive_draft_subgraph.ainvoke(state)
    state.update(result or {})

    await _save_checkpoint_state(config, state)

    next_stage = str(state.get("current_stage") or current_stage)
    if next_stage == "wait_for_review":
        await _mark_workflow_blocked(
            run_id=run_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            state=state,
        )
        return

    await _persist_workflow_progress(
        run_id=run_id,
        current_stage=next_stage,
        run_status="running",
        state=state,
    )

    if next_stage in _FINAL_PIPELINE_STAGES:
        await enqueue_final_pipeline(
            run_id=run_id,
            source_run_id=run_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            current_stage=next_stage,
            affected_scope=dict(state.get("affected_scope") or {}),
            resume_from_checkpoint=state.get("resume_from_checkpoint"),
        )


async def _handle_final_pipeline(message_body: dict[str, Any]) -> None:
    """处理 final_pipeline_queue 消息 — 运行 Final 子图并落正式结果。"""
    from app.services.archive_workflow import archive_final_subgraph

    run_id: str = message_body.get("source_run_id") or message_body["run_id"]
    batch_id: str = message_body["batch_id"]
    tenant_id: str = message_body.get("tenant_id", "default")
    current_stage: str = (
        message_body.get("resume_from_checkpoint")
        or message_body.get("current_stage")
        or "sort_documents_final"
    )

    logger.info("[archive_worker] final_pipeline: run_id=%s stage=%s", run_id, current_stage)

    config, state = await _load_workflow_state(
        run_id=run_id,
        batch_id=batch_id,
        tenant_id=tenant_id,
        current_stage=current_stage,
    )
    state["current_stage"] = current_stage
    state["affected_scope"] = dict(message_body.get("affected_scope") or state.get("affected_scope") or {})
    state["resume_from_checkpoint"] = message_body.get("resume_from_checkpoint") or state.get("resume_from_checkpoint")

    result = await archive_final_subgraph.ainvoke(state)
    state.update(result or {})

    await _save_checkpoint_state(config, state)
    final_stage = str(state.get("current_stage") or current_stage)
    final_status = str(state.get("final_status") or "pending")
    await _persist_workflow_progress(
        run_id=run_id,
        current_stage=final_stage,
        run_status="done" if final_status == "done" or final_stage == "done" else "running",
        state=state,
    )


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
    "relation_analysis_queue": _handle_relation_analysis,
    "draft_pipeline_queue": _handle_draft_pipeline,
    "final_pipeline_queue": _handle_final_pipeline,
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
