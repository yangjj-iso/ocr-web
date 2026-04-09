from __future__ import annotations

import logging
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.utils.image_sequence_pdf import (
    DEFAULT_SIMILARITY_THRESHOLD,
    PageFingerprint,
    compare_page_fingerprints,
    compute_phash,
    compute_text_similarity,
    decide_page_split,
    extract_text_signature,
)
from app.utils.image_sequence_pdf import _compute_layout_signature


logger = logging.getLogger(__name__)


STRONG_MERGE_SCORE = 0.72
AMBIGUOUS_SCORE_LOW = 0.46
HARD_SPLIT_SCORE = 0.34
JOIN_GAIN_BASELINE = 0.58
MAX_SEGMENT_LENGTH = 10
RELATED_TITLE_THRESHOLD = 0.15

CONTINUATION_FAMILIES = {"budget", "contract", "drawing", "minutes"}
ATTACHMENT_START_MARKERS = (
    "附件",
    "附表",
    "附图",
    "实施要求",
    "验收单",
    "确认单",
    "营业执照",
    "资质证书",
    "报价表",
)
END_OF_DOCUMENT_MARKERS = (
    "签字盖章后生效",
    "本合同及附件",
    "本协议及附件",
    "合同附件",
    "均具有同等法律效力",
    "可向甲方所在地人民法院提起诉讼",
)
CONTINUATION_PATTERNS = (
    re.compile(r"^\s*(?:第[一二三四五六七八九十百零\d]+条)"),
    re.compile(r"^\s*(?:[（(]?[一二三四五六七八九十百零\d]+[）).、])"),
    re.compile(r"^\s*(?:\d+[.)、])"),
)
ENTITY_PATTERNS = (
    re.compile(r"(?:甲方|乙方|丙方|项目名称|工程名称|项目编号|工程地点|户名|开户行)[:：]?\s*([^\n，。；;]{2,48})"),
    re.compile(r"([\u4e00-\u9fffA-Za-z0-9（）()·\-.]{4,48}(?:有限公司|集团|银行|支行|剧院|学校|学院|中心|事务所))"),
)
_PUNCT_PATTERN = re.compile(r"[\s,.;:!?\-_/\\，。；：！？（）()《》【】\[\]]+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(slots=True)
class SequencePage:
    task_id: int
    filename: str
    file_path: str
    prefix: str
    page_no: int
    created_at: datetime | None = None
    title_hint: str = ""
    full_text: str = ""
    title_norm: str = ""
    doc_no_norm: str = ""
    doc_no_prefix: str = ""
    responsible_norm: str = ""
    date_norm: str = ""
    document_family: str = ""
    rule_fields: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class BoundaryDecision:
    left_task_id: int
    right_task_id: int
    prefix: str
    left_page_no: int
    right_page_no: int
    same_document_score: float
    should_merge: bool
    is_ambiguous: bool
    strong_split: bool
    reason: str
    signals: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class BoundaryGroup:
    group_id: str
    prefix: str
    task_ids: list[int]
    filenames: list[str]
    start_page: int
    end_page: int
    confidence: float
    reasons: list[str]

    @property
    def page_count(self) -> int:
        return len(self.task_ids)

    @property
    def suggested_pdf_filename(self) -> str:
        return f"{self.prefix}-{self.start_page:03d}-{self.end_page:03d}.pdf"


@dataclass(slots=True)
class BoundaryResult:
    groups: list[BoundaryGroup]
    adjacent_decisions: list[BoundaryDecision]
    task_to_group: dict[int, str]
    group_meta: dict[str, dict[str, Any]]
    pair_meta: dict[tuple[int, int], dict[str, Any]]
    sequence_meta: dict[str, dict[str, Any]] = field(default_factory=dict)


def _normalize_similarity_threshold(value: int | None) -> int:
    if value is None:
        return DEFAULT_SIMILARITY_THRESHOLD
    try:
        return max(1, min(64, int(value)))
    except (TypeError, ValueError):
        return DEFAULT_SIMILARITY_THRESHOLD


@dataclass(slots=True)
class BoundaryFeedbackStats:
    same_count: int = 0
    different_count: int = 0

    @property
    def total(self) -> int:
        return self.same_count + self.different_count

    @property
    def same_ratio(self) -> float:
        if self.total <= 0:
            return 0.0
        return self.same_count / float(self.total)

    def to_bias(self, *, min_samples: int, max_abs: float) -> float:
        if self.total < min_samples:
            return 0.0
        raw_bias = (self.same_ratio - 0.5) * 2.0 * max_abs
        return round(max(-max_abs, min(max_abs, raw_bias)), 4)


@dataclass(slots=True)
class BoundaryFeedbackPriors:
    family_page_gap: dict[tuple[str, int], BoundaryFeedbackStats] = field(default_factory=dict)
    family_transition_gap: dict[tuple[str, str, int], BoundaryFeedbackStats] = field(default_factory=dict)
    page_gap: dict[int, BoundaryFeedbackStats] = field(default_factory=dict)


@dataclass(slots=True)
class _PreparedSequencePage:
    page: SequencePage
    text_signature: str
    entity_tokens: frozenset[str]
    starts_attachment: bool
    starts_continuation: bool
    ends_formal_closure: bool


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_text(value: Any) -> str:
    return _PUNCT_PATTERN.sub("", _coerce_text(value)).lower()


def _strip_html(value: str) -> str:
    return _HTML_TAG_RE.sub(" ", _coerce_text(value))


def _first_chars(value: str, length: int = 240) -> str:
    plain = re.sub(r"\s+", " ", _strip_html(value))
    return plain[:length].strip()


def _last_chars(value: str, length: int = 240) -> str:
    plain = re.sub(r"\s+", " ", _strip_html(value))
    return plain[-length:].strip()


def _starts_with_continuation(value: str) -> bool:
    text = _first_chars(value, 80)
    if not text:
        return False
    if any(pattern.search(text) for pattern in CONTINUATION_PATTERNS):
        return True
    continuation_keywords = (
        "验收合格",
        "剩余",
        "质保金",
        "付款方式",
        "若乙方",
        "甲方通过",
        "乙方应当",
        "权在",
        "会议强调",
        "会议要求",
        "会议传达",
        "出席",
        "请假",
    )
    return any(keyword in text for keyword in continuation_keywords)


def _starts_with_attachment(value: str) -> bool:
    text = _first_chars(value, 40)
    return any(text.startswith(marker) for marker in ATTACHMENT_START_MARKERS)


def _ends_formal_closure(value: str) -> bool:
    text = _last_chars(value, 240)
    return any(marker in text for marker in END_OF_DOCUMENT_MARKERS)


def _extract_entities(value: str) -> frozenset[str]:
    text = _strip_html(value)
    entities: set[str] = set()
    for pattern in ENTITY_PATTERNS:
        for match in pattern.findall(text):
            candidate = _normalize_text(match)[:48]
            if len(candidate) >= 4:
                entities.add(candidate)
    return frozenset(entities)


def _jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left or not right:
        return 0.0
    union = left | right
    if not union:
        return 0.0
    return round(len(left & right) / float(len(union)), 4)


def _field_overlap_score(left: SequencePage, right: SequencePage) -> float:
    matches: list[float] = []
    if left.doc_no_norm and right.doc_no_norm:
        matches.append(1.0 if left.doc_no_norm == right.doc_no_norm else 0.0)
    elif left.doc_no_prefix and right.doc_no_prefix:
        matches.append(1.0 if left.doc_no_prefix == right.doc_no_prefix else 0.0)

    if left.responsible_norm and right.responsible_norm:
        matches.append(1.0 if left.responsible_norm == right.responsible_norm else 0.0)

    if left.date_norm and right.date_norm:
        matches.append(1.0 if left.date_norm == right.date_norm else 0.0)

    if not matches:
        return 0.0
    return round(sum(matches) / len(matches), 4)


def _title_similarity(left: SequencePage, right: SequencePage) -> float:
    if not left.title_norm or not right.title_norm:
        return 0.0
    return round(SequenceMatcher(a=left.title_norm, b=right.title_norm).ratio(), 4)


def _build_fingerprint(prepared: _PreparedSequencePage, previous: PageFingerprint | None) -> PageFingerprint | None:
    image_path = Path(prepared.page.file_path)
    if not image_path.exists():
        return None
    layout_hash, row_profile, col_profile, ink_ratio = _compute_layout_signature(image_path)
    fingerprint = PageFingerprint(
        path=image_path,
        prefix=prepared.page.prefix,
        page_no=prepared.page.page_no,
        phash=compute_phash(image_path),
        layout_hash=layout_hash,
        ink_ratio=ink_ratio,
        row_profile=row_profile,
        col_profile=col_profile,
        text_signature=prepared.text_signature or extract_text_signature(image_path),
    )
    if previous is not None:
        comparison = compare_page_fingerprints(previous, fingerprint)
        fingerprint.distance_from_previous = comparison.phash_distance
        fingerprint.comparison_from_previous = comparison
    return fingerprint


def _prepare_pages(pages: list[SequencePage]) -> list[_PreparedSequencePage]:
    prepared_pages: list[_PreparedSequencePage] = []
    for page in pages:
        text = _strip_html(page.full_text or "")
        prepared_pages.append(
            _PreparedSequencePage(
                page=page,
                text_signature=_normalize_text(text)[:3000],
                entity_tokens=_extract_entities(" ".join([page.title_hint, text])),
                starts_attachment=_starts_with_attachment(" ".join([page.title_hint, text])),
                starts_continuation=_starts_with_continuation(text or page.title_hint),
                ends_formal_closure=_ends_formal_closure(text),
            )
        )
    return prepared_pages


def _visual_similarity_from_comparison(comparison, *, similarity_threshold: int) -> float:
    if comparison is None:
        return 0.5
    judged = decide_page_split(comparison, similarity_threshold=similarity_threshold)
    return round(max(0.0, min(1.0, 1.0 - float(judged.combined_change_score or 0.0))), 4)


def _build_feedback_adjustment(
    *,
    left_page: SequencePage,
    right_page: SequencePage,
    page_gap: int,
    feedback_priors: BoundaryFeedbackPriors | None,
) -> tuple[float, list[str], dict[str, Any]]:
    if feedback_priors is None:
        return 0.0, [], {}

    reasons: list[str] = []
    details: dict[str, Any] = {}
    adjustments: list[float] = []

    left_family = _coerce_text(left_page.document_family)
    right_family = _coerce_text(right_page.document_family)

    if left_family and right_family and left_family == right_family:
        stats = feedback_priors.family_page_gap.get((left_family, page_gap))
        if stats is not None:
            bias = stats.to_bias(min_samples=2, max_abs=0.16)
            if bias:
                adjustments.append(bias)
                details["family_page_gap"] = {
                    "family": left_family,
                    "page_gap": page_gap,
                    "same_count": stats.same_count,
                    "different_count": stats.different_count,
                    "bias": bias,
                }
                trend = "支持连续页合并" if bias > 0 else "提示应切为新文件"
                reasons.append(
                    f"历史人工样本对{left_family}类相邻页{trend}（{stats.same_count}/{stats.total}）"
                )
    elif left_family and right_family:
        stats = feedback_priors.family_transition_gap.get((left_family, right_family, page_gap))
        if stats is not None:
            bias = stats.to_bias(min_samples=2, max_abs=0.14)
            if bias:
                adjustments.append(bias)
                details["family_transition_gap"] = {
                    "left_family": left_family,
                    "right_family": right_family,
                    "page_gap": page_gap,
                    "same_count": stats.same_count,
                    "different_count": stats.different_count,
                    "bias": bias,
                }
                trend = "支持连续页合并" if bias > 0 else "提示应切为新文件"
                reasons.append(
                    f"历史人工样本对{left_family}->{right_family}切换{trend}（{stats.same_count}/{stats.total}）"
                )

    gap_stats = feedback_priors.page_gap.get(page_gap)
    if gap_stats is not None:
        gap_bias = gap_stats.to_bias(min_samples=4, max_abs=0.06)
        if gap_bias:
            adjustments.append(gap_bias)
            details["page_gap"] = {
                "page_gap": page_gap,
                "same_count": gap_stats.same_count,
                "different_count": gap_stats.different_count,
                "bias": gap_bias,
            }
            reasons.append(
                f"历史人工样本对页间距 {page_gap} 的边界倾向为 {'合并' if gap_bias > 0 else '切分'}（{gap_stats.same_count}/{gap_stats.total}）"
            )

    total_bias = round(max(-0.18, min(0.18, sum(adjustments))), 4)
    details["total_bias"] = total_bias
    return total_bias, reasons, details


def _score_boundary(
    left: _PreparedSequencePage,
    right: _PreparedSequencePage,
    *,
    comparison,
    similarity_threshold: int,
    feedback_priors: BoundaryFeedbackPriors | None = None,
) -> BoundaryDecision:
    left_page = left.page
    right_page = right.page
    page_gap = max(1, right_page.page_no - left_page.page_no)

    visual_similarity = _visual_similarity_from_comparison(comparison, similarity_threshold=similarity_threshold)
    text_similarity = compute_text_similarity(left.text_signature, right.text_signature) or 0.0
    title_similarity = _title_similarity(left_page, right_page)
    entity_overlap = _jaccard(left.entity_tokens, right.entity_tokens)
    field_overlap = _field_overlap_score(left_page, right_page)
    same_family = bool(left_page.document_family and left_page.document_family == right_page.document_family)
    same_continuation_family = same_family and left_page.document_family in CONTINUATION_FAMILIES
    weak_semantic_signal = (
        text_similarity <= 0.05
        and title_similarity <= 0.05
        and entity_overlap <= 0.05
        and field_overlap <= 0.05
    )

    score = (
        (visual_similarity * 0.30)
        + (text_similarity * 0.18)
        + (title_similarity * 0.12)
        + (entity_overlap * 0.16)
        + (field_overlap * 0.12)
        + (0.08 if same_family else 0.0)
    )

    bonuses: list[str] = []
    penalties: list[str] = []

    if same_continuation_family:
        score += 0.18
        bonuses.append(f"同属{left_page.document_family}类材料")

    if entity_overlap >= 0.25:
        score += 0.10
        bonuses.append("项目/主体信息连续")

    if page_gap == 1 and visual_similarity >= 0.92 and not right.starts_attachment:
        if weak_semantic_signal:
            score += 0.46
            bonuses.append("相邻页视觉版式高度一致")
        else:
            score += 0.10
            bonuses.append("相邻页视觉连续")

    if left.starts_continuation or right.starts_continuation:
        score += 0.16
        bonuses.append("续页语义明显")

    if title_similarity >= 0.62:
        score += 0.06
        bonuses.append("题名相近")
    elif same_continuation_family and page_gap == 1 and title_similarity >= RELATED_TITLE_THRESHOLD:
        score += 0.08
        bonuses.append("题名存在关联")

    if same_continuation_family and page_gap == 1 and not right.starts_attachment:
        score += 0.18
        bonuses.append("相邻页材料脉络连续")

    if page_gap > 1:
        gap_penalty = min(0.24, (page_gap - 1) * 0.12)
        score -= gap_penalty
        penalties.append("页码存在跳跃")

    if left_page.document_family and right_page.document_family and left_page.document_family != right_page.document_family:
        score -= 0.22
        penalties.append("材料类型切换明显")

    if right.starts_attachment and left.ends_formal_closure:
        score -= 0.32
        penalties.append("前页已结束且后页为附件/新表单起始")

    if right.starts_attachment and not same_family:
        score -= 0.18
        penalties.append("后页出现附件或新表单起始")

    if (
        visual_similarity <= 0.18
        and entity_overlap <= 0.05
        and text_similarity <= 0.05
        and not (same_continuation_family and page_gap == 1)
    ):
        score -= 0.12
        penalties.append("视觉与文本都缺少连续信号")

    feedback_bias, feedback_reasons, feedback_details = _build_feedback_adjustment(
        left_page=left_page,
        right_page=right_page,
        page_gap=page_gap,
        feedback_priors=feedback_priors,
    )
    if feedback_bias:
        score += feedback_bias
        if feedback_bias > 0:
            bonuses.extend(feedback_reasons)
        else:
            penalties.extend(feedback_reasons)

    score = round(max(0.02, min(0.98, score)), 4)
    strong_split = score <= HARD_SPLIT_SCORE or ("前页已结束且后页为附件/新表单起始" in penalties)
    should_merge = score >= STRONG_MERGE_SCORE
    is_ambiguous = not should_merge and score >= AMBIGUOUS_SCORE_LOW

    reason_parts: list[str] = []
    if bonuses:
        reason_parts.append("、".join(bonuses))
    if penalties:
        reason_parts.append("、".join(penalties))
    if not reason_parts:
        reason_parts.append("连续性信号不足")
    reason_parts.append(f"same_doc_score={score:.2f}")

    return BoundaryDecision(
        left_task_id=left_page.task_id,
        right_task_id=right_page.task_id,
        prefix=left_page.prefix,
        left_page_no=left_page.page_no,
        right_page_no=right_page.page_no,
        same_document_score=score,
        should_merge=should_merge,
        is_ambiguous=is_ambiguous,
        strong_split=strong_split,
        reason="；".join(reason_parts),
        signals={
            "visual_similarity": visual_similarity,
            "text_similarity": text_similarity,
            "title_similarity": title_similarity,
            "entity_overlap": entity_overlap,
            "field_overlap": field_overlap,
            "same_family": same_family,
            "starts_attachment": right.starts_attachment,
            "ends_formal_closure": left.ends_formal_closure,
            "starts_continuation": bool(left.starts_continuation or right.starts_continuation),
            "page_gap": page_gap,
            "feedback_bias": feedback_bias,
            "feedback_details": feedback_details,
        },
    )


def _smooth_adjacent_decisions(
    pages: list[_PreparedSequencePage],
    decisions: list[BoundaryDecision],
) -> list[BoundaryDecision]:
    if len(decisions) < 3:
        return decisions

    smoothed: list[BoundaryDecision] = []
    for index, decision in enumerate(decisions):
        updated = BoundaryDecision(
            left_task_id=decision.left_task_id,
            right_task_id=decision.right_task_id,
            prefix=decision.prefix,
            left_page_no=decision.left_page_no,
            right_page_no=decision.right_page_no,
            same_document_score=decision.same_document_score,
            should_merge=decision.should_merge,
            is_ambiguous=decision.is_ambiguous,
            strong_split=decision.strong_split,
            reason=decision.reason,
            signals=dict(decision.signals),
        )
        if 0 < index < len(decisions) - 1:
            previous_score = decisions[index - 1].same_document_score
            next_score = decisions[index + 1].same_document_score
            left_family = pages[index - 1].page.document_family
            middle_left_family = pages[index].page.document_family
            middle_right_family = pages[index + 1].page.document_family
            if (
                updated.same_document_score < 0.58
                and previous_score >= 0.78
                and next_score >= 0.78
                and left_family
                and left_family == middle_left_family == middle_right_family
                and not updated.strong_split
            ):
                updated.same_document_score = round(min(0.79, updated.same_document_score + 0.16), 4)
                updated.should_merge = updated.same_document_score >= STRONG_MERGE_SCORE
                updated.is_ambiguous = not updated.should_merge and updated.same_document_score >= AMBIGUOUS_SCORE_LOW
                updated.reason = f"{updated.reason}；前后页连续上下文补强"
        smoothed.append(updated)
    return smoothed


def _segment_gain(
    pages: list[_PreparedSequencePage],
    decisions: list[BoundaryDecision],
    start: int,
    end: int,
) -> float:
    if start == end:
        return 0.0

    relevant = decisions[start:end]
    gain = sum(decision.same_document_score - JOIN_GAIN_BASELINE for decision in relevant)
    segment_length = end - start + 1

    families = [prepared.page.document_family for prepared in pages[start : end + 1] if prepared.page.document_family]
    if len(families) >= 2:
        family_counter = Counter(families)
        dominant_family, dominant_count = family_counter.most_common(1)[0]
        if len(family_counter) == 1 and dominant_family in CONTINUATION_FAMILIES:
            gain += min(0.30, 0.05 * (segment_length - 1))
        elif dominant_count < len(families):
            gain -= 0.18

    shared_entities = pages[start].entity_tokens & pages[end].entity_tokens
    if len(shared_entities) >= 1:
        gain += 0.08

    if all(
        pages[index + 1].page.page_no - pages[index].page.page_no == 1
        for index in range(start, end)
    ):
        gain += 0.05

    for decision in relevant:
        if decision.strong_split:
            gain -= 0.32

    for offset in range(start + 1, end + 1):
        if pages[offset].starts_attachment and pages[offset - 1].ends_formal_closure:
            gain -= 0.35

    return round(gain, 4)


def _build_groups_for_sequence(
    prepared_pages: list[_PreparedSequencePage],
    decisions: list[BoundaryDecision],
) -> list[list[_PreparedSequencePage]]:
    if not prepared_pages:
        return []

    page_count = len(prepared_pages)
    best_scores = [-10**9] * (page_count + 1)
    best_starts = [0] * (page_count + 1)
    best_scores[0] = 0.0

    for end in range(1, page_count + 1):
        best_score = -10**9
        best_start = end - 1
        lower_bound = max(0, end - MAX_SEGMENT_LENGTH)
        for start in range(lower_bound, end):
            candidate = best_scores[start] + _segment_gain(prepared_pages, decisions, start, end - 1)
            if candidate > best_score:
                best_score = candidate
                best_start = start
        best_scores[end] = best_score
        best_starts[end] = best_start

    groups: list[list[_PreparedSequencePage]] = []
    cursor = page_count
    while cursor > 0:
        start = best_starts[cursor]
        groups.append(prepared_pages[start:cursor])
        cursor = start
    groups.reverse()
    return groups


def _pair_key(left_task_id: int, right_task_id: int) -> tuple[int, int]:
    return (left_task_id, right_task_id) if left_task_id <= right_task_id else (right_task_id, left_task_id)


def _group_reasons(group_pages: list[_PreparedSequencePage], pair_meta: dict[tuple[int, int], dict[str, Any]]) -> list[str]:
    reasons: list[str] = []
    for index in range(len(group_pages) - 1):
        left = group_pages[index].page
        right = group_pages[index + 1].page
        meta = pair_meta.get(_pair_key(left.task_id, right.task_id))
        if not meta:
            continue
        reason = _coerce_text(meta.get("reason"))
        if reason and reason not in reasons:
            reasons.append(reason)
    return reasons or ["边界引擎判定为同一原始文件。"]


def build_boundary_result(
    pages: list[SequencePage],
    *,
    feedback_priors: BoundaryFeedbackPriors | None = None,
    similarity_threshold: int | None = None,
) -> BoundaryResult:
    prepared_sequences: dict[str, list[_PreparedSequencePage]] = defaultdict(list)
    pair_meta: dict[tuple[int, int], dict[str, Any]] = {}
    adjacent_decisions: list[BoundaryDecision] = []
    groups: list[BoundaryGroup] = []
    task_to_group: dict[int, str] = {}
    group_meta: dict[str, dict[str, Any]] = {}
    sequence_meta: dict[str, dict[str, Any]] = {}

    for page in pages:
        if not page.prefix or page.page_no is None:
            continue
        prepared_sequences[page.prefix].append(page)

    group_counter = 0
    for prefix in sorted(prepared_sequences):
        sequence_pages = sorted(
            _prepare_pages(prepared_sequences[prefix]),
            key=lambda item: (item.page.page_no, item.page.created_at or datetime.min, item.page.task_id),
        )
        if not sequence_pages:
            continue

        previous_fingerprint: PageFingerprint | None = None
        fingerprints: list[PageFingerprint] = []
        fingerprint_by_task_id: dict[int, PageFingerprint] = {}
        for prepared in sequence_pages:
            try:
                fingerprint = _build_fingerprint(prepared, previous_fingerprint)
            except Exception:  # noqa: BLE001
                logger.debug("Failed to build fingerprint for %s", prepared.page.file_path, exc_info=True)
                fingerprint = None
            if fingerprint is not None:
                fingerprints.append(fingerprint)
                fingerprint_by_task_id[prepared.page.task_id] = fingerprint
                previous_fingerprint = fingerprint

        distances = [
            int(fingerprint.distance_from_previous)
            for fingerprint in fingerprints[1:]
            if fingerprint.distance_from_previous is not None
        ]
        recommended_threshold = 12 if not distances else max(8, min(18, sum(distances) // len(distances) + 2))
        if len(fingerprints) >= 2:
            try:
                recommended_threshold = suggest_similarity_threshold(fingerprints)
            except Exception:  # noqa: BLE001
                logger.debug("Failed to auto-suggest similarity threshold for %s", prefix, exc_info=True)
        effective_threshold = _normalize_similarity_threshold(similarity_threshold)
        sequence_meta[prefix] = {
            "page_count": len(sequence_pages),
            "applied_similarity_threshold": effective_threshold,
            "recommended_similarity_threshold": recommended_threshold,
            "distance_sample_count": len(distances),
        }

        sequence_decisions: list[BoundaryDecision] = []
        for index in range(len(sequence_pages) - 1):
            left = sequence_pages[index]
            right = sequence_pages[index + 1]
            left_fingerprint = fingerprint_by_task_id.get(left.page.task_id)
            right_fingerprint = fingerprint_by_task_id.get(right.page.task_id)
            comparison = None
            if left_fingerprint is not None and right_fingerprint is not None:
                comparison = right_fingerprint.comparison_from_previous
                if comparison is None:
                    comparison = compare_page_fingerprints(left_fingerprint, right_fingerprint)
            decision = _score_boundary(
                left,
                right,
                comparison=comparison,
                similarity_threshold=effective_threshold,
                feedback_priors=feedback_priors,
            )
            sequence_decisions.append(decision)

        sequence_decisions = _smooth_adjacent_decisions(sequence_pages, sequence_decisions)
        for decision in sequence_decisions:
            adjacent_decisions.append(decision)
            pair_meta[_pair_key(decision.left_task_id, decision.right_task_id)] = {
                "same_document_score": decision.same_document_score,
                "should_merge": decision.should_merge,
                "is_ambiguous": decision.is_ambiguous,
                "strong_split": decision.strong_split,
                "reason": decision.reason,
                "signals": decision.signals,
            }

        sequence_groups = _build_groups_for_sequence(sequence_pages, sequence_decisions)
        for member_pages in sequence_groups:
            group_counter += 1
            group_id = f"{prefix}#boundary-{group_counter}"
            task_ids = [member.page.task_id for member in member_pages]
            filenames = [member.page.filename for member in member_pages]
            reasons = _group_reasons(member_pages, pair_meta)
            if len(member_pages) == 1:
                confidence = 1.0
            else:
                internal_scores = []
                for index in range(len(member_pages) - 1):
                    pair = _pair_key(member_pages[index].page.task_id, member_pages[index + 1].page.task_id)
                    internal_scores.append(float(pair_meta.get(pair, {}).get("same_document_score", 0.72)))
                confidence = round(sum(internal_scores) / max(1, len(internal_scores)), 4)
            group = BoundaryGroup(
                group_id=group_id,
                prefix=prefix,
                task_ids=task_ids,
                filenames=filenames,
                start_page=member_pages[0].page.page_no,
                end_page=member_pages[-1].page.page_no,
                confidence=confidence,
                reasons=reasons,
            )
            groups.append(group)
            group_meta[group_id] = {
                "confidence": confidence,
                "reason": "；".join(reasons),
                "task_ids": task_ids,
                "start_page": group.start_page,
                "end_page": group.end_page,
                "page_count": group.page_count,
                "suggested_pdf_filename": group.suggested_pdf_filename,
                "applied_similarity_threshold": effective_threshold,
                "recommended_similarity_threshold": recommended_threshold,
            }
            for task_id in task_ids:
                task_to_group[task_id] = group_id

    return BoundaryResult(
        groups=groups,
        adjacent_decisions=adjacent_decisions,
        task_to_group=task_to_group,
        group_meta=group_meta,
        pair_meta=pair_meta,
        sequence_meta=sequence_meta,
    )


__all__ = [
    "AMBIGUOUS_SCORE_LOW",
    "BoundaryDecision",
    "BoundaryFeedbackPriors",
    "BoundaryFeedbackStats",
    "BoundaryGroup",
    "BoundaryResult",
    "HARD_SPLIT_SCORE",
    "STRONG_MERGE_SCORE",
    "SequencePage",
    "build_boundary_result",
]
