"""
失效传播服务（Invalidation Service）— Develop.md §18.5。

当返工审核改变了分件边界、字段或排序时，
使已计算的下游结果失效，触发局部重跑。

三类失效场景：
    1. page_reassignment   — 页面归属改变（影响最广）
    2. field_change        — 字段著录修改
    3. order_change        — 排序调整

每种场景返回 AffectedScope dict，供 resume_archive_workflow 使用。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 场景一：页面归属改变（Develop.md §18.5 — page_reassignment）
# ---------------------------------------------------------------------------

def invalidate_for_page_reassignment(
    affected_doc_ids: list[str],
) -> dict[str, Any]:
    """
    页面重新归属影响最多层：
      - 元数据著录（page_count / title / date / doc_no 均需重提取）
      - 排序依据改变
      - 编号需重分配
      - 卷内目录需重生成
      - searchable PDF 需重建

    返回 AffectedScope dict。
    """
    logger.info(
        "invalidate_for_page_reassignment: doc_ids=%s → all downstream invalidated",
        affected_doc_ids,
    )
    return {
        "doc_ids": affected_doc_ids,
        "invalidate_metadata": True,
        "invalidate_sort": True,
        "invalidate_numbering": True,
        "invalidate_catalog": True,
        "invalidate_pdf": True,
    }


# ---------------------------------------------------------------------------
# 场景二：字段修改（Develop.md §18.5 — field_change）
# ---------------------------------------------------------------------------

def invalidate_for_field_change(
    affected_doc_ids: list[str],
    changed_fields: list[str] | None = None,
) -> dict[str, Any]:
    """
    字段著录修改只影响卷内目录/索引/导出，不影响排序/编号。

    changed_fields: 修改的字段名列表，如 ["title", "date"]。
    Returns AffectedScope dict.
    """
    logger.info(
        "invalidate_for_field_change: doc_ids=%s fields=%s → catalog/index/export invalidated",
        affected_doc_ids,
        changed_fields,
    )
    return {
        "doc_ids": affected_doc_ids,
        "changed_fields": changed_fields or [],
        "invalidate_metadata": False,   # 字段已由审核人直接赋值，无需重提取
        "invalidate_sort": False,
        "invalidate_numbering": False,
        "invalidate_catalog": True,
        "invalidate_pdf": True,
    }


# ---------------------------------------------------------------------------
# 场景三：排序调整（Develop.md §18.5 — order_change）
# ---------------------------------------------------------------------------

def invalidate_for_order_change(
    from_order_index: int,
) -> dict[str, Any]:
    """
    排序调整只影响从 from_order_index 开始的编号与目录，不影响页面内容/元数据。

    Returns AffectedScope dict.
    """
    logger.info(
        "invalidate_for_order_change: from_index=%d → numbering/catalog/pdf invalidated",
        from_order_index,
    )
    return {
        "renumber_from_order_index": from_order_index,
        "invalidate_metadata": False,
        "invalidate_sort": False,
        "invalidate_numbering": True,
        "invalidate_catalog": True,
        "invalidate_pdf": True,
    }


# ---------------------------------------------------------------------------
# 根据 review_result 自动推断失效范围
# ---------------------------------------------------------------------------

def build_affected_scope_from_review(
    review_result: dict[str, Any],
) -> dict[str, Any]:
    """
    根据审核结果自动推断 AffectedScope。

    review_result 结构（Develop.md §18.3）：
        {
            "result_type": "boundary_confirmed" | "boundary_rejected" |
                           "field_corrected" | "order_adjusted",
            "affected_doc_ids": [...],
            "changed_fields": [...],         # field_corrected 时填充
            "from_order_index": int,         # order_adjusted 时填充
        }
    """
    result_type = review_result.get("result_type", "")
    affected_doc_ids: list[str] = review_result.get("affected_doc_ids") or []

    if result_type == "boundary_rejected":
        # 边界被否决 → 重做页面分配，影响最广
        return invalidate_for_page_reassignment(affected_doc_ids)

    if result_type == "field_corrected":
        changed_fields: list[str] = review_result.get("changed_fields") or []
        return invalidate_for_field_change(affected_doc_ids, changed_fields)

    if result_type == "order_adjusted":
        from_idx: int = review_result.get("from_order_index", 0)
        return invalidate_for_order_change(from_idx)

    # boundary_confirmed 或未知类型 → 无需失效
    logger.info("build_affected_scope_from_review: result_type=%s → no invalidation", result_type)
    return {}


# ---------------------------------------------------------------------------
# 根据 AffectedScope 决定从哪个节点恢复（Develop.md §18.5）
# ---------------------------------------------------------------------------

_STAGE_ORDER = [
    "split_documents",
    "assess_split_risk",
    "run_draft_subgraph",
    "create_review_tasks",
    "gate_final_subgraph",
    "sort_documents_final",
    "assign_archive_numbers",
    "extract_metadata_final",
    "build_catalog_final",
    "export_searchable_pdf_final",
    "persist_record_and_index",
]


def earliest_invalidated_stage(scope: dict[str, Any]) -> str:
    """
    根据 AffectedScope 推断需要从哪个 LangGraph 节点重新开始执行。

    返回节点名称（与 archive_workflow.py 中的节点 key 一致）。
    """
    if not scope:
        return "sort_documents_final"

    if scope.get("invalidate_metadata") or scope.get("invalidate_sort"):
        # 元数据或排序失效 → 从 Draft 轨重跑
        return "run_draft_subgraph"

    if scope.get("invalidate_numbering"):
        # 编号失效 → Final 轨排序后重跑
        return "sort_documents_final"

    if scope.get("invalidate_catalog") or scope.get("invalidate_pdf"):
        # 只目录/PDF 失效 → 直接跑 catalog
        return "build_catalog_final"

    return "sort_documents_final"
