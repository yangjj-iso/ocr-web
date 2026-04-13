"""
Archive Document Workflow — 档案智能整理 LangGraph 工作流（4层结构）。

架构层次（遵循 Develop.md 第十五节）：
1. main_graph      — 整卷主流程（接入 → 分件 → 双轨分流 → 定稿 → 导出）
2. draft_subgraph  — 草稿轨（字段提取/标签/目录/审核任务生成）
3. final_subgraph  — 正式轨（排序/编号/著录/目录/导出/入库）
4. resume_subgraph — 恢复/返工（审核后恢复、局部重跑、失效传播）

State 结构遵循 Develop.md 第十五节 § 2。
节点清单遵循 Develop.md 第十五节 § 3。
条件路由遵循 Develop.md 第十五节 § 4。
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from functools import lru_cache
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict, cast

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import interrupt

from app.config import (
    LANGGRAPH_CHECKPOINTER_BACKEND,
    LANGGRAPH_CHECKPOINTER_DSN,
    LANGGRAPH_CHECKPOINTER_REDIS_URL,
)

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_langgraph_checkpointer():
    backend = LANGGRAPH_CHECKPOINTER_BACKEND
    if backend == "postgres" and LANGGRAPH_CHECKPOINTER_DSN:
        try:
            from langgraph.checkpoint.postgres import PostgresSaver  # type: ignore[import-not-found]

            saver_factory = getattr(PostgresSaver, "from_conn_string", None)
            if callable(saver_factory):
                return saver_factory(LANGGRAPH_CHECKPOINTER_DSN)
            raise RuntimeError("PostgresSaver.from_conn_string is unavailable")
        except Exception:
            logger.warning(
                "Falling back to InMemorySaver because Postgres checkpointer is unavailable.",
                exc_info=True,
            )
    if backend == "redis" and LANGGRAPH_CHECKPOINTER_REDIS_URL:
        try:
            from langgraph.checkpoint.redis import RedisSaver  # type: ignore[import-not-found]

            saver_factory = getattr(RedisSaver, "from_conn_string", None)
            if callable(saver_factory):
                return saver_factory(LANGGRAPH_CHECKPOINTER_REDIS_URL)
            raise RuntimeError("RedisSaver.from_conn_string is unavailable")
        except Exception:
            logger.warning(
                "Falling back to InMemorySaver because Redis checkpointer is unavailable.",
                exc_info=True,
            )
    return InMemorySaver()


# ---------------------------------------------------------------------------
# State 定义
# ---------------------------------------------------------------------------

class AffectedScope(TypedDict, total=False):
    page_ids: list[str]
    doc_ids: list[str]
    renumber_from_order_index: int | None
    regenerate_catalog: bool
    regenerate_pdf: bool


class WorkflowArtifacts(TypedDict, total=False):
    draft_catalog_path: str | None
    draft_pdf_path: str | None
    final_catalog_path: str | None
    final_pdf_path: str | None


class WorkflowCheckpoints(TypedDict, total=False):
    after_ocr: str | None
    after_page_analysis: str | None
    after_split: str | None
    after_draft_metadata: str | None
    after_final_sort: str | None
    after_final_catalog: str | None


class ArchiveWorkflowState(TypedDict, total=False):
    # 标识
    task_id: str
    batch_id: str
    tenant_id: str
    policy_snapshot_id: str | None
    run_mode: str                         # normal / resume / rework

    # 阶段
    current_stage: str
    draft_status: str                     # pending/running/done/blocked/failed
    final_status: str                     # pending/running/blocked/done/failed
    review_status: str                    # none/pending/in_review/resolved

    # 数据
    pages: list[dict[str, Any]]           # page schema 列表
    draft_docs: list[dict[str, Any]]      # 草稿件列表
    final_docs: list[dict[str, Any]]      # 正式件列表
    review_tasks: list[str]               # review_task_id 列表
    blocked_reasons: list[str]

    # 恢复控制
    affected_scope: AffectedScope
    resume_from_checkpoint: str | None
    resume_reason: str

    # 产物引用
    checkpoints: WorkflowCheckpoints
    artifacts: WorkflowArtifacts

    # 指标
    metrics: dict[str, Any]

    # 规则快照内容（运行时加载）
    policy_rules: dict[str, Any]

    # 审核结果（外部传入，用于恢复时应用字段修正）
    review_result: dict[str, Any] | None


# ---------------------------------------------------------------------------
# 辅助函数
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_checkpoint_id(stage: str) -> str:
    return f"ckpt_{stage}_{uuid.uuid4().hex[:8]}"


# ---------------------------------------------------------------------------
# 节点实现
# ---------------------------------------------------------------------------

async def node_ingest_batch(state: ArchiveWorkflowState) -> dict[str, Any]:
    """节点 1：接入批次，创建 WorkflowRun 记录，发送 WORKFLOW_STARTED 事件。"""
    task_id = state.get("task_id", "")
    batch_id = state.get("batch_id", "")
    tenant_id = state.get("tenant_id", "default")
    logger.info("[%s] ingest_batch: batch_id=%s", task_id, batch_id)

    # 创建 WorkflowRun 记录（Develop.md §16.1）
    try:
        from app.db.database import async_session as AsyncSessionLocal
        from app.db.models import WorkflowRun
        async with AsyncSessionLocal() as db:
            run = WorkflowRun(
                run_id=task_id,
                batch_id=batch_id,
                tenant_id=tenant_id,
                run_type=state.get("run_mode", "normal"),
                run_status="running",
                current_stage="ingest_batch",
                state_json={},
                blocked_reasons_json=[],
                policy_snapshot_id=state.get("policy_snapshot_id"),
            )
            db.add(run)
            await db.commit()
    except Exception:
        logger.exception("Failed to create WorkflowRun for task_id=%s", task_id)

    # 发送 WORKFLOW_STARTED 事件（Develop.md §17.3）
    try:
        from app.infrastructure.callback.workflow_events import emit_workflow_started
        await emit_workflow_started(
            task_id=task_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            page_count=len(state.get("pages") or []),
        )
    except Exception:
        logger.exception("Failed to emit WORKFLOW_STARTED for task_id=%s", task_id)

    return {
        "current_stage": "load_policy_snapshot",
        "draft_status": "running",
        "final_status": "pending",
        "review_status": "none",
        "pages": state.get("pages") or [],
        "draft_docs": [],
        "final_docs": [],
        "review_tasks": [],
        "blocked_reasons": [],
        "metrics": {"started_at": _utc_now(), "page_count": len(state.get("pages") or [])},
    }


async def node_load_policy_snapshot(state: ArchiveWorkflowState) -> dict[str, Any]:
    """节点 2：加载规则快照，固定本次运行使用的规则版本。"""
    from sqlalchemy import select
    snapshot_id = state.get("policy_snapshot_id")
    policy_rules: dict[str, Any] = {}

    if snapshot_id:
        try:
            from app.db.database import async_session as AsyncSessionLocal
            from app.db.models import PolicySnapshot
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(PolicySnapshot).where(PolicySnapshot.snapshot_id == snapshot_id).limit(1)
                )
                snap = result.scalar_one_or_none()
                if snap:
                    policy_rules = snap.rules_json or {}
        except Exception:
            logger.exception("Failed to load policy snapshot %s, using defaults", snapshot_id)

    return {
        "current_stage": "preprocess_pages",
        "policy_rules": policy_rules,
    }


async def node_preprocess_pages(state: ArchiveWorkflowState) -> dict[str, Any]:
    """
    节点 3：图像预处理（旋转矫正、去噪等）。

    前提契约（Develop.md §2）：
      本节点假设调用方（Java 控制面 / external worker）在构造 pages 数据时，
      已完成图像上传到 MinIO，且每页 page 至少包含：
        - page_id     （唯一标识）
        - page_index  （0-based 页号）
        - image_uri   （MinIO 图像路径，非空）
      OCR 执行、pHash 计算由专用图像 worker 完成，结果写回 page 后再投入工作流。
      若 image_uri 缺失，后续 pHash 计算将降级为无 pHash 模式（不中断流程）。
    """
    pages = state.get("pages") or []
    missing_uri = [p.get("page_id", str(i)) for i, p in enumerate(pages) if not p.get("image_uri")]
    if missing_uri:
        logger.warning(
            "[%s] preprocess_pages: %d pages missing image_uri: %s",
            state.get("task_id"), len(missing_uri), missing_uri[:5],
        )
    logger.info(
        "[%s] preprocess_pages: %d pages (image_uri present: %d)",
        state.get("task_id"),
        len(pages),
        len(pages) - len(missing_uri),
    )
    # 实际预处理通过专用队列派发，此处仅推进状态
    return {"current_stage": "run_ocr"}


async def node_run_ocr(state: ArchiveWorkflowState) -> dict[str, Any]:
    """
    节点 4：并行对所有页面执行 OCR。

    前提契约（Develop.md §2）：
      本节点假设 pages 中每页的 ocr_text / ocr_blocks / phash 字段
      已由外部 OCR worker（接收 ocr_queue 消息）填充完毕后传入本工作流。
      若 ocr_text 为空，后续特征提取将产生空候选，分件置信度会下降，
      并触发 review_required 审核任务，由人工补救——这是设计预期行为。
    """
    pages = state.get("pages") or []
    missing_ocr = sum(1 for p in pages if not (p.get("ocr_text") or "").strip())
    if missing_ocr:
        logger.warning(
            "[%s] run_ocr: %d/%d pages have empty ocr_text — OCR worker may not have run yet",
            state.get("task_id"), missing_ocr, len(pages),
        )
    logger.info(
        "[%s] run_ocr: %d pages (ocr_text filled: %d)",
        state.get("task_id"), len(pages), len(pages) - missing_ocr,
    )
    return {
        "current_stage": "extract_page_features",
        "checkpoints": {
            **(state.get("checkpoints") or {}),
            "after_ocr": _new_checkpoint_id("after_ocr"),
        },
    }


async def _extract_page_feature(page: dict[str, Any], *, task_id: str) -> dict[str, Any]:
    from app.domains.page_processing.page_service import (
        build_page_schema,
        compute_phash_from_uri,
        extract_candidates_from_text,
        score_first_page,
    )

    ocr_text = page.get("ocr_text") or ""
    candidates = extract_candidates_from_text(ocr_text)
    first_page_score = score_first_page(ocr_text, candidates)

    phash_val = page.get("phash")
    if not phash_val and page.get("image_uri"):
        try:
            phash_val = await compute_phash_from_uri(page["image_uri"])
        except Exception:
            logger.debug(
                "[%s] phash computation failed for page_id=%s, continuing without phash",
                task_id,
                page.get("page_id", ""),
            )

    return build_page_schema(
        page_id=page.get("page_id", ""),
        batch_id=page.get("batch_id", ""),
        page_index=page.get("page_index", 0),
        image_uri=page.get("image_uri", ""),
        ocr_text=ocr_text,
        ocr_blocks=page.get("ocr_blocks"),
        layout_type=page.get("layout_type"),
        phash=phash_val,
        first_page_score=first_page_score,
        duplicate_score=page.get("duplicate_score", 0.0),
        candidates=candidates,
    )


async def node_extract_page_features(state: ArchiveWorkflowState) -> dict[str, Any]:
    """
    节点 5：提取页面特征（pHash / 首页得分 / 候选字段）。

    若 page 中已有 phash（由外部 OCR worker 计算），直接复用；
    若 phash 缺失且 image_uri 可达，则在此处直接计算（降级模式，建议生产以 OCR worker 为主）。
    """
    pages = state.get("pages") or []
    task_id = state.get("task_id", "")
    updated_pages = list(
        await asyncio.gather(
            *[_extract_page_feature(page, task_id=task_id) for page in pages]
        )
    ) if pages else []

    return {
        "current_stage": "analyze_page_relations",
        "pages": updated_pages,
    }


async def node_analyze_page_relations(state: ArchiveWorkflowState) -> dict[str, Any]:
    """
    节点 6：页面关系分析（相邻页连续性、新件信号、重复页）。

    输出每页 page_relation_json，包含 splitting_service 所需的全部信号：
      - phash_similarity_to_prev  → 分件权重 0.10
      - doc_no_changed            → 分件权重 0.50
      - relation_analysis_new_doc → 分件权重 0.30
      - is_new_doc_start          → 高置信首页标记
      - is_duplicate              → 重复页标记
    """
    from app.domains.page_processing.page_service import score_duplicate_page

    pages = state.get("pages") or []
    logger.info("[%s] analyze_page_relations: %d pages", state.get("task_id"), len(pages))

    analyzed: list[dict[str, Any]] = []
    for i, page in enumerate(pages):
        prev = pages[i - 1] if i > 0 else None

        # pHash 与前一页的视觉相似度（0.0 = 完全不同, 1.0 = 相同）
        phash_sim = 0.0
        if prev is not None:
            phash_sim = score_duplicate_page(
                prev.get("phash"),
                page.get("phash"),
            )

        # 文号变化：文号均存在且不相同时视为边界强信号
        prev_cands = (prev.get("candidates") or {}) if prev else {}
        curr_cands = page.get("candidates") or {}
        prev_doc_no = (prev_cands.get("doc_nos") or [None])[0]
        curr_doc_no = (curr_cands.get("doc_nos") or [None])[0]
        doc_no_changed = bool(
            prev_doc_no and curr_doc_no and prev_doc_no != curr_doc_no
        )

        # 关系分析综合结论：首页得分高 OR 文号变化
        first_page_score = page.get("first_page_score", 0.0)
        relation_analysis_new_doc = first_page_score >= 0.50 or doc_no_changed

        relation: dict[str, Any] = {
            "prev_page_index": i - 1 if i > 0 else None,
            "phash_similarity_to_prev": round(phash_sim, 4),
            "doc_no_changed": doc_no_changed,
            "is_new_doc_start": first_page_score >= 0.65,
            "is_duplicate": phash_sim >= 0.85,
            "relation_analysis_new_doc": relation_analysis_new_doc,
        }
        analyzed.append({**page, "page_relation_json": relation})

    return {
        "current_stage": "split_documents",
        "pages": analyzed,
        "checkpoints": {
            **(state.get("checkpoints") or {}),
            "after_page_analysis": _new_checkpoint_id("after_page_analysis"),
        },
    }


async def node_split_documents(state: ArchiveWorkflowState) -> dict[str, Any]:
    """节点 7：自动分件，生成草稿件集合。"""
    from app.domains.document_splitting.splitting_service import (
        detect_boundaries,
        split_into_draft_docs,
        to_doc_schema,
    )

    pages = state.get("pages") or []
    batch_id = state.get("batch_id", "")

    boundaries = detect_boundaries(pages)
    draft_docs_objs = split_into_draft_docs(pages, boundaries, batch_id)
    draft_docs = [to_doc_schema(d) for d in draft_docs_objs]

    logger.info(
        "[%s] split_documents: %d pages → %d draft docs",
        state.get("task_id"),
        len(pages),
        len(draft_docs),
    )

    return {
        "current_stage": "assess_split_risk",
        "draft_docs": draft_docs,
        "checkpoints": {
            **(state.get("checkpoints") or {}),
            "after_split": _new_checkpoint_id("after_split"),
        },
    }


async def node_assess_split_risk(state: ArchiveWorkflowState) -> dict[str, Any]:
    """节点 8：评估分件风险，决定是否阻塞 Final 轨。"""
    draft_docs = state.get("draft_docs") or []
    policy_rules = state.get("policy_rules") or {}

    # 建议 4：阈值从规则快照读取，允许不同业务场景差异化配置
    threshold: float = float(policy_rules.get("split_confidence_threshold", 0.55))

    review_required = [d for d in draft_docs if d.get("status") == "review_required"]
    low_confidence = [d for d in draft_docs if d.get("confidence", 1.0) < threshold]
    needs_block = bool(review_required or low_confidence)

    block_reasons = []
    if review_required:
        block_reasons.append(f"{len(review_required)} docs need boundary review")
    if low_confidence:
        block_reasons.append(
            f"{len(low_confidence)} docs have confidence < {threshold}"
        )

    return {
        "current_stage": "run_draft_subgraph",
        "blocked_reasons": block_reasons if needs_block else [],
        "final_status": "blocked" if needs_block else "pending",
    }


async def node_run_draft_subgraph(state: ArchiveWorkflowState) -> dict[str, Any]:
    """
    节点 9：Draft 轨——字段提取/标签/质量评分/草稿目录/持久化。

    Develop.md §6（双轨分流）、§10（自动著录与标签）、§19.1（质量评分）。
    """
    task_id = state.get("task_id", "")
    batch_id = state.get("batch_id", "")
    tenant_id = state.get("tenant_id", "default")
    draft_docs = [d.copy() for d in (state.get("draft_docs") or [])]
    pages = state.get("pages") or []
    policy_rules = state.get("policy_rules") or {}

    logger.info("[%s] run_draft_subgraph: %d docs", task_id, len(draft_docs))

    # 1. 字段提取 + 标签生成（Develop.md §10 混合策略：规则优先）
    from app.domains.draft_pipeline.draft_service import (
        extract_draft_metadata,
        generate_draft_tags,
        build_draft_catalog,
        upload_draft_catalog,
        persist_draft_docs,
        register_artifact,
        draft_catalog_storage_uri,
        draft_pdf_storage_uri,
    )
    for i, doc in enumerate(draft_docs):
        meta = extract_draft_metadata(doc, pages, policy_rules)
        # Opt 2: subject_categories 关键词匹配注入 doc，generate_draft_tags 内部读取
        doc["_policy_rules"] = policy_rules
        tags = generate_draft_tags(doc, pages)
        doc["metadata_json"] = {
            "title": meta["title"],
            "date": meta["date"],
            "doc_no": meta["doc_no"],
            "page_count": meta["page_count"],
            "preservation_period": meta["preservation_period"],
            "responsible_party": meta.get("responsible_party", ""),
        }
        doc["tags"] = tags
        doc["sort_index"] = i

    # 2. 质量评分门控（Develop.md §19.1：final_readiness_score 公式）
    from app.domains.quality.quality_service import compute_quality_scores, is_ready_for_final
    quality_scores = compute_quality_scores(pages, draft_docs, policy_rules)

    # 从规则快照读取 final_readiness_threshold（建议 4）
    readiness_threshold: float = float(
        policy_rules.get("final_readiness_threshold", 0.60)
    )

    blocked_reasons = list(state.get("blocked_reasons") or [])
    if not is_ready_for_final(quality_scores, threshold=readiness_threshold):
        score = quality_scores.get("final_readiness_score", 0)
        blocked_reasons.append(f"quality_gate_failed: final_readiness_score={score:.3f}")

        # 建议 7：质量门控失败时生成 metadata 审核任务，让人工知道要补什么字段
        meta_low_docs = [
            d for d in draft_docs
            if not (d.get("metadata_json") or {}).get("title")
            or not (d.get("metadata_json") or {}).get("date")
        ]
        if meta_low_docs:
            logger.info(
                "[%s] quality gate failed, %d docs need metadata review",
                task_id, len(meta_low_docs),
            )
            # 在 create_review_tasks 节点统一创建；此处预填 draft_docs 状态
            for d in meta_low_docs:
                if d.get("status") == "draft":
                    d["status"] = "review_required"
                    if not d.get("boundary_reason"):
                        d["boundary_reason"] = "metadata_quality_insufficient"

    # 3. 持久化 DocUnit + DocVersion(version_type='draft')（Develop.md §16.2）
    catalog_uri = draft_catalog_storage_uri(tenant_id, batch_id)
    doc_ids: list[str] = []
    try:
        from app.db.database import async_session as AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            doc_ids = await persist_draft_docs(
                db,
                draft_docs,
                batch_id=batch_id,
                tenant_id=tenant_id,
                run_id=task_id,
                quality_scores=quality_scores,
            )
            await register_artifact(
                db,
                batch_id=batch_id,
                artifact_type="draft_catalog",
                storage_uri=catalog_uri,
                run_id=task_id,
            )
    except Exception:
        logger.exception("[%s] Failed to persist draft docs", task_id)

    # 4. 草稿卷内目录结构（Develop.md §11）+ Opt 6：实际上传到 MinIO
    catalog = build_draft_catalog(draft_docs, batch_id=batch_id, tenant_id=tenant_id)
    try:
        actual_catalog_uri = await upload_draft_catalog(catalog, batch_id=batch_id, tenant_id=tenant_id)
        catalog_uri = actual_catalog_uri
    except Exception:
        logger.exception("[%s] draft catalog upload failed, using placeholder uri", task_id)

    # 4.5 生成 Draft searchable PDF（Develop.md §6）
    draft_pdf_path = draft_pdf_storage_uri(tenant_id, batch_id)
    try:
        from app.services.export_service import export_searchable_pdf

        pages_by_id = {p.get("page_id"): p for p in pages}
        draft_doc_ids = [doc_id for doc_id in (d.get("tmp_doc_id") for d in draft_docs) if isinstance(doc_id, str) and doc_id]
        ordered_pages: list[dict[str, Any]] = []
        for doc in draft_docs:
            for pid in doc.get("page_ids") or []:
                page = pages_by_id.get(pid)
                if page:
                    ordered_pages.append(page)

        if ordered_pages:
            draft_pdf_path = await export_searchable_pdf(
                batch_id=batch_id,
                tenant_id=tenant_id,
                pages=ordered_pages,
                doc_ids=doc_ids or draft_doc_ids,
                version=1,
                run_id=task_id,
                export_type="draft",
            )
        else:
            logger.warning("[%s] run_draft_subgraph: no pages for draft PDF generation", task_id)
    except Exception:
        logger.exception("[%s] draft searchable PDF generation failed", task_id)

    # 5. 发送 NODE_COMPLETED 事件（Develop.md §17.3）
    try:
        from app.infrastructure.callback.workflow_events import emit_node_completed
        await emit_node_completed(
            task_id=task_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            stage="run_draft_subgraph",
            extra={
                "doc_count": len(draft_docs),
                "quality_scores": quality_scores,
                "catalog_entry_count": len(catalog.get("entries", [])),
            },
        )
    except Exception:
        logger.exception("Failed to emit NODE_COMPLETED after draft subgraph")

    return {
        "current_stage": "create_review_tasks",
        "draft_status": "done",
        "draft_docs": draft_docs,
        "blocked_reasons": blocked_reasons,
        "artifacts": {
            **(state.get("artifacts") or {}),
            "draft_catalog_path": catalog_uri,
            "draft_pdf_path": draft_pdf_path,
        },
        "metrics": {
            **(state.get("metrics") or {}),
            "quality_scores": quality_scores,
            "draft_doc_count": len(draft_docs),
        },
    }


async def node_create_review_tasks(state: ArchiveWorkflowState) -> dict[str, Any]:
    """
    节点 10：为模糊边界、低置信著录、排序冲突和 Final 放行创建人工审核任务。

    对应 Develop.md §7 和第十三节的 4 类中断点：
      boundary     — 分件/边界不确定
      metadata     — 题名/日期/责任者等著录字段缺失或冲突
      ordering     — 件级排序需人工确认（多件日期相同时）
      final_release — 整卷 Final 放行确认（仅在无阻塞时生成）
    """
    task_id = state.get("task_id", "")
    batch_id = state.get("batch_id", "")
    tenant_id = state.get("tenant_id", "default")
    draft_docs = state.get("draft_docs") or []
    blocked_reasons = state.get("blocked_reasons") or []

    task_specs: list[dict] = []

    # ── 1. boundary 审核：status=review_required 的件 ──
    boundary_docs = [d for d in draft_docs if d.get("status") == "review_required"]
    for d in boundary_docs:
        task_specs.append({
            "task_type": "boundary",
            "affected_page_ids": d.get("page_ids", []),
            "affected_doc_ids": [d.get("tmp_doc_id", "")],
            "reason": d.get("boundary_reason", "low confidence boundary"),
            "evidence": {"confidence": d.get("confidence", 0.0)},
            "confidence": d.get("confidence", 0.0),
        })

    # ── 2. metadata 审核：关键字段为空的件 ──
    metadata_docs = [
        d for d in draft_docs
        if not (d.get("metadata_json") or {}).get("title")
        or not (d.get("metadata_json") or {}).get("date")
    ]
    for d in metadata_docs:
        # 避免与 boundary 任务重复
        if d.get("status") != "review_required":
            meta = d.get("metadata_json") or {}
            missing = [f for f in ("title", "date", "doc_no") if not meta.get(f)]
            task_specs.append({
                "task_type": "metadata",
                "affected_page_ids": d.get("page_ids", []),
                "affected_doc_ids": [d.get("tmp_doc_id", "")],
                "reason": f"missing fields: {', '.join(missing)}",
                "evidence": {"missing_fields": missing, "metadata_json": meta},
                "confidence": d.get("confidence", 0.0),
            })

    # ── 3. ordering 审核：同日期多件，顺序不确定 ──
    date_groups: dict[str, list[str]] = {}
    for d in draft_docs:
        date_val = (d.get("metadata_json") or {}).get("date", "")
        if date_val:
            date_groups.setdefault(date_val, []).append(d.get("tmp_doc_id", ""))
    for date_val, doc_ids in date_groups.items():
        if len(doc_ids) > 1:
            task_specs.append({
                "task_type": "ordering",
                "affected_page_ids": [],
                "affected_doc_ids": doc_ids,
                "reason": f"multiple docs with same date {date_val}, ordering needs confirmation",
                "evidence": {"date": date_val, "doc_count": len(doc_ids)},
                "confidence": 0.5,
            })

    # ── 4. final_release 审核：整卷无阻塞时等待放行确认 ──
    if not blocked_reasons:
        all_doc_ids = [d.get("tmp_doc_id", "") for d in draft_docs]
        task_specs.append({
            "task_type": "final_release",
            "affected_page_ids": [],
            "affected_doc_ids": all_doc_ids,
            "reason": "awaiting final approval before entering Final track",
            "evidence": {"doc_count": len(draft_docs)},
            "confidence": 1.0,
        })

    if not task_specs:
        logger.info("[%s] create_review_tasks: no review tasks needed", task_id)
        return {
            "current_stage": "gate_final_subgraph",
            "review_status": "none",
            "review_tasks": [],
        }

    review_task_ids: list[str] = []
    try:
        from app.db.database import async_session as AsyncSessionLocal
        from app.domains.review.review_service import create_review_tasks
        async with AsyncSessionLocal() as db:
            review_task_ids = await create_review_tasks(
                db,
                batch_id=batch_id,
                tenant_id=tenant_id,
                run_id=task_id,
                task_specs=task_specs,
            )
    except Exception:
        logger.exception("Failed to create review tasks")

    logger.info(
        "[%s] create_review_tasks: created %d tasks (boundary=%d metadata=%d ordering=%d final_release=%d)",
        task_id, len(review_task_ids),
        len(boundary_docs),
        len(metadata_docs),
        len([s for s in task_specs if s["task_type"] == "ordering"]),
        len([s for s in task_specs if s["task_type"] == "final_release"]),
    )

    # 发送 REVIEW_TASK_CREATED 事件（Develop.md §17.3）
    try:
        from app.infrastructure.callback.workflow_events import emit_review_task_created
        await emit_review_task_created(
            task_id=task_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            review_task_ids=review_task_ids,
            task_count=len(review_task_ids),
        )
    except Exception:
        logger.exception("Failed to emit REVIEW_TASK_CREATED for task_id=%s", task_id)

    return {
        "current_stage": "wait_for_review",
        "review_status": "pending",
        "review_tasks": review_task_ids,
    }


async def node_gate_final_subgraph(state: ArchiveWorkflowState) -> dict[str, Any]:
    """节点 11：Final 轨入口判断。只有没有阻塞原因时才放行。"""
    blocked = state.get("blocked_reasons") or []
    if blocked:
        return {
            "current_stage": "wait_for_review",
            "final_status": "blocked",
        }
    return {
        "current_stage": "sort_documents_final",
        "final_status": "running",
    }


async def node_wait_for_review(state: ArchiveWorkflowState) -> dict[str, Any]:
    """
    节点 12：等待人工审核（LangGraph interrupt 中断点）。

    首次执行时：
      1. 更新 WorkflowRun.run_status = 'blocked'
      2. 发送 WORKFLOW_BLOCKED 事件给 Java 控制面
      3. 调用 interrupt() 暂停图执行

    resume_archive_workflow() 调用 aupdate_state(review_status='resolved') 后，
    本节点再次运行时检测到 review_status=resolved，跳过 interrupt 继续执行。
    """
    task_id = state.get("task_id", "")
    batch_id = state.get("batch_id", "")
    tenant_id = state.get("tenant_id", "default")

    # 恢复路径：已 resolved，直接通过，不再中断
    if state.get("review_status") == "resolved":
        logger.info("[%s] wait_for_review: already resolved, proceeding", task_id)
        return {}

    logger.info("[%s] wait_for_review: blocking with interrupt()", task_id)

    # 更新 WorkflowRun.run_status = 'blocked'（Develop.md §16.1）
    try:
        from sqlalchemy import update as sa_update
        from app.db.database import async_session as AsyncSessionLocal
        from app.db.models import WorkflowRun
        async with AsyncSessionLocal() as db:
            await db.execute(
                sa_update(WorkflowRun)
                .where(WorkflowRun.run_id == task_id)
                .values(
                    run_status="blocked",
                    current_stage="wait_for_review",
                    blocked_reasons_json=state.get("blocked_reasons") or [],
                )
            )
            await db.commit()
    except Exception:
        logger.exception("Failed to update WorkflowRun to blocked for task_id=%s", task_id)

    # 发送 WORKFLOW_BLOCKED 事件（Develop.md §17.3）
    try:
        from app.infrastructure.callback.workflow_events import emit_workflow_blocked
        await emit_workflow_blocked(
            task_id=task_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            stage="wait_for_review",
            blocked_reasons=state.get("blocked_reasons") or [],
        )
    except Exception:
        logger.exception("Failed to emit WORKFLOW_BLOCKED for task_id=%s", task_id)

    # LangGraph interrupt()：暂停图执行，等待外部 resume_archive_workflow() 恢复
    interrupt({
        "reason": "waiting_for_human_review",
        "batch_id": batch_id,
        "review_tasks": state.get("review_tasks") or [],
        "blocked_reasons": state.get("blocked_reasons") or [],
    })

    return {
        "current_stage": "wait_for_review",
        "final_status": "blocked",
        "review_status": "in_review",
    }


async def node_resume_from_review(state: ArchiveWorkflowState) -> dict[str, Any]:
    """节点 13：审核完成后恢复，应用字段修正/排序调整，动态路由回局部重跑节点。

    Develop.md §18.5：
    - boundary_rejected  → draft_subgraph 重跑
    - field_corrected    → 应用字段修正到 draft_docs，路由到 build_catalog_final
    - order_adjusted     → sort_documents_final（重新排序+编号）
    - boundary_confirmed → sort_documents_final
    """
    from app.domains.rework.invalidation_service import earliest_invalidated_stage

    task_id = state.get("task_id", "")
    batch_id = state.get("batch_id", "")
    tenant_id = state.get("tenant_id", "default")
    affected_scope = state.get("affected_scope") or {}
    review_result = state.get("review_result") or {}

    logger.info(
        "[%s] resume_from_review: reason=%s result_type=%s affected_scope=%s",
        task_id, state.get("resume_reason"), review_result.get("result_type"), affected_scope,
    )

    # 将审核结果中的字段修正应用到 draft_docs（field_corrected 层次）
    draft_docs = [d.copy() for d in (state.get("draft_docs") or [])]
    if review_result.get("result_type") == "field_corrected":
        field_updates: dict[str, dict[str, str]] = review_result.get("field_updates") or {}
        doc_id_to_idx = {d.get("tmp_doc_id", ""): i for i, d in enumerate(draft_docs)}
        for doc_id, updates in field_updates.items():
            idx = doc_id_to_idx.get(doc_id)
            if idx is not None:
                meta = draft_docs[idx].get("metadata_json") or {}
                meta.update({k: v for k, v in updates.items() if v})
                draft_docs[idx]["metadata_json"] = meta
                draft_docs[idx]["status"] = "draft"  # 重置为完成状态
        logger.info(
            "[%s] resume_from_review: applied field corrections to %d docs",
            task_id, len(field_updates)
        )

    # boundary_confirmed 后重置 review_required 件的状态
    if review_result.get("result_type") == "boundary_confirmed":
        for d in draft_docs:
            if d.get("status") == "review_required":
                d["status"] = "draft"

    # 根据失效范围确定回退节点
    target_stage = earliest_invalidated_stage(dict(affected_scope))

    # 更新 WorkflowRun.run_status（Develop.md §16.1）
    try:
        from sqlalchemy import update as sa_update
        from app.db.database import async_session as AsyncSessionLocal
        from app.db.models import WorkflowRun
        async with AsyncSessionLocal() as db:
            await db.execute(
                sa_update(WorkflowRun)
                .where(WorkflowRun.run_id == task_id)
                .values(
                    run_status="running",
                    current_stage=target_stage,
                    blocked_reasons_json=[],
                )
            )
            await db.commit()
    except Exception:
        logger.exception("Failed to update WorkflowRun on resume for task_id=%s", task_id)

    # 发送 WORKFLOW_RESUMED 事件（Develop.md §17.3）
    try:
        from app.infrastructure.callback.workflow_events import emit_workflow_resumed
        await emit_workflow_resumed(
            task_id=task_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            reason=state.get("resume_reason", ""),
        )
    except Exception:
        logger.exception("Failed to emit WORKFLOW_RESUMED for task_id=%s", task_id)

    return {
        "current_stage": target_stage,
        "blocked_reasons": [],
        "final_status": "running",
        "review_status": "resolved",
        "draft_docs": draft_docs,
        "review_result": None,       # 用完清除，避免下次误用
    }


async def node_sort_documents_final(state: ArchiveWorkflowState) -> dict[str, Any]:
    """节点 14：Final 正式排序。"""
    from app.domains.document_sorting.sorting_service import sort_docs

    docs = [d.copy() for d in (state.get("draft_docs") or [])]
    sorted_docs = sort_docs(docs)

    return {
        "current_stage": "assign_archive_numbers",
        "final_docs": sorted_docs,
        "checkpoints": {
            **(state.get("checkpoints") or {}),
            "after_final_sort": _new_checkpoint_id("after_final_sort"),
        },
    }


async def node_assign_archive_numbers(state: ArchiveWorkflowState) -> dict[str, Any]:
    """节点 15：分配正式档案编号（必须在排序确认之后）。"""
    from app.domains.document_sorting.sorting_service import assign_archive_numbers

    batch_id = state.get("batch_id", "")
    policy_rules = state.get("policy_rules") or {}
    final_docs = [d.copy() for d in (state.get("final_docs") or [])]
    # Opt 1：从 policy_rules.numbering_rules 读取编号格式
    numbered_docs = assign_archive_numbers(
        final_docs, batch_id=batch_id, policy_rules=policy_rules
    )

    return {
        "current_stage": "extract_metadata_final",
        "final_docs": numbered_docs,
    }


async def node_extract_metadata_final(state: ArchiveWorkflowState) -> dict[str, Any]:
    """
    节点 16：Final 正式著录——规则优先字段提取 + 质量评分 + 持久化 DocVersion(final)。

    Develop.md §10 混合策略：规则字段（date/doc_no）优先，空值才用规则推断。
    """
    task_id = state.get("task_id", "")
    batch_id = state.get("batch_id", "")
    tenant_id = state.get("tenant_id", "default")
    final_docs = [d.copy() for d in (state.get("final_docs") or [])]
    pages = state.get("pages") or []
    policy_rules = state.get("policy_rules") or {}

    logger.info("[%s] extract_metadata_final: %d docs", task_id, len(final_docs))

    # rules-first 策略提取字段，保留草稿已有字段，仅补空值
    from app.domains.draft_pipeline.draft_service import (
        extract_draft_metadata,
        generate_draft_tags,
    )
    for doc in final_docs:
        meta = extract_draft_metadata(doc, pages, policy_rules)
        existing = doc.get("metadata_json") or {}
        doc["metadata_json"] = {
            "title": existing.get("title") or meta["title"],
            "date": existing.get("date") or meta["date"],
            "doc_no": existing.get("doc_no") or meta["doc_no"],
            "page_count": meta["page_count"],
            "preservation_period": existing.get("preservation_period") or meta["preservation_period"],
            "responsible_party": existing.get("responsible_party", ""),
        }
        # Opt 2: 传入 policy_rules 供主题标签关键词匹配
        doc["_policy_rules"] = policy_rules
        doc["tags"] = generate_draft_tags(doc, pages)

    # Gap 4：LLM 补全——规则提取后 title / responsible_party 仍为空时调用 LLM 兜底
    try:
        from app.services.llm_field_extraction_service import call_minimax_field_extraction
        llm_enabled = policy_rules.get("llm_supplement_enabled", True)
        if llm_enabled:
            for doc in final_docs:
                existing = doc.get("metadata_json") or {}
                missing_fields = [
                    f for f in ("title", "responsible_party")
                    if not existing.get(f)
                ]
                if not missing_fields:
                    continue
                # 取该件前三页 OCR 文本作为上下文
                doc_page_ids = set(doc.get("page_ids") or [])
                doc_pages = [p for p in pages if p.get("page_id") in doc_page_ids]
                full_text = "\n".join(p.get("ocr_text", "") for p in doc_pages[:3])
                if not full_text.strip():
                    continue
                # 调用 Minimax LLM 提取缺失字段（中文字段名映射）
                llm_result = await call_minimax_field_extraction(
                    filename=f"batch_{batch_id}_doc_{doc.get('tmp_doc_id', '')}",
                    page_count=len(doc_pages),
                    full_text=full_text,
                    result_json={},
                    rule_fields={
                        "题名": existing.get("title", ""),
                        "责任者": existing.get("responsible_party", ""),
                        "文号": existing.get("doc_no", ""),
                        "日期": existing.get("date", ""),
                    },
                )
                llm_fields = llm_result.get("llm_fields", {})
                # 仅用 LLM 结果填充原本为空的字段
                field_map = {"title": "题名", "responsible_party": "责任者"}
                for eng, chn in field_map.items():
                    if eng in missing_fields and llm_fields.get(chn):
                        existing[eng] = llm_fields[chn]
                doc["metadata_json"] = existing
                logger.debug(
                    "[%s] LLM supplemented doc=%s fields=%s",
                    task_id, doc.get("tmp_doc_id", ""), missing_fields,
                )
    except Exception:
        logger.exception("[%s] LLM supplement step failed, continuing without it", task_id)

    # 持久化 DocVersion(version_type='final')（Develop.md §16.2）
    from app.domains.quality.quality_service import compute_quality_scores
    from app.domains.draft_pipeline.draft_service import persist_draft_docs
    quality_scores = compute_quality_scores(pages, final_docs, policy_rules)
    try:
        from app.db.database import async_session as AsyncSessionLocal
        async with AsyncSessionLocal() as db:
            await persist_draft_docs(
                db,
                final_docs,
                batch_id=batch_id,
                tenant_id=tenant_id,
                run_id=task_id,
                quality_scores=quality_scores,
            )
    except Exception:
        logger.exception("[%s] Failed to persist final doc metadata", task_id)

    # 发送 NODE_COMPLETED 事件（Develop.md §17.3）
    try:
        from app.infrastructure.callback.workflow_events import emit_node_completed
        await emit_node_completed(
            task_id=task_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            stage="extract_metadata_final",
            extra={"final_doc_count": len(final_docs)},
        )
    except Exception:
        logger.exception("Failed to emit NODE_COMPLETED after extract_metadata_final")

    return {
        "current_stage": "build_catalog_final",
        "final_docs": final_docs,
        "checkpoints": {
            **(state.get("checkpoints") or {}),
            "after_draft_metadata": _new_checkpoint_id("after_draft_metadata"),
        },
    }


async def node_build_catalog_final(state: ArchiveWorkflowState) -> dict[str, Any]:
    """节点 17：生成正式卷内目录并上传 MinIO。"""
    from app.services.export_service import export_final_catalog_json

    task_id = state.get("task_id", "")
    batch_id = state.get("batch_id", "")
    tenant_id = state.get("tenant_id", "default")
    final_docs = state.get("final_docs") or []

    catalog_entries = [
        {
            "sort_index": d.get("sort_index", i),
            "archive_no": d.get("archive_no", ""),
            "title": (d.get("metadata_json") or {}).get("title", ""),
            "date": (d.get("metadata_json") or {}).get("date", ""),
            "doc_no": (d.get("metadata_json") or {}).get("doc_no", ""),
            "page_count": len(d.get("page_ids", [])),
            "preservation_period": (d.get("metadata_json") or {}).get("preservation_period", ""),
            "tags": d.get("tags", []),
            "responsible_party": (d.get("metadata_json") or {}).get("responsible_party", ""),
        }
        for i, d in enumerate(final_docs)
    ]

    # 实际生成并上传目录 JSON（Develop.md §16.2）
    catalog_path = await export_final_catalog_json(
        batch_id=batch_id,
        tenant_id=tenant_id,
        entries=catalog_entries,
        version=1,
        run_id=task_id,
    )

    logger.info(
        "[%s] build_catalog_final: %d entries -> %s", task_id, len(catalog_entries), catalog_path
    )

    return {
        "current_stage": "export_searchable_pdf_final",
        "artifacts": {
            **(state.get("artifacts") or {}),
            "final_catalog_path": catalog_path,
        },
        "checkpoints": {
            **(state.get("checkpoints") or {}),
            "after_final_catalog": _new_checkpoint_id("after_final_catalog"),
        },
    }


async def node_export_searchable_pdf_final(state: ArchiveWorkflowState) -> dict[str, Any]:
    """
    节点 18：生成 searchable PDF（底图 + OCR 文字层）。

    按 final_docs 中件的 page_ids 顺序从 state.pages 中提取页面，
    调用 export_service.export_searchable_pdf 合成双层 PDF 并上传 MinIO。
    """
    from app.services.export_service import export_searchable_pdf

    batch_id = state.get("batch_id", "")
    tenant_id = state.get("tenant_id", "default")
    task_id = state.get("task_id", "")

    # 按正式件顺序重排页面列表（final_docs 已由 sort_docs 排序）
    final_docs = state.get("final_docs") or []
    pages_by_id = {p.get("page_id"): p for p in (state.get("pages") or [])}
    ordered_pages: list[dict[str, Any]] = []
    for doc in final_docs:
        for pid in doc.get("page_ids") or []:
            if pid in pages_by_id:
                ordered_pages.append(pages_by_id[pid])

    if not ordered_pages:
        logger.warning("[%s] export_searchable_pdf_final: no pages, skipping PDF generation", task_id)
        pdf_path = f"tenant/{tenant_id}/batch/{batch_id}/final/searchable_v1.pdf"
    else:
        final_doc_ids = [doc_id for doc_id in (d.get("tmp_doc_id") for d in final_docs) if isinstance(doc_id, str) and doc_id]
        pdf_path = await export_searchable_pdf(
            batch_id=batch_id,
            tenant_id=tenant_id,
            pages=ordered_pages,
            doc_ids=final_doc_ids,
            version=1,
            run_id=task_id,
        )

    logger.info("[%s] export_searchable_pdf_final: path=%s pages=%d", task_id, pdf_path, len(ordered_pages))

    return {
        "current_stage": "persist_record_and_index",
        "artifacts": {
            **(state.get("artifacts") or {}),
            "final_pdf_path": pdf_path,
        },
    }


async def node_persist_record_and_index(state: ArchiveWorkflowState) -> dict[str, Any]:
    """
    节点 19：写正式卷宗记录、完成 WorkflowRun、发送 EXPORT_READY 事件。

    Develop.md §16.1（WorkflowRun.run_status='done'）、§17.3（EXPORT_READY 事件）。
    """
    from sqlalchemy import update as sa_update
    from app.db.database import async_session as AsyncSessionLocal
    from app.db.models import BatchRecord, WorkflowRun

    task_id = state.get("task_id", "")
    batch_id = state.get("batch_id", "")
    tenant_id = state.get("tenant_id", "default")
    finished_at = datetime.now(timezone.utc)

    final_docs = state.get("final_docs") or []
    pages = state.get("pages") or []

    try:
        async with AsyncSessionLocal() as db:
            # 更新 BatchRecord 状态
            await db.execute(
                sa_update(BatchRecord)
                .where(BatchRecord.batch_id == batch_id)
                .values(
                    final_status="done",
                    draft_status="done",
                    status="done",
                    review_status="resolved",
                )
            )
            # 完成 WorkflowRun（Develop.md §16.1）
            await db.execute(
                sa_update(WorkflowRun)
                .where(WorkflowRun.run_id == task_id)
                .values(
                    run_status="done",
                    current_stage="done",
                    finished_at=finished_at,
                )
            )
            await db.commit()
    except Exception:
        logger.exception("Failed to persist record for batch_id=%s", batch_id)

    # Gap 6：全文索引——将件内所有页 OCR 文本写入 doc_units.search_vector（Develop.md §14）
    try:
        from sqlalchemy import text as sa_text
        from app.db.database import async_session as _AsyncSession
        from app.db.models import DocUnit  # noqa: F401 — ensure model is loaded

        # 为每件构建完整 OCR 全文，用 to_tsvector 更新 PostgreSQL 全文索引列
        async with _AsyncSession() as db:
            for doc in final_docs:
                doc_unit_id = doc.get("doc_unit_id") or doc.get("tmp_doc_id")
                if not doc_unit_id:
                    continue
                doc_page_ids = set(doc.get("page_ids") or [])
                full_text = " ".join(
                    p.get("ocr_text", "")
                    for p in pages
                    if p.get("page_id") in doc_page_ids
                )
                if not full_text.strip():
                    continue
                # 使用 PostgreSQL to_tsvector 写入 search_vector（需 DocUnit 有该列）
                await db.execute(
                    sa_text(
                        "UPDATE doc_units SET search_vector = to_tsvector('simple', :txt)"
                        " WHERE id = :uid"
                    ),
                    {"txt": full_text[:200_000], "uid": str(doc_unit_id)},
                )
            await db.commit()
        logger.info("[%s] persist_record_and_index: full-text index updated for %d docs", task_id, len(final_docs))
    except Exception:
        logger.exception("[%s] Full-text index update failed (non-fatal)", task_id)

    logger.info("[%s] persist_record_and_index: batch_id=%s done", task_id, batch_id)

    # 发送 EXPORT_READY 事件（Develop.md §17.3）
    try:
        from app.infrastructure.callback.workflow_events import emit_export_ready
        artifacts = state.get("artifacts") or {}
        final_pdf = artifacts.get("final_pdf_path", "")
        if final_pdf:
            await emit_export_ready(
                task_id=task_id,
                batch_id=batch_id,
                tenant_id=tenant_id,
                artifact_type="final_pdf",
                storage_uri=final_pdf,
            )
        final_catalog = artifacts.get("final_catalog_path", "")
        if final_catalog:
            await emit_export_ready(
                task_id=task_id,
                batch_id=batch_id,
                tenant_id=tenant_id,
                artifact_type="final_catalog",
                storage_uri=final_catalog,
            )
    except Exception:
        logger.exception("Failed to emit EXPORT_READY for task_id=%s", task_id)

    return {
        "current_stage": "done",
        "final_status": "done",
        "draft_status": "done",
        "metrics": {
            **(state.get("metrics") or {}),
            "finished_at": finished_at.isoformat(),
            "final_doc_count": len(state.get("final_docs") or []),
        },
    }


# ---------------------------------------------------------------------------
# 条件路由
# ---------------------------------------------------------------------------

def route_after_resume(
    state: ArchiveWorkflowState,
) -> Literal["run_draft_subgraph", "sort_documents_final", "build_catalog_final"]:
    """审核恢复后动态路由：根据 affected_scope 决定回退节点。

    Develop.md §18.5：
    - invalidate_metadata/sort → run_draft_subgraph
    - invalidate_numbering     → sort_documents_final
    - invalidate_catalog/pdf   → build_catalog_final
    - 无失效                   → sort_documents_final
    """
    stage = state.get("current_stage", "sort_documents_final")
    allowed = {"run_draft_subgraph", "sort_documents_final", "build_catalog_final"}
    return stage if stage in allowed else "sort_documents_final"  # type: ignore[return-value]


def route_after_assess_split(state: ArchiveWorkflowState) -> Literal["run_draft_subgraph"]:
    """分件评估后始终先跑 Draft 轨。"""
    return "run_draft_subgraph"


def route_after_draft(state: ArchiveWorkflowState) -> Literal["create_review_tasks", "gate_final_subgraph"]:
    """Draft 完成后：有审核任务则创建，否则直接判断 Final 门控。"""
    if state.get("blocked_reasons"):
        return "create_review_tasks"
    return "gate_final_subgraph"


def route_after_review_tasks(
    state: ArchiveWorkflowState,
) -> Literal["wait_for_review", "gate_final_subgraph"]:
    """有审核任务则等待，无则继续。"""
    if state.get("review_tasks"):
        return "wait_for_review"
    return "gate_final_subgraph"


def route_gate_final(
    state: ArchiveWorkflowState,
) -> Literal["sort_documents_final", "wait_for_review"]:
    """Final 门控：有阻塞则等待，否则放行。"""
    if state.get("blocked_reasons"):
        return "wait_for_review"
    return "sort_documents_final"


def route_draft_subgraph_entry(
    state: ArchiveWorkflowState,
) -> Literal["run_draft_subgraph", "create_review_tasks", "gate_final_subgraph"]:
    """Draft 子图入口：支持从草稿生成、审核任务或 Final 门控处恢复。"""
    stage = state.get("current_stage", "run_draft_subgraph")
    allowed = {"run_draft_subgraph", "create_review_tasks", "gate_final_subgraph"}
    return stage if stage in allowed else "run_draft_subgraph"  # type: ignore[return-value]


def route_after_draft_subgraph(
    state: ArchiveWorkflowState,
) -> Literal["wait_for_review", "final_subgraph"]:
    """Draft 子图退出后，统一回到人工审核或 Final 子图。"""
    return "wait_for_review" if state.get("current_stage") == "wait_for_review" else "final_subgraph"


def route_final_subgraph_entry(
    state: ArchiveWorkflowState,
) -> Literal[
    "sort_documents_final",
    "assign_archive_numbers",
    "extract_metadata_final",
    "build_catalog_final",
    "export_searchable_pdf_final",
    "persist_record_and_index",
]:
    """Final 子图入口：支持从恢复点直接进入后半段。"""
    stage = state.get("current_stage", "sort_documents_final")
    allowed = {
        "sort_documents_final",
        "assign_archive_numbers",
        "extract_metadata_final",
        "build_catalog_final",
        "export_searchable_pdf_final",
        "persist_record_and_index",
    }
    return stage if stage in allowed else "sort_documents_final"  # type: ignore[return-value]


def route_after_resume_subgraph(
    state: ArchiveWorkflowState,
) -> Literal["draft_subgraph", "final_subgraph"]:
    """Resume 子图退出后，根据失效范围回到 Draft 或 Final。"""
    return "draft_subgraph" if state.get("current_stage") == "run_draft_subgraph" else "final_subgraph"


# ---------------------------------------------------------------------------
# 图构建
# ---------------------------------------------------------------------------


def _build_archive_draft_subgraph() -> StateGraph:
    """构建 Draft 子图：草稿生成 -> 审核任务 -> Final 门控。"""
    graph = StateGraph(ArchiveWorkflowState)

    graph.add_node("run_draft_subgraph", node_run_draft_subgraph)
    graph.add_node("create_review_tasks", node_create_review_tasks)
    graph.add_node("gate_final_subgraph", node_gate_final_subgraph)

    graph.add_conditional_edges(
        START,
        route_draft_subgraph_entry,
        {
            "run_draft_subgraph": "run_draft_subgraph",
            "create_review_tasks": "create_review_tasks",
            "gate_final_subgraph": "gate_final_subgraph",
        },
    )
    graph.add_conditional_edges(
        "run_draft_subgraph",
        route_after_draft,
        {
            "create_review_tasks": "create_review_tasks",
            "gate_final_subgraph": "gate_final_subgraph",
        },
    )
    graph.add_conditional_edges(
        "create_review_tasks",
        route_after_review_tasks,
        {
            "wait_for_review": END,
            "gate_final_subgraph": "gate_final_subgraph",
        },
    )
    graph.add_conditional_edges(
        "gate_final_subgraph",
        route_gate_final,
        {
            "sort_documents_final": END,
            "wait_for_review": END,
        },
    )

    return graph


def _build_archive_resume_subgraph() -> StateGraph:
    """构建 Resume 子图：应用审核结果并确定回退阶段。"""
    graph = StateGraph(ArchiveWorkflowState)

    graph.add_node("resume_from_review", node_resume_from_review)
    graph.add_edge(START, "resume_from_review")
    graph.add_conditional_edges(
        "resume_from_review",
        route_after_resume,
        {
            "run_draft_subgraph": END,
            "sort_documents_final": END,
            "build_catalog_final": END,
        },
    )

    return graph


def _build_archive_final_subgraph() -> StateGraph:
    """构建 Final 子图：排序、编号、著录、目录、PDF、入库。"""
    graph = StateGraph(ArchiveWorkflowState)

    graph.add_node("sort_documents_final", node_sort_documents_final)
    graph.add_node("assign_archive_numbers", node_assign_archive_numbers)
    graph.add_node("extract_metadata_final", node_extract_metadata_final)
    graph.add_node("build_catalog_final", node_build_catalog_final)
    graph.add_node("export_searchable_pdf_final", node_export_searchable_pdf_final)
    graph.add_node("persist_record_and_index", node_persist_record_and_index)

    graph.add_conditional_edges(
        START,
        route_final_subgraph_entry,
        {
            "sort_documents_final": "sort_documents_final",
            "assign_archive_numbers": "assign_archive_numbers",
            "extract_metadata_final": "extract_metadata_final",
            "build_catalog_final": "build_catalog_final",
            "export_searchable_pdf_final": "export_searchable_pdf_final",
            "persist_record_and_index": "persist_record_and_index",
        },
    )
    graph.add_edge("sort_documents_final", "assign_archive_numbers")
    graph.add_edge("assign_archive_numbers", "extract_metadata_final")
    graph.add_edge("extract_metadata_final", "build_catalog_final")
    graph.add_edge("build_catalog_final", "export_searchable_pdf_final")
    graph.add_edge("export_searchable_pdf_final", "persist_record_and_index")
    graph.add_edge("persist_record_and_index", END)

    return graph

def _build_archive_main_graph() -> StateGraph:
    """构建档案整理主工作流图（接入层 + 4 层子图编排）。"""
    graph = StateGraph(ArchiveWorkflowState)

    # 注册节点
    graph.add_node("ingest_batch", node_ingest_batch)
    graph.add_node("load_policy_snapshot", node_load_policy_snapshot)
    graph.add_node("preprocess_pages", node_preprocess_pages)
    graph.add_node("run_ocr", node_run_ocr)
    graph.add_node("extract_page_features", node_extract_page_features)
    graph.add_node("analyze_page_relations", node_analyze_page_relations)
    graph.add_node("split_documents", node_split_documents)
    graph.add_node("assess_split_risk", node_assess_split_risk)
    graph.add_node("draft_subgraph", archive_draft_subgraph)
    graph.add_node("wait_for_review", node_wait_for_review)
    graph.add_node("resume_subgraph", archive_resume_subgraph)
    graph.add_node("final_subgraph", archive_final_subgraph)

    # 线性主链
    graph.add_edge(START, "ingest_batch")
    graph.add_edge("ingest_batch", "load_policy_snapshot")
    graph.add_edge("load_policy_snapshot", "preprocess_pages")
    graph.add_edge("preprocess_pages", "run_ocr")
    graph.add_edge("run_ocr", "extract_page_features")
    graph.add_edge("extract_page_features", "analyze_page_relations")
    graph.add_edge("analyze_page_relations", "split_documents")
    graph.add_edge("split_documents", "assess_split_risk")

    # 分件后进入 Draft 子图
    graph.add_conditional_edges(
        "assess_split_risk",
        route_after_assess_split,
        {"run_draft_subgraph": "draft_subgraph"},
    )

    graph.add_conditional_edges(
        "draft_subgraph",
        route_after_draft_subgraph,
        {"wait_for_review": "wait_for_review", "final_subgraph": "final_subgraph"},
    )

    # 审核等待与恢复：interrupt() 保证图在此处真正暂停；恢复后进入 Resume 子图
    graph.add_edge("wait_for_review", "resume_subgraph")
    graph.add_conditional_edges(
        "resume_subgraph",
        route_after_resume_subgraph,
        {
            "draft_subgraph": "draft_subgraph",
            "final_subgraph": "final_subgraph",
        },
    )

    graph.add_edge("final_subgraph", END)

    return graph


# ---------------------------------------------------------------------------
# 编译后的图（根据配置自动选择 memory/postgres/redis checkpointer）
# ---------------------------------------------------------------------------

_checkpointer = get_langgraph_checkpointer()

archive_draft_subgraph = _build_archive_draft_subgraph().compile()
archive_resume_subgraph = _build_archive_resume_subgraph().compile()
archive_final_subgraph = _build_archive_final_subgraph().compile()

archive_main_graph = _build_archive_main_graph().compile(checkpointer=cast(Any, _checkpointer))


# ---------------------------------------------------------------------------
# 公共入口函数
# ---------------------------------------------------------------------------

async def run_archive_workflow(
    *,
    task_id: str,
    batch_id: str,
    tenant_id: str = "default",
    policy_snapshot_id: str | None = None,
    pages: list[dict[str, Any]] | None = None,
    run_mode: str = "normal",
) -> dict[str, Any]:
    """
    启动档案整理工作流。
    返回最终 state 快照。
    """
    initial_state: ArchiveWorkflowState = {
        "task_id": task_id,
        "batch_id": batch_id,
        "tenant_id": tenant_id,
        "policy_snapshot_id": policy_snapshot_id,
        "run_mode": run_mode,
        "current_stage": "ingest_batch",
        "draft_status": "pending",
        "final_status": "pending",
        "review_status": "none",
        "pages": pages or [],
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
    }

    config: RunnableConfig = {"configurable": {"thread_id": task_id}}
    final_state = await archive_main_graph.ainvoke(initial_state, config=config)
    return final_state


async def resume_archive_workflow(
    *,
    task_id: str,
    batch_id: str,
    reason: str = "review_resolved",
    affected_scope: dict[str, Any] | None = None,
    resume_from_checkpoint: str | None = None,
    review_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    恢复被阻塞的工作流（审核完成后调用）。

    流程（Develop.md §15 + §18.5）：
    1. 若传入 review_result，使用失效传播服务自动推断 affected_scope
    2. 通过 aupdate_state 注入 review_status='resolved' 恢复信号
    3. ainvoke(None) 从 interrupt() 中断点继续执行

    Args:
        task_id:                LangGraph thread_id，与启动时相同
        batch_id:               批次 ID
        reason:                 恢复原因描述
        affected_scope:         显式指定失效范围（可选，优先于 review_result 推断）
        resume_from_checkpoint: 恢复节点（可选，用于记录）
        review_result:          审核结果 dict (result_type/affected_doc_ids 等)
    """
    # 若未显式传入 affected_scope，从 review_result 自动推断（Develop.md §18.5）
    if affected_scope is None and review_result:
        from app.domains.rework.invalidation_service import build_affected_scope_from_review
        affected_scope = build_affected_scope_from_review(review_result)

    config: RunnableConfig = {"configurable": {"thread_id": task_id}}

    # 通过 aupdate_state 注入恢复信号：node_wait_for_review 再次运行时检测
    # review_status='resolved'，跳过 interrupt()，工作流继续（Develop.md §15）
    await archive_main_graph.aupdate_state(
        config,
        {
            "review_status": "resolved",
            "blocked_reasons": [],
            "resume_reason": reason,
            "resume_from_checkpoint": resume_from_checkpoint,
            "affected_scope": affected_scope or {},
            "review_result": review_result or {},  # 供 node_resume_from_review 应用字段修正
        },
    )

    # ainvoke(None) 从最后检查点继续执行（即 interrupt() 被调用时的 wait_for_review 节点）
    final_state = await archive_main_graph.ainvoke(None, config=config)
    return final_state
