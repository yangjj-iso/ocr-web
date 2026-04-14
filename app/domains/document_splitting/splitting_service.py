"""
Document Splitting Domain — 自动分件领域服务。

核心能力：
- 基于页面关系分析、OCR 文本、版面特征，识别件边界
- 生成初步件集合（draft doc schema）
- 评估分件置信度和风险点
- 输出需要人工审核的边界候选

遵循 Develop.md 阶段 4：自动分件
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class BoundaryCandidate:
    """件边界候选：相邻两页之间可能的新件开始。"""
    left_page_index: int
    right_page_index: int
    is_boundary: bool
    confidence: float
    reason: str
    signals: dict[str, Any] = field(default_factory=dict)
    needs_review: bool = False


@dataclass
class DraftDoc:
    """草稿件：分件后的初步件对象。"""
    tmp_doc_id: str
    batch_id: str
    start_page: int        # 0-based
    end_page: int          # 0-based inclusive
    page_ids: list[str]
    confidence: float
    doc_type_guess: str    # correspondence/report/form/other
    boundary_reason: str
    status: str = "draft"  # draft/review_required/confirmed


def _is_strong_boundary_signal(page_a: dict[str, Any], page_b: dict[str, Any]) -> tuple[bool, str, float]:
    """
    判断两页之间是否存在强边界信号。
    返回 (is_boundary, reason, confidence)。
    """
    reasons = []
    confidence = 0.0

    # 文号变化是最强信号
    doc_nos_a = set((page_a.get("candidates") or {}).get("doc_nos") or [])
    doc_nos_b = set((page_b.get("candidates") or {}).get("doc_nos") or [])
    if doc_nos_a and doc_nos_b and doc_nos_a.isdisjoint(doc_nos_b):
        reasons.append("doc_no_changed")
        confidence += 0.50

    # 右页首页得分高
    first_page_score_b = page_b.get("first_page_score", 0.0)
    if first_page_score_b >= 0.65:
        reasons.append(f"first_page_score={first_page_score_b:.2f}")
        confidence += 0.30

    # pHash 相似度低（两页视觉差异大，通常意味着新文件）
    phash_similarity = page_b.get("duplicate_score", 0.0)
    if phash_similarity < 0.15:
        confidence += 0.10

    # 页面关系分析明确标记为新件
    relation = (page_b.get("page_relation_json") or {})
    if relation.get("is_new_doc_start"):
        reasons.append("relation_analysis_new_doc")
        confidence += 0.30

    is_boundary = confidence >= 0.45
    return is_boundary, "; ".join(reasons) if reasons else "no_signal", min(confidence, 1.0)


def detect_boundaries(pages: list[dict[str, Any]]) -> list[BoundaryCandidate]:
    """
    对整卷页面逐对分析，生成边界候选列表。
    pages: 按 page_index 排序的 page schema 列表。
    """
    candidates: list[BoundaryCandidate] = []
    if len(pages) < 2:
        return candidates

    for i in range(len(pages) - 1):
        pa = pages[i]
        pb = pages[i + 1]
        is_boundary, reason, confidence = _is_strong_boundary_signal(pa, pb)

        # 置信度在 0.3–0.6 之间认为模糊，需要人工审核
        needs_review = 0.25 <= confidence < 0.60 or (is_boundary and confidence < 0.70)

        candidates.append(
            BoundaryCandidate(
                left_page_index=pa.get("page_index", i),
                right_page_index=pb.get("page_index", i + 1),
                is_boundary=is_boundary,
                confidence=confidence,
                reason=reason,
                signals={
                    "first_page_score_right": pb.get("first_page_score", 0.0),
                    "duplicate_score_right": pb.get("duplicate_score", 0.0),
                    "doc_nos_left": list((pa.get("candidates") or {}).get("doc_nos") or []),
                    "doc_nos_right": list((pb.get("candidates") or {}).get("doc_nos") or []),
                },
                needs_review=needs_review,
            )
        )
    return candidates


def split_into_draft_docs(
    pages: list[dict[str, Any]],
    boundaries: list[BoundaryCandidate],
    batch_id: str,
) -> list[DraftDoc]:
    """
    根据边界候选，将页面序列拆分为草稿件列表。
    """
    if not pages:
        return []

    # 确定分割点（is_boundary=True 的右侧页面索引）
    split_points: set[int] = {0}  # 第一页总是一件的开始
    ambiguous_splits: set[int] = set()

    for bc in boundaries:
        if bc.is_boundary:
            split_points.add(bc.right_page_index)
            if bc.needs_review:
                ambiguous_splits.add(bc.right_page_index)

    split_sorted = sorted(split_points)
    page_map = {p["page_index"]: p for p in pages}
    all_indices = sorted(page_map.keys())

    docs: list[DraftDoc] = []
    for i, start_idx in enumerate(split_sorted):
        end_idx = split_sorted[i + 1] - 1 if i + 1 < len(split_sorted) else all_indices[-1]

        doc_pages = [page_map[idx] for idx in all_indices if start_idx <= idx <= end_idx]
        page_ids = [p["page_id"] for p in doc_pages]

        # 组合置信度：取该件各页首页得分和边界得分的加权均值
        boundary_conf = next(
            (bc.confidence for bc in boundaries if bc.right_page_index == start_idx),
            0.8,  # 第一件没有前置边界，给予高置信度
        )
        avg_first_page = sum(p.get("first_page_score", 0.5) for p in doc_pages) / max(len(doc_pages), 1)
        confidence = round(0.6 * boundary_conf + 0.4 * avg_first_page, 3)

        needs_review_flag = start_idx in ambiguous_splits
        status = "review_required" if needs_review_flag else "draft"

        docs.append(
            DraftDoc(
                tmp_doc_id=f"tmp_{batch_id}_{uuid4().hex[:8]}",
                batch_id=batch_id,
                start_page=start_idx,
                end_page=end_idx,
                page_ids=page_ids,
                confidence=confidence,
                doc_type_guess="correspondence",
                boundary_reason=(
                    next(
                        (bc.reason for bc in boundaries if bc.right_page_index == start_idx),
                        "first_doc_in_batch",
                    )
                ),
                status=status,
            )
        )

    return docs


def assess_split_risk(docs: list[DraftDoc]) -> dict[str, Any]:
    """
    评估分件整体风险，决定是否需要阻塞 Final 轨进入人工审核。
    返回风险摘要，供工作流路由条件使用。
    """
    review_required = [d for d in docs if d.status == "review_required"]
    low_confidence = [d for d in docs if d.confidence < 0.55]

    needs_block = len(review_required) > 0 or len(low_confidence) > 0
    block_reason = []
    if review_required:
        block_reason.append(f"{len(review_required)} docs need boundary review")
    if low_confidence:
        block_reason.append(f"{len(low_confidence)} docs have low confidence (<0.55)")

    return {
        "total_docs": len(docs),
        "review_required_count": len(review_required),
        "low_confidence_count": len(low_confidence),
        "needs_final_block": needs_block,
        "block_reasons": block_reason,
        "review_doc_ids": [d.tmp_doc_id for d in review_required],
    }


def to_doc_schema(doc: DraftDoc) -> dict[str, Any]:
    """将 DraftDoc 转换为可序列化的 schema 字典。"""
    return {
        "tmp_doc_id": doc.tmp_doc_id,
        "batch_id": doc.batch_id,
        "start_page": doc.start_page,
        "end_page": doc.end_page,
        "page_ids": doc.page_ids,
        "confidence": doc.confidence,
        "doc_type_guess": doc.doc_type_guess,
        "boundary_reason": doc.boundary_reason,
        "status": doc.status,
    }
