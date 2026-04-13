"""
Quality Domain — 档案整理质量评分服务。

实现 Develop.md §19.1 的四维置信度 + final_readiness_score 加权公式：

    final_readiness_score =
        0.30 * ocr_confidence
      + 0.35 * boundary_confidence
      + 0.20 * metadata_confidence
      + 0.15 * rule_match_score

每维含义：
  ocr_confidence       — 页面 OCR 结果整体可信度（基于文字密度、字符混乱度）
  boundary_confidence  — 分件边界置信度（来自 splitting_service 的最低件置信度）
  metadata_confidence  — 著录字段置信度（候选是否唯一、命中规则字段数占比）
  rule_match_score     — 政策规则匹配分（分件规则、排序规则命中率）
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 权重（Develop.md §19.1）
# ---------------------------------------------------------------------------

_W_OCR = 0.30
_W_BOUNDARY = 0.35
_W_METADATA = 0.20
_W_RULE = 0.15


# ---------------------------------------------------------------------------
# 单项置信度计算
# ---------------------------------------------------------------------------

def compute_ocr_confidence(pages: list[dict[str, Any]]) -> float:
    """
    基于全卷页面的 OCR 结果估算整体文字质量置信度。

    策略：
    - 空文本页降低得分
    - OCR 文本长度过短（< 20字符）视为低质量
    - 有候选字段（日期/文号/标题）的页面加分
    """
    if not pages:
        return 0.0

    total = len(pages)
    ok_count = 0
    for page in pages:
        text = (page.get("ocr_text") or "").strip()
        if len(text) < 10:
            continue
        candidates = page.get("candidates") or {}
        has_candidates = bool(
            candidates.get("dates") or candidates.get("doc_nos") or candidates.get("title_lines")
        )
        if len(text) >= 20 or has_candidates:
            ok_count += 1

    return round(ok_count / total, 4)


def compute_boundary_confidence(draft_docs: list[dict[str, Any]]) -> float:
    """
    基于草稿件集合的分件置信度。

    策略：
    - 取全部件置信度的加权均值（低置信件更影响结果）
    - 有 review_required 件则显著拉低分数
    """
    if not draft_docs:
        return 0.0

    confidences = [d.get("confidence", 0.5) for d in draft_docs]
    avg = sum(confidences) / len(confidences)

    # 每出现一个 review_required 件，整体扣 0.1
    review_count = sum(1 for d in draft_docs if d.get("status") == "review_required")
    penalty = min(review_count * 0.1, 0.4)

    return round(max(0.0, avg - penalty), 4)


def compute_metadata_confidence(draft_docs: list[dict[str, Any]]) -> float:
    """
    基于草稿件集合的著录字段置信度。

    策略：
    - 对每件检查 metadata_json 中关键字段（title/date/doc_no）是否存在
    - 命中率 = 有字段的件数 / 总件数
    """
    if not draft_docs:
        return 0.0

    key_fields = ("title", "date", "doc_no")
    hit = 0
    for doc in draft_docs:
        meta = doc.get("metadata_json") or {}
        if any(meta.get(f) for f in key_fields):
            hit += 1

    return round(hit / len(draft_docs), 4)


def compute_rule_match_score(
    draft_docs: list[dict[str, Any]],
    policy_rules: dict[str, Any],
) -> float:
    """
    规则匹配分：分件规则、排序规则命中率。

    策略：
    - 检查每件是否命中预设的必要字段要求
    - policy_rules.required_fields 优先
    - 无规则配置时默认返回 0.75（中等）
    """
    if not draft_docs:
        return 0.0

    required_fields: list[str] = (policy_rules or {}).get("required_fields", [])
    if not required_fields:
        return 0.75  # 无规则配置，默认中等

    total_checks = len(draft_docs) * len(required_fields)
    if total_checks == 0:
        return 0.75

    hit = 0
    for doc in draft_docs:
        meta = doc.get("metadata_json") or {}
        for field in required_fields:
            if meta.get(field):
                hit += 1

    return round(hit / total_checks, 4)


# ---------------------------------------------------------------------------
# 主评分函数（Develop.md §19.1 加权公式）
# ---------------------------------------------------------------------------

def compute_quality_scores(
    pages: list[dict[str, Any]],
    draft_docs: list[dict[str, Any]],
    policy_rules: dict[str, Any] | None = None,
) -> dict[str, float]:
    """
    计算全套质量分，返回 quality_scores_json 结构。

    返回：
        {
            "ocr_confidence": float,
            "boundary_confidence": float,
            "metadata_confidence": float,
            "rule_match_score": float,
            "final_readiness_score": float,
        }
    """
    ocr_conf = compute_ocr_confidence(pages)
    boundary_conf = compute_boundary_confidence(draft_docs)
    metadata_conf = compute_metadata_confidence(draft_docs)
    rule_score = compute_rule_match_score(draft_docs, policy_rules or {})

    final_readiness = round(
        _W_OCR * ocr_conf
        + _W_BOUNDARY * boundary_conf
        + _W_METADATA * metadata_conf
        + _W_RULE * rule_score,
        4,
    )

    scores = {
        "ocr_confidence": ocr_conf,
        "boundary_confidence": boundary_conf,
        "metadata_confidence": metadata_conf,
        "rule_match_score": rule_score,
        "final_readiness_score": final_readiness,
    }

    logger.debug("quality_scores: %s", scores)
    return scores


def is_ready_for_final(quality_scores: dict[str, float], threshold: float = 0.60) -> bool:
    """
    判断整卷是否达到 Final 轨放行阈值。

    默认阈值 0.60 (可通过 policy_rules.final_readiness_threshold 覆盖)。
    """
    return quality_scores.get("final_readiness_score", 0.0) >= threshold
