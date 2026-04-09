import asyncio
import logging
import re
from collections import defaultdict
from dataclasses import dataclass
from copy import deepcopy
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_cache import cache_delete, cache_get, cache_set
from app.db.models import ArchiveRecord, OCRTask
from app.services.document_boundary_feedback_service import get_batch_boundary_truth
from app.services.document_boundary_feedback_learning import load_boundary_feedback_priors
from app.services.document_boundary_store import load_boundary_analysis, save_boundary_analysis
from app.services.document_boundary_engine import (
    BoundaryResult,
    SequencePage,
    build_boundary_result,
)
from app.services.document_family import (
    MULTI_LAYOUT_CONTINUATION_FAMILIES,
    coerce_text as shared_coerce_text,
    document_family_label,
    infer_document_family_from_text,
    infer_title_hint,
)
from app.services.excel_export import extract_fields
from app.services.llm_field_extraction_service import (
    ARCHIVE_FIELDS,
    MiniMaxServiceError,
    build_agreement_summary,
    call_minimax_same_document_judgement,
    compare_rule_and_llm_fields_for_content,
)
from app.utils.image_sequence_pdf import (
    DEFAULT_SIMILARITY_THRESHOLD,
    DEFAULT_TEXT_SIMILARITY_THRESHOLD,
    PDFGroup,
    PageFingerprint,
    compare_page_fingerprints,
    compute_phash,
    group_pages_by_similarity,
    parse_page_file,
    save_group_as_pdf,
    suggest_similarity_threshold,
)
from app.utils.image_sequence_pdf import _compute_layout_signature
from config import (
    BOUNDARY_GROUP_PDF_OUTPUT_DIRNAME,
    BOUNDARY_SIMILARITY_THRESHOLD,
    MINIMAX_BATCH_CONCURRENCY,
)

logger = logging.getLogger(__name__)


SAME_DOCUMENT_CONFIDENCE_THRESHOLD = 0.90
ADJACENT_PAGE_SAME_DOCUMENT_CONFIDENCE_THRESHOLD = 0.82
TITLE_STRONG_MATCH_THRESHOLD = 0.97
TITLE_HINT_THRESHOLD = 0.62
FILENAME_HINT_THRESHOLD = 0.78
SERIES_NEIGHBOR_DISTANCE = 2
NEARBY_CANDIDATE_DISTANCE = 1
MISSING_TEXT_REASON = "Task full_text is empty."
MISSING_TEXT_WITHOUT_VISUAL_REASON = "Task full_text is empty and cannot participate in visual grouping."
NOT_DONE_REASON = "Task is not finished yet."
MERGE_CACHE_PREFIX = "batch_ai_merge:v2:"
MERGE_CACHE_TTL = 1800
VISUAL_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff"}

_PUNCT_PATTERN = re.compile(r"[\s,.;:!?\-_/\\，。；：！？（）()《》【】\[\]]+")
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_FILENAME_SEQ_PATTERNS = [
    re.compile(r"第\s*(\d+)\s*(?:册|卷|部分|篇)"),
    re.compile(r"(?:part|vol|volume|册|卷|p)[\s_-]*(\d+)", re.IGNORECASE),
    re.compile(r"(\d{1,4})(?!.*\d)"),
]


@dataclass(slots=True)
class TaskCandidate:
    task: OCRTask
    rule_fields: dict[str, str]
    title_norm: str
    doc_no_norm: str
    doc_no_prefix: str
    responsible_norm: str
    date_norm: str
    filename_norm: str
    sequence: int | None
    series_key: str
    visual_prefix: str
    visual_page_no: int | None
    title_hint: str
    document_family: str


@dataclass(slots=True)
class PositiveEdge:
    left_id: int
    right_id: int
    confidence: float
    reason: str


class _UnionFind:
    def __init__(self, size: int):
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, index: int) -> int:
        if self.parent[index] != index:
            self.parent[index] = self.find(self.parent[index])
        return self.parent[index]

    def union(self, left: int, right: int) -> None:
        root_left = self.find(left)
        root_right = self.find(right)
        if root_left == root_right:
            return
        if self.rank[root_left] < self.rank[root_right]:
            self.parent[root_left] = root_right
            return
        if self.rank[root_left] > self.rank[root_right]:
            self.parent[root_right] = root_left
            return
        self.parent[root_right] = root_left
        self.rank[root_left] += 1


def _coerce_text(value: Any) -> str:
    return shared_coerce_text(value)


def _normalize_text(value: Any) -> str:
    return _PUNCT_PATTERN.sub("", _coerce_text(value)).lower()


def _normalize_doc_no_prefix(value: str) -> str:
    if not value:
        return ""
    return re.sub(r"\d+", "", value)[:12]


def _extract_filename_sequence(filename: str) -> int | None:
    stem = Path(filename or "").stem
    if not stem:
        return None
    for pattern in _FILENAME_SEQ_PATTERNS:
        match = pattern.search(stem)
        if not match:
            continue
        try:
            return int(match.group(1))
        except (TypeError, ValueError):
            continue
    return None


def _build_series_key(filename: str) -> str:
    path = Path(filename or "")
    parent_norm = _normalize_text(str(path.parent))
    stem = re.sub(r"(?:[_-]?page[_-]?\d+|[_-]?\d{1,4})$", "", path.stem, flags=re.IGNORECASE)
    stem_norm = _normalize_text(stem or path.stem)
    return f"{parent_norm}|{stem_norm}" if parent_norm or stem_norm else ""


def _strip_html(value: str) -> str:
    return _HTML_TAG_RE.sub(" ", _coerce_text(value))


def _is_multi_layout_continuation_pair(
    left: TaskCandidate,
    right: TaskCandidate,
    *,
    same_visual_prefix: bool,
    visual_page_gap: int | None,
) -> bool:
    return (
        same_visual_prefix
        and visual_page_gap is not None
        and visual_page_gap <= 1
        and bool(left.document_family)
        and left.document_family == right.document_family
        and left.document_family in MULTI_LAYOUT_CONTINUATION_FAMILIES
    )

def _infer_document_family_from_task(*, title_hint: str, full_text: str) -> str:
    return infer_document_family_from_text(title_hint=title_hint, full_text=full_text)


def _extract_visual_sequence_parts(filename: str) -> tuple[str, int] | None:
    try:
        return parse_page_file(Path(filename or ""))
    except Exception:
        return None


def _is_visual_sequence_candidate(task: OCRTask) -> bool:
    file_type = _coerce_text(task.file_type).lower() or Path(task.filename or "").suffix.lower()
    return file_type in VISUAL_IMAGE_EXTENSIONS and _extract_visual_sequence_parts(task.filename) is not None


def _task_is_merge_eligible(task: OCRTask) -> bool:
    return task.status == "done" and bool(_coerce_text(task.full_text) or _is_visual_sequence_candidate(task))


def _task_is_boundary_analysis_eligible(task: OCRTask) -> bool:
    if _task_is_merge_eligible(task):
        return True
    return _is_visual_sequence_candidate(task)


def _similarity(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    return SequenceMatcher(a=left, b=right).ratio()


def _filename_sort_key(candidate: TaskCandidate) -> tuple[int, datetime, int]:
    sequence = (
        candidate.visual_page_no
        if candidate.visual_page_no is not None
        else (candidate.sequence if candidate.sequence is not None else 10**9)
    )
    created_at = candidate.task.created_at or datetime.min
    return sequence, created_at, candidate.task.id


def _merge_usage(total: dict[str, Any], usage: dict[str, Any]) -> None:
    for key, value in (usage or {}).items():
        if isinstance(value, (int, float)):
            total[key] = total.get(key, 0) + value
            continue
        if key not in total:
            total[key] = value


def _merge_cache_key(batch_id: str) -> str:
    return f"{MERGE_CACHE_PREFIX}{batch_id}"


def _normalize_similarity_threshold(value: int | None) -> int:
    if value is None:
        return BOUNDARY_SIMILARITY_THRESHOLD or DEFAULT_SIMILARITY_THRESHOLD
    try:
        return max(1, min(64, int(value)))
    except (TypeError, ValueError):
        return BOUNDARY_SIMILARITY_THRESHOLD or DEFAULT_SIMILARITY_THRESHOLD


def _uses_custom_similarity_threshold(value: int | None) -> bool:
    return value is not None and _normalize_similarity_threshold(value) != _normalize_similarity_threshold(None)


def _merge_cache_key_for_threshold(batch_id: str, similarity_threshold: int | None) -> str:
    if not _uses_custom_similarity_threshold(similarity_threshold):
        return _merge_cache_key(batch_id)
    return f"{_merge_cache_key(batch_id)}:th:{_normalize_similarity_threshold(similarity_threshold)}"


def _extract_group_task_ids(payload: dict[str, Any]) -> set[int]:
    ids: set[int] = set()
    for group in payload.get("groups", []):
        if not isinstance(group, dict):
            continue
        for task_id in group.get("task_ids", []):
            try:
                ids.add(int(task_id))
            except (TypeError, ValueError):
                continue
    return ids


def _extract_eligible_task_ids(tasks: list[OCRTask]) -> set[int]:
    return {
        int(task.id)
        for task in tasks
        if _task_is_merge_eligible(task)
    }


def _is_merge_cache_stale(payload: dict[str, Any], current_tasks: list[OCRTask]) -> bool:
    return _extract_group_task_ids(payload) != _extract_eligible_task_ids(current_tasks)


def _strip_evidence_in_result(payload: dict[str, Any]) -> None:
    for document in payload.get("documents", []):
        llm_fields = document.get("llm_fields")
        if isinstance(llm_fields, dict):
            llm_fields.pop("evidence", None)


def _suggested_group_pdf_filename(prefix: str, start_page: int, end_page: int) -> str:
    return f"{prefix}-{int(start_page):03d}-{int(end_page):03d}.pdf"


def _overall_recommended_similarity_threshold(sequence_meta: dict[str, Any] | None) -> int | None:
    values: list[int] = []
    for meta in (sequence_meta or {}).values():
        try:
            values.append(int(meta.get("recommended_similarity_threshold")))
        except (AttributeError, TypeError, ValueError):
            continue
    if not values:
        return None
    return int(round(sum(values) / float(len(values))))


def _apply_boundary_pdf_exports(
    payload: dict[str, Any],
    *,
    task_by_id: dict[int, OCRTask],
) -> tuple[list[str], int]:
    warnings: list[str] = []
    exported_count = 0
    groups = payload.get("groups") or []
    if not isinstance(groups, list):
        return warnings, exported_count

    for group in groups:
        if not isinstance(group, dict):
            continue
        prefix = _coerce_text(group.get("prefix"))
        start_page = int(group.get("start_page") or 0)
        end_page = int(group.get("end_page") or start_page)
        task_ids = [int(task_id) for task_id in (group.get("task_ids") or []) if str(task_id).strip()]
        group["page_count"] = len(task_ids)
        fallback_filename = _coerce_text(group.get("suggested_pdf_filename")) or f"{_coerce_text(group.get('group_id'))}.pdf"
        group["suggested_pdf_filename"] = (
            _suggested_group_pdf_filename(prefix, start_page, end_page)
            if prefix
            else fallback_filename
        )
        group["pdf_output_path"] = _coerce_text(group.get("pdf_output_path"))
        group["pdf_exported"] = bool(group.get("pdf_exported"))

        pages: list[PageFingerprint] = []
        output_root: Path | None = None
        for task_id in task_ids:
            task = task_by_id.get(task_id)
            if task is None:
                warnings.append(f"{group['suggested_pdf_filename']}: 缺少任务 {task_id}，未导出 PDF。")
                pages = []
                break

            image_path = Path(_coerce_text(task.file_path))
            if not image_path.exists():
                warnings.append(f"{group['suggested_pdf_filename']}: 找不到源图片 {image_path}，未导出 PDF。")
                pages = []
                break

            visual_sequence = _extract_visual_sequence_parts(task.filename or image_path.name)
            if visual_sequence is None:
                warnings.append(f"{group['suggested_pdf_filename']}: 文件名不符合连续页规则，未导出 PDF。")
                pages = []
                break

            page_prefix, page_no = visual_sequence
            if not prefix:
                prefix = page_prefix
                group["prefix"] = prefix
                group["suggested_pdf_filename"] = _suggested_group_pdf_filename(prefix, start_page, end_page)

            pages.append(
                PageFingerprint(
                    path=image_path,
                    prefix=page_prefix,
                    page_no=page_no,
                    phash=0,
                )
            )
            if output_root is None:
                output_root = image_path.parent / BOUNDARY_GROUP_PDF_OUTPUT_DIRNAME

        if not pages or output_root is None:
            continue

        pages.sort(key=lambda item: item.page_no)
        pdf_group = PDFGroup(prefix=prefix, pages=pages)
        try:
            output_path = save_group_as_pdf(pdf_group, output_root)
        except Exception:  # noqa: BLE001
            logger.warning("Failed to export grouped PDF for batch material %s", group.get("group_id"), exc_info=True)
            warnings.append(f"{group['suggested_pdf_filename']}: 导出 PDF 失败。")
            continue

        group["pdf_output_path"] = str(output_path)
        group["pdf_exported"] = True
        exported_count += 1

    return list(dict.fromkeys(warnings)), exported_count


def _finalize_boundary_payload(
    payload: dict[str, Any],
    *,
    batch_id: str,
    task_by_id: dict[int, OCRTask],
    applied_similarity_threshold: int,
    sequence_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    enriched = deepcopy(payload)
    enriched["sequence_meta"] = sequence_meta or dict(enriched.get("sequence_meta") or {})
    warnings, exported_count = _apply_boundary_pdf_exports(enriched, task_by_id=task_by_id)
    recommended_threshold = _overall_recommended_similarity_threshold(enriched.get("sequence_meta"))
    groups = enriched.get("groups") or []
    total_pages = sum(int(group.get("page_count") or len(group.get("task_ids") or [])) for group in groups if isinstance(group, dict))
    summary = dict(enriched.get("summary") or {})
    summary.update(
        {
            "group_count": len(groups),
            "grouped_pdf_count": exported_count,
            "total_pages": total_pages,
            "applied_similarity_threshold": applied_similarity_threshold,
            "recommended_similarity_threshold": recommended_threshold,
            "threshold_source": "manual_or_config",
        }
    )
    enriched["summary"] = summary
    enriched["warnings"] = warnings
    enriched["threshold_help"] = (
        "similarity_threshold 越大越宽松，越小越严格。推荐 8-15：版式稳定时可调到 8-10，"
        "同类材料版面差异较大时可放宽到 12-15。"
    )

    lines = [
        f"batch {batch_id}: 共识别出 {len(groups)} 个文件，覆盖 {total_pages} 页。",
        f"similarity_threshold = {applied_similarity_threshold}",
    ]
    if recommended_threshold is not None:
        lines.append(f"recommended_similarity_threshold = {recommended_threshold}")
    for index, group in enumerate(groups, start=1):
        if not isinstance(group, dict):
            continue
        start_page = int(group.get("start_page") or 0)
        end_page = int(group.get("end_page") or start_page)
        page_count = int(group.get("page_count") or len(group.get("task_ids") or []))
        filename = _coerce_text(group.get("suggested_pdf_filename"))
        lines.append(
            f"{index:02d}. {filename} | 页码 {start_page:03d}-{end_page:03d} | {page_count} 页"
        )
    for warning in warnings:
        lines.append(f"警告: {warning}")
    logger.info("\n%s", "\n".join(lines))
    return enriched


async def _load_batch_tasks(db: AsyncSession, batch_id: str) -> list[OCRTask]:
    stmt = (
        select(OCRTask)
        .join(ArchiveRecord, ArchiveRecord.task_id == OCRTask.id)
        .where(ArchiveRecord.batch_id == batch_id)
        .order_by(OCRTask.created_at.asc(), OCRTask.id.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()

    unique_tasks: list[OCRTask] = []
    seen: set[int] = set()
    for task in rows:
        if task.id in seen:
            continue
        seen.add(task.id)
        unique_tasks.append(task)
    return unique_tasks


def _build_task_candidate(task: OCRTask) -> TaskCandidate:
    fields = extract_fields(task.filename, task.full_text or "", task.result_json, task.page_count)
    title_hint = _coerce_text(fields.get("题名")) or infer_title_hint(task.full_text or "")
    title = _normalize_text(title_hint)
    doc_no = _normalize_text(fields.get("文号", ""))
    responsible = _normalize_text(fields.get("责任者", ""))
    date = _normalize_text(fields.get("日期", ""))
    filename_norm = _normalize_text(Path(task.filename or "").stem)
    visual_sequence = _extract_visual_sequence_parts(task.filename)
    return TaskCandidate(
        task=task,
        rule_fields=fields,
        title_norm=title,
        doc_no_norm=doc_no,
        doc_no_prefix=_normalize_doc_no_prefix(doc_no),
        responsible_norm=responsible,
        date_norm=date,
        filename_norm=filename_norm,
        sequence=_extract_filename_sequence(task.filename),
        series_key=_build_series_key(task.filename),
        visual_prefix=visual_sequence[0] if visual_sequence else "",
        visual_page_no=visual_sequence[1] if visual_sequence else None,
        title_hint=title_hint,
        document_family=_infer_document_family_from_task(title_hint=title_hint, full_text=task.full_text or ""),
    )


def _build_boundary_hints(
    candidates: list[TaskCandidate],
    *,
    feedback_priors=None,
    similarity_threshold: int | None = None,
) -> BoundaryResult:
    sequence_pages = [
        SequencePage(
            task_id=candidate.task.id,
            filename=candidate.task.filename,
            file_path=candidate.task.file_path,
            prefix=candidate.visual_prefix,
            page_no=int(candidate.visual_page_no or 0),
            created_at=candidate.task.created_at,
            title_hint=candidate.title_hint,
            full_text=candidate.task.full_text or "",
            title_norm=candidate.title_norm,
            doc_no_norm=candidate.doc_no_norm,
            doc_no_prefix=candidate.doc_no_prefix,
            responsible_norm=candidate.responsible_norm,
            date_norm=candidate.date_norm,
            document_family=candidate.document_family,
            rule_fields=candidate.rule_fields,
        )
        for candidate in candidates
        if candidate.visual_prefix and candidate.visual_page_no is not None
    ]
    return build_boundary_result(
        sequence_pages,
        feedback_priors=feedback_priors,
        similarity_threshold=_normalize_similarity_threshold(similarity_threshold),
    )


def _build_boundary_sequences_payload(candidates: list[TaskCandidate]) -> list[dict[str, Any]]:
    sequences: dict[str, list[TaskCandidate]] = defaultdict(list)
    for candidate in candidates:
        if not candidate.visual_prefix or candidate.visual_page_no is None:
            continue
        sequences[candidate.visual_prefix].append(candidate)

    payload: list[dict[str, Any]] = []
    for prefix, members in sorted(sequences.items()):
        ordered_members = sorted(members, key=_filename_sort_key)
        payload.append(
            {
                "prefix": prefix,
                "task_ids": [member.task.id for member in ordered_members],
                "filenames": [member.task.filename for member in ordered_members],
            }
        )
    return payload


def _build_boundary_analysis_payload(
    *,
    batch_id: str,
    boundary_sequences: list[dict[str, Any]],
    boundary_result: BoundaryResult,
) -> dict[str, Any]:
    return {
        "batch_id": batch_id,
        "sequences": boundary_sequences,
        "decisions": [
            {
                "left_task_id": decision.left_task_id,
                "right_task_id": decision.right_task_id,
                "prefix": decision.prefix,
                "left_page_no": decision.left_page_no,
                "right_page_no": decision.right_page_no,
                "same_document_score": decision.same_document_score,
                "should_merge": decision.should_merge,
                "is_ambiguous": decision.is_ambiguous,
                "strong_split": decision.strong_split,
                "reason": decision.reason,
                "signals": decision.signals,
            }
            for decision in boundary_result.adjacent_decisions
        ],
        "groups": [
            {
                "group_id": group.group_id,
                "prefix": group.prefix,
                "task_ids": group.task_ids,
                "filenames": group.filenames,
                "start_page": group.start_page,
                "end_page": group.end_page,
                "page_count": group.page_count,
                "confidence": group.confidence,
                "reasons": group.reasons,
                "suggested_pdf_filename": group.suggested_pdf_filename,
                "pdf_output_path": "",
                "pdf_exported": False,
            }
            for group in boundary_result.groups
        ],
        "task_to_group": boundary_result.task_to_group,
        "sequence_meta": boundary_result.sequence_meta,
        "summary": {
            "sequence_count": len(boundary_sequences),
            "decision_count": len(boundary_result.adjacent_decisions),
            "group_count": len(boundary_result.groups),
        },
    }


def _build_group_specs(
    *,
    candidates: list[TaskCandidate],
    union_find: _UnionFind,
    truth_task_to_doc_key: dict[int, str],
) -> list[tuple[list[TaskCandidate], str | None]]:
    candidate_by_task_id = {candidate.task.id: candidate for candidate in candidates}
    auto_groups: dict[int, list[TaskCandidate]] = defaultdict(list)
    for index, candidate in enumerate(candidates):
        auto_groups[union_find.find(index)].append(candidate)

    used_task_ids: set[int] = set()
    group_specs: list[tuple[list[TaskCandidate], str | None]] = []

    truth_groups: dict[str, list[TaskCandidate]] = defaultdict(list)
    for task_id, doc_key in truth_task_to_doc_key.items():
        candidate = candidate_by_task_id.get(task_id)
        if candidate is None:
            continue
        truth_groups[doc_key].append(candidate)

    if truth_groups:
        ordered_truth_groups = sorted(
            truth_groups.items(),
            key=lambda item: min(_filename_sort_key(member) for member in item[1]),
        )
        for doc_key, members in ordered_truth_groups:
            ordered_members = sorted(members, key=_filename_sort_key)
            group_specs.append((ordered_members, doc_key))
            used_task_ids.update(member.task.id for member in ordered_members)

    remaining_auto_groups = [
        sorted(members, key=_filename_sort_key)
        for members in auto_groups.values()
        if not any(member.task.id in used_task_ids for member in members)
    ]
    remaining_auto_groups.sort(key=lambda members: min(_filename_sort_key(member) for member in members))
    for members in remaining_auto_groups:
        group_specs.append((members, None))

    return group_specs


def _build_boundary_groups_from_truth(
    *,
    boundary_sequences: list[dict[str, Any]],
    boundary_result: BoundaryResult,
    truth_task_to_doc_key: dict[int, str],
) -> tuple[list[dict[str, Any]], dict[int, str]]:
    if not truth_task_to_doc_key:
        return (
            [
                {
                    "group_id": group.group_id,
                    "prefix": group.prefix,
                    "task_ids": group.task_ids,
                    "filenames": group.filenames,
                    "start_page": group.start_page,
                    "end_page": group.end_page,
                    "page_count": group.page_count,
                    "confidence": group.confidence,
                    "reasons": group.reasons,
                    "suggested_pdf_filename": group.suggested_pdf_filename,
                    "pdf_output_path": "",
                    "pdf_exported": False,
                }
                for group in boundary_result.groups
            ],
            dict(boundary_result.task_to_group),
        )

    sequence_by_task_id: dict[int, tuple[str, str]] = {}
    for sequence in boundary_sequences:
        prefix = str(sequence.get("prefix", "") or "")
        filenames = sequence.get("filenames") or []
        for task_id, filename in zip(sequence.get("task_ids") or [], filenames):
            try:
                sequence_by_task_id[int(task_id)] = (prefix, str(filename))
            except (TypeError, ValueError):
                continue

    grouped_tasks: dict[str, list[int]] = defaultdict(list)
    for task_id, doc_key in truth_task_to_doc_key.items():
        grouped_tasks[doc_key].append(task_id)

    groups_payload: list[dict[str, Any]] = []
    task_to_group: dict[int, str] = {}
    covered_task_ids: set[int] = set()

    ordered_truth_groups = sorted(
        grouped_tasks.items(),
        key=lambda item: min(sequence_by_task_id.get(task_id, ("", ""))[1] for task_id in item[1]),
    )
    for doc_key, task_ids in ordered_truth_groups:
        ordered_task_ids = sorted(task_ids, key=lambda task_id: sequence_by_task_id.get(task_id, ("", ""))[1])
        filenames = [sequence_by_task_id.get(task_id, ("", ""))[1] for task_id in ordered_task_ids]
        prefix = sequence_by_task_id.get(ordered_task_ids[0], ("", ""))[0] if ordered_task_ids else ""
        page_numbers = [parse_page_file(Path(filename))[1] for filename in filenames if filename]
        group_id = f"truth:{doc_key}"
        reasons = [f"人工校正：按 doc_key={doc_key} 覆盖文档归并结果。"]
        groups_payload.append(
            {
                "group_id": group_id,
                "prefix": prefix,
                "task_ids": ordered_task_ids,
                "filenames": filenames,
                "start_page": min(page_numbers) if page_numbers else 0,
                "end_page": max(page_numbers) if page_numbers else 0,
                "page_count": len(ordered_task_ids),
                "confidence": 1.0,
                "reasons": reasons,
                "suggested_pdf_filename": _suggested_group_pdf_filename(
                    prefix,
                    min(page_numbers) if page_numbers else 0,
                    max(page_numbers) if page_numbers else 0,
                ),
                "pdf_output_path": "",
                "pdf_exported": False,
            }
        )
        for task_id in ordered_task_ids:
            task_to_group[task_id] = group_id
        covered_task_ids.update(ordered_task_ids)

    for group in boundary_result.groups:
        remaining_task_ids = [task_id for task_id in group.task_ids if task_id not in covered_task_ids]
        if not remaining_task_ids:
            continue
        filenames = [sequence_by_task_id.get(task_id, ("", ""))[1] for task_id in remaining_task_ids]
        groups_payload.append(
            {
                "group_id": group.group_id,
                "prefix": group.prefix,
                "task_ids": remaining_task_ids,
                "filenames": filenames,
                "start_page": group.start_page,
                "end_page": group.end_page,
                "page_count": len(remaining_task_ids),
                "confidence": group.confidence,
                "reasons": group.reasons,
                "suggested_pdf_filename": group.suggested_pdf_filename,
                "pdf_output_path": "",
                "pdf_exported": False,
            }
        )
        for task_id in remaining_task_ids:
            task_to_group[task_id] = group.group_id

    groups_payload.sort(key=lambda item: (item.get("prefix") or "", item.get("start_page") or 0, item["group_id"]))
    return groups_payload, task_to_group


def _build_visual_group_hints(candidates: list[TaskCandidate]) -> tuple[dict[int, str], dict[str, dict[str, Any]]]:
    visual_group_by_task_id: dict[int, str] = {}
    visual_group_meta: dict[str, dict[str, Any]] = {}
    sequence_candidates: dict[str, list[TaskCandidate]] = defaultdict(list)

    for candidate in candidates:
        if not candidate.visual_prefix or candidate.visual_page_no is None:
            continue
        if not Path(candidate.task.file_path).exists():
            continue
        sequence_candidates[candidate.visual_prefix].append(candidate)

    for prefix, members in sequence_candidates.items():
        ordered_members = sorted(members, key=_filename_sort_key)
        fingerprints: list[PageFingerprint] = []
        fingerprint_to_candidate: dict[int, TaskCandidate] = {}
        previous_fingerprint: PageFingerprint | None = None

        for candidate in ordered_members:
            try:
                image_path = Path(candidate.task.file_path)
                layout_hash, row_profile, col_profile, ink_ratio = _compute_layout_signature(image_path)
                fingerprint = PageFingerprint(
                    path=image_path,
                    prefix=prefix,
                    page_no=int(candidate.visual_page_no or 0),
                    phash=compute_phash(image_path),
                    layout_hash=layout_hash,
                    ink_ratio=ink_ratio,
                    row_profile=row_profile,
                    col_profile=col_profile,
                    text_signature=_normalize_text(candidate.task.full_text or ""),
                )
                if previous_fingerprint is not None:
                    comparison = compare_page_fingerprints(previous_fingerprint, fingerprint)
                    fingerprint.distance_from_previous = comparison.phash_distance
                    fingerprint.comparison_from_previous = comparison
                fingerprints.append(fingerprint)
                fingerprint_to_candidate[id(fingerprint)] = candidate
                previous_fingerprint = fingerprint
            except Exception:
                logger.debug(
                    "Skipping visual grouping fingerprint build for task=%s file=%s",
                    candidate.task.id,
                    candidate.task.file_path,
                    exc_info=True,
                )

        if not fingerprints:
            continue

        threshold = suggest_similarity_threshold(fingerprints)
        groups = group_pages_by_similarity(
            fingerprints,
            similarity_threshold=threshold,
            text_similarity_threshold=DEFAULT_TEXT_SIMILARITY_THRESHOLD,
        )
        for group_index, group in enumerate(groups, start=1):
            member_candidates = [
                fingerprint_to_candidate[id(page)]
                for page in group.pages
                if id(page) in fingerprint_to_candidate
            ]
            if not member_candidates:
                continue
            member_candidates.sort(key=_filename_sort_key)
            group_id = f"{prefix}#visual-{group_index}"
            start_page = member_candidates[0].visual_page_no or 0
            end_page = member_candidates[-1].visual_page_no or start_page
            adjacent_scores = [
                float(page.comparison_from_previous.combined_change_score or 0.0)
                for page in group.pages[1:]
                if page.comparison_from_previous is not None
            ]
            confidence = round(max(0.9, 1.0 - (max(adjacent_scores) * 0.08 if adjacent_scores else 0.02)), 4)
            reason = (
                f"视觉分页判定为同一原始文件（序列 {prefix}，页码 {start_page:03d}-{end_page:03d}，"
                f"阈值 {threshold}）。"
            )
            visual_group_meta[group_id] = {
                "confidence": confidence,
                "reason": reason,
                "task_ids": [candidate.task.id for candidate in member_candidates],
            }
            for candidate in member_candidates:
                visual_group_by_task_id[candidate.task.id] = group_id

    return visual_group_by_task_id, visual_group_meta


def _same_document_acceptance_threshold(
    left: TaskCandidate,
    right: TaskCandidate,
    *,
    left_index: int,
    right_index: int,
) -> float:
    visual_page_gap = (
        abs(left.visual_page_no - right.visual_page_no)
        if left.visual_page_no is not None and right.visual_page_no is not None
        else None
    )
    if (
        left.visual_prefix
        and left.visual_prefix == right.visual_prefix
        and visual_page_gap is not None
        and visual_page_gap <= 1
    ):
        return ADJACENT_PAGE_SAME_DOCUMENT_CONFIDENCE_THRESHOLD

    if left.series_key and left.series_key == right.series_key and (right_index - left_index) <= 1:
        return max(ADJACENT_PAGE_SAME_DOCUMENT_CONFIDENCE_THRESHOLD, 0.84)

    return SAME_DOCUMENT_CONFIDENCE_THRESHOLD


def _should_use_llm_for_uncertain_pair(
    left: TaskCandidate,
    right: TaskCandidate,
    *,
    left_index: int,
    right_index: int,
) -> bool:
    pair_distance = right_index - left_index
    title_similarity = _similarity(left.title_norm, right.title_norm)
    filename_similarity = _similarity(left.filename_norm, right.filename_norm)
    same_date = bool(left.date_norm and right.date_norm and left.date_norm == right.date_norm)
    same_responsible = bool(
        left.responsible_norm and right.responsible_norm and left.responsible_norm == right.responsible_norm
    )
    same_doc_no_prefix = bool(
        left.doc_no_prefix and right.doc_no_prefix and left.doc_no_prefix == right.doc_no_prefix
    )
    same_series = bool(left.series_key and left.series_key == right.series_key)
    sequence_gap = (
        abs(left.sequence - right.sequence)
        if left.sequence is not None and right.sequence is not None
        else None
    )
    same_visual_prefix = bool(left.visual_prefix and left.visual_prefix == right.visual_prefix)
    visual_page_gap = (
        abs(left.visual_page_no - right.visual_page_no)
        if left.visual_page_no is not None and right.visual_page_no is not None
        else None
    )

    if same_visual_prefix and visual_page_gap is not None and visual_page_gap <= SERIES_NEIGHBOR_DISTANCE:
        return True

    if same_series:
        if sequence_gap is not None:
            return sequence_gap <= SERIES_NEIGHBOR_DISTANCE
        return pair_distance <= SERIES_NEIGHBOR_DISTANCE

    if pair_distance <= NEARBY_CANDIDATE_DISTANCE:
        if title_similarity >= TITLE_HINT_THRESHOLD:
            return True
        if filename_similarity >= FILENAME_HINT_THRESHOLD and (same_date or same_responsible or same_doc_no_prefix):
            return True
        if same_date and (same_responsible or same_doc_no_prefix):
            return True

    if title_similarity >= 0.9 and (same_date or same_responsible or filename_similarity >= 0.7):
        return True

    return False


def _has_intermediate_visual_candidate(
    left: TaskCandidate,
    right: TaskCandidate,
    candidates: list[TaskCandidate],
) -> bool:
    if not left.visual_prefix or left.visual_prefix != right.visual_prefix:
        return False
    if left.visual_page_no is None or right.visual_page_no is None:
        return False
    start_page = min(left.visual_page_no, right.visual_page_no)
    end_page = max(left.visual_page_no, right.visual_page_no)
    if end_page - start_page <= 1:
        return False
    for candidate in candidates:
        if candidate.task.id in {left.task.id, right.task.id}:
            continue
        if candidate.visual_prefix != left.visual_prefix or candidate.visual_page_no is None:
            continue
        if start_page < candidate.visual_page_no < end_page:
            return True
    return False


def _rule_decision(
    left: TaskCandidate,
    right: TaskCandidate,
    *,
    visual_group_by_task_id: dict[int, str] | None = None,
    visual_group_meta: dict[str, dict[str, Any]] | None = None,
    boundary_group_by_task_id: dict[int, str] | None = None,
    boundary_group_meta: dict[str, dict[str, Any]] | None = None,
    boundary_pair_meta: dict[tuple[int, int], dict[str, Any]] | None = None,
) -> tuple[bool | None, float, str]:
    visual_group_by_task_id = visual_group_by_task_id or {}
    visual_group_meta = visual_group_meta or {}
    boundary_group_by_task_id = boundary_group_by_task_id or {}
    boundary_group_meta = boundary_group_meta or {}
    boundary_pair_meta = boundary_pair_meta or {}
    left_visual_group = visual_group_by_task_id.get(left.task.id, "")
    right_visual_group = visual_group_by_task_id.get(right.task.id, "")
    left_boundary_group = boundary_group_by_task_id.get(left.task.id, "")
    right_boundary_group = boundary_group_by_task_id.get(right.task.id, "")
    same_visual_prefix = bool(left.visual_prefix and left.visual_prefix == right.visual_prefix)
    visual_page_gap = (
        abs(left.visual_page_no - right.visual_page_no)
        if left.visual_page_no is not None and right.visual_page_no is not None
        else None
    )
    pair_key = (left.task.id, right.task.id) if left.task.id <= right.task.id else (right.task.id, left.task.id)
    boundary_pair = boundary_pair_meta.get(pair_key) or {}
    multi_layout_continuation = _is_multi_layout_continuation_pair(
        left,
        right,
        same_visual_prefix=same_visual_prefix,
        visual_page_gap=visual_page_gap,
    )

    if left_boundary_group and right_boundary_group:
        if left_boundary_group == right_boundary_group:
            meta = boundary_group_meta.get(left_boundary_group) or {}
            return (
                True,
                float(meta.get("confidence", 0.92)),
                _coerce_text(meta.get("reason")) or "边界引擎判定为同一原始文件。",
            )
        if same_visual_prefix and visual_page_gap is not None and visual_page_gap <= 1 and boundary_pair:
            if bool(boundary_pair.get("is_ambiguous")):
                return (
                    None,
                    float(boundary_pair.get("same_document_score", 0)),
                    _coerce_text(boundary_pair.get("reason")) or "边界引擎判定边界不确定，需进一步确认。",
                )
            return (
                False,
                0.0,
                _coerce_text(boundary_pair.get("reason")) or "边界引擎判定已切换到下一份原始文件。",
            )

    if left_visual_group and right_visual_group:
        if left_visual_group == right_visual_group:
            visual_meta = visual_group_meta.get(left_visual_group) or {}
            return (
                True,
                float(visual_meta.get("confidence", 0.96)),
                _coerce_text(visual_meta.get("reason")) or "视觉布局连续，判定为同一原始文件。",
            )
        if same_visual_prefix and not multi_layout_continuation:
            return False, 0.0, "视觉分页判定显示已切换到下一份原始文件。"

    if multi_layout_continuation:
        return True, 0.86, f"相邻页同属{document_family_label(left.document_family)}类材料，判定为同一原始文件。"

    if left.doc_no_norm and right.doc_no_norm:
        if left.doc_no_norm == right.doc_no_norm:
            return True, 1.0, "文号完全一致。"
        return False, 0.0, "文号不一致。"

    if (
        left.series_key
        and left.series_key == right.series_key
        and left.sequence is not None
        and right.sequence is not None
        and abs(left.sequence - right.sequence) <= SERIES_NEIGHBOR_DISTANCE
    ):
        return None, 0.0, "文件序列连续且属于同一命名系列，需结合视觉或文本进一步确认。"

    title_similarity = _similarity(left.title_norm, right.title_norm)
    filename_similarity = _similarity(left.filename_norm, right.filename_norm)
    same_date = bool(left.date_norm and right.date_norm and left.date_norm == right.date_norm)
    same_responsible = bool(
        left.responsible_norm and right.responsible_norm and left.responsible_norm == right.responsible_norm
    )

    if left.title_norm and right.title_norm and title_similarity >= TITLE_STRONG_MATCH_THRESHOLD:
        if same_date:
            return True, 0.97, "题名高度一致且日期一致。"
        if same_responsible:
            return True, 0.94, "题名高度一致且责任者一致。"

    if left.title_norm and right.title_norm and title_similarity <= 0.35 and left.date_norm and right.date_norm:
        if left.date_norm != right.date_norm:
            return False, 0.0, "题名差异较大且日期不一致。"

    hints: list[str] = []
    if title_similarity >= TITLE_HINT_THRESHOLD:
        hints.append("题名相似")
    if filename_similarity >= FILENAME_HINT_THRESHOLD:
        hints.append("文件名相似")
    if same_date:
        hints.append("日期一致")
    if same_responsible:
        hints.append("责任者一致")
    if left.doc_no_prefix and right.doc_no_prefix and left.doc_no_prefix == right.doc_no_prefix:
        hints.append("文号前缀一致")

    if hints:
        return None, 0.0, f"规则存在不确定信号：{'、'.join(hints)}。"
    return False, 0.0, "缺少可支持同文档的规则信号。"


def _collect_group_edges(group_ids: set[int], edges: list[PositiveEdge]) -> list[PositiveEdge]:
    return [
        edge
        for edge in edges
        if edge.left_id in group_ids and edge.right_id in group_ids
    ]


def _dedupe_reasons(reasons: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for reason in reasons:
        if not reason or reason in seen:
            continue
        seen.add(reason)
        result.append(reason)
    return result


def _build_merged_text(candidates: list[TaskCandidate]) -> tuple[str, int, list[dict[str, Any]]]:
    parts: list[str] = []
    merged_pages: list[dict[str, Any]] = []
    page_count = 0

    for candidate in candidates:
        task = candidate.task
        parts.append(
            "\n".join(
                [
                    f"--- 文件片段开始: {task.filename} (task_id={task.id}) ---",
                    task.full_text or "",
                    f"--- 文件片段结束: {task.filename} (task_id={task.id}) ---",
                ]
            )
        )
        page_count += max(task.page_count or 0, 0)

        result_json = task.result_json
        if isinstance(result_json, list):
            merged_pages.extend(page for page in result_json if isinstance(page, dict))
        elif isinstance(result_json, dict):
            merged_pages.append(result_json)

    return "\n\n".join(parts), page_count, merged_pages


async def _run_limited(semaphore: asyncio.Semaphore, coroutine):
    async with semaphore:
        return await coroutine


def _build_rule_fallback_comparison(
    *,
    filename: str,
    page_count: int,
    full_text: str,
    result_json: Any,
) -> dict[str, Any]:
    rule_fields = extract_fields(filename, full_text or "", result_json, page_count)
    llm_fields = {field: "" for field in ARCHIVE_FIELDS}
    llm_fields["evidence"] = {field: "" for field in ARCHIVE_FIELDS}
    return {
        "rule_fields": rule_fields,
        "llm_fields": llm_fields,
        "recommended_fields": dict(rule_fields),
        "conflicts": {},
        "agreement": build_agreement_summary(rule_fields, llm_fields),
        "provider": "rule-fallback",
        "model": "",
        "raw_usage": {},
    }


async def batch_merge_extract_fields(
    db: AsyncSession,
    *,
    batch_id: str,
    include_evidence: bool = True,
    similarity_threshold: int | None = None,
) -> dict[str, Any] | None:
    tasks = await _load_batch_tasks(db, batch_id)
    if not tasks:
        return None

    skipped_tasks: list[dict[str, Any]] = []
    eligible_tasks: list[OCRTask] = []
    done_tasks = 0
    for task in tasks:
        if task.status == "done":
            done_tasks += 1
        if task.status != "done":
            skipped_tasks.append(
                {
                    "task_id": task.id,
                    "filename": task.filename,
                    "status": task.status,
                    "reason": NOT_DONE_REASON,
                }
            )
            continue
        if not _coerce_text(task.full_text) and not _is_visual_sequence_candidate(task):
            skipped_tasks.append(
                {
                    "task_id": task.id,
                    "filename": task.filename,
                    "status": task.status,
                    "reason": MISSING_TEXT_WITHOUT_VISUAL_REASON,
                }
            )
            continue
        eligible_tasks.append(task)

    if not eligible_tasks:
        return None

    candidates = [_build_task_candidate(task) for task in eligible_tasks]
    feedback_priors = await load_boundary_feedback_priors(db)
    boundary_sequences = _build_boundary_sequences_payload(candidates)
    applied_similarity_threshold = _normalize_similarity_threshold(similarity_threshold)
    boundary_result = _build_boundary_hints(
        candidates,
        feedback_priors=feedback_priors,
        similarity_threshold=applied_similarity_threshold,
    )
    if not _uses_custom_similarity_threshold(similarity_threshold):
        try:
            await save_boundary_analysis(
                db,
                batch_id=batch_id,
                sequences=boundary_sequences,
                boundary_result=boundary_result,
            )
        except Exception:  # noqa: BLE001
            logger.warning("Failed to persist boundary analysis for batch %s during merge extraction.", batch_id, exc_info=True)
    try:
        boundary_truth = await get_batch_boundary_truth(db, batch_id=batch_id)
    except Exception:  # noqa: BLE001
        logger.warning("Failed to load boundary truth for batch %s during merge extraction.", batch_id, exc_info=True)
        boundary_truth = {"tasks": []}
    truth_task_to_doc_key = {
        int(item["task_id"]): _coerce_text(item.get("doc_key"))
        for item in boundary_truth.get("tasks", [])
        if _coerce_text(item.get("doc_key"))
    }
    boundary_group_by_task_id = boundary_result.task_to_group
    boundary_group_meta = boundary_result.group_meta
    boundary_pair_meta = boundary_result.pair_meta
    union_find = _UnionFind(len(candidates))
    candidate_index_by_task_id = {candidate.task.id: index for index, candidate in enumerate(candidates)}
    positive_edges: list[PositiveEdge] = []
    raw_usage: dict[str, Any] = {}
    provider = "rule-fallback"
    model = ""
    llm_semaphore = asyncio.Semaphore(MINIMAX_BATCH_CONCURRENCY)
    pending_pair_jobs: list[tuple[int, int, str, TaskCandidate, TaskCandidate]] = []

    for group in boundary_result.groups:
        if len(group.task_ids) <= 1:
            continue
        for left_id, right_id in zip(group.task_ids, group.task_ids[1:]):
            left_index = candidate_index_by_task_id.get(left_id)
            right_index = candidate_index_by_task_id.get(right_id)
            if left_index is None or right_index is None:
                continue
            union_find.union(left_index, right_index)
            pair_key = (left_id, right_id) if left_id <= right_id else (right_id, left_id)
            pair_meta = boundary_pair_meta.get(pair_key) or {}
            positive_edges.append(
                PositiveEdge(
                    left_id=left_id,
                    right_id=right_id,
                    confidence=float(pair_meta.get("same_document_score", group.confidence)),
                    reason=_coerce_text(pair_meta.get("reason")) or "边界引擎判定为同一原始文件。",
                )
            )

    for left_index in range(len(candidates)):
        for right_index in range(left_index + 1, len(candidates)):
            left = candidates[left_index]
            right = candidates[right_index]
            left_boundary_group = boundary_group_by_task_id.get(left.task.id, "")
            right_boundary_group = boundary_group_by_task_id.get(right.task.id, "")
            if left_boundary_group and left_boundary_group == right_boundary_group:
                continue
            merge, confidence, reason = _rule_decision(
                left,
                right,
                boundary_group_by_task_id=boundary_group_by_task_id,
                boundary_group_meta=boundary_group_meta,
                boundary_pair_meta=boundary_pair_meta,
            )
            if merge is True:
                union_find.union(left_index, right_index)
                positive_edges.append(
                    PositiveEdge(
                        left_id=left.task.id,
                        right_id=right.task.id,
                        confidence=confidence,
                        reason=reason,
                    )
                )
                continue
            if merge is False:
                continue

            if _has_intermediate_visual_candidate(left, right, candidates):
                continue

            if not _should_use_llm_for_uncertain_pair(
                left,
                right,
                left_index=left_index,
                right_index=right_index,
            ):
                continue

            pending_pair_jobs.append((left_index, right_index, reason, left, right))

    if pending_pair_jobs:
        pair_results = await asyncio.gather(
            *[
                _run_limited(
                    llm_semaphore,
                    call_minimax_same_document_judgement(
                        left_filename=left.task.filename,
                        left_page_count=left.task.page_count,
                        left_full_text=left.task.full_text or "",
                        left_rule_fields=left.rule_fields,
                        right_filename=right.task.filename,
                        right_page_count=right.task.page_count,
                        right_full_text=right.task.full_text or "",
                        right_rule_fields=right.rule_fields,
                    ),
                )
                for _left_index, _right_index, _reason, left, right in pending_pair_jobs
            ],
            return_exceptions=True,
        )

        for (left_index, right_index, reason, left, right), llm_decision in zip(pending_pair_jobs, pair_results):
            if isinstance(llm_decision, Exception):
                logger.warning(
                    "Skipping uncertain pair (%s, %s) for batch %s because same-document judgement failed: %s",
                    left.task.id,
                    right.task.id,
                    batch_id,
                    llm_decision,
                )
                continue
            _merge_usage(raw_usage, llm_decision.get("raw_usage", {}))
            provider = llm_decision.get("provider") or provider
            model = model or (llm_decision.get("model") or "")

            acceptance_threshold = _same_document_acceptance_threshold(
                left,
                right,
                left_index=left_index,
                right_index=right_index,
            )
            if llm_decision.get("same_document") and llm_decision.get("confidence", 0) >= acceptance_threshold:
                union_find.union(left_index, right_index)
                evidence = _coerce_text(llm_decision.get("evidence"))
                llm_reason = (
                    f"LLM判定同文档（置信度 {llm_decision.get('confidence', 0):.2f}，"
                    f"接收阈值 {acceptance_threshold:.2f}）。"
                )
                if evidence:
                    llm_reason = f"{llm_reason} 证据：{evidence}"
                positive_edges.append(
                    PositiveEdge(
                        left_id=left.task.id,
                        right_id=right.task.id,
                        confidence=float(llm_decision.get("confidence", 0)),
                        reason=f"{reason} {llm_reason}".strip(),
                    )
                )

    groups_payload: list[dict[str, Any]] = []
    documents_payload: list[dict[str, Any]] = []
    group_members: dict[str, list[TaskCandidate]] = {}

    group_specs = _build_group_specs(
        candidates=candidates,
        union_find=union_find,
        truth_task_to_doc_key=truth_task_to_doc_key,
    )

    for group_number, (members, truth_doc_key) in enumerate(group_specs, start=1):
        group_id = f"group-{group_number}"
        group_members[group_id] = members
        member_task_ids = [member.task.id for member in members]
        member_filenames = [member.task.filename for member in members]
        prefix = _coerce_text(members[0].visual_prefix if members else "")
        page_numbers = [int(member.visual_page_no or 0) for member in members if member.visual_page_no is not None]
        start_page = min(page_numbers) if page_numbers else 0
        end_page = max(page_numbers) if page_numbers else 0
        if truth_doc_key:
            confidence = 1.0
            reasons = [f"人工校正：按 doc_key={truth_doc_key} 覆盖文档归并结果。"]
        else:
            edge_candidates = _collect_group_edges(set(member_task_ids), positive_edges)
            if edge_candidates:
                confidence = min(edge.confidence for edge in edge_candidates)
                reasons = _dedupe_reasons([edge.reason for edge in edge_candidates])
            else:
                confidence = 1.0
                reasons = ["单文件组，无需合并判定。"]

        groups_payload.append(
            {
                "group_id": group_id,
                "prefix": prefix,
                "task_ids": member_task_ids,
                "filenames": member_filenames,
                "start_page": start_page,
                "end_page": end_page,
                "page_count": len(member_task_ids),
                "same_document_confidence": round(float(confidence), 4),
                "decision_reasons": reasons,
                "suggested_pdf_filename": _suggested_group_pdf_filename(prefix, start_page, end_page) if prefix else "",
                "pdf_output_path": "",
                "pdf_exported": False,
                **({"truth_doc_key": truth_doc_key} if truth_doc_key else {}),
            }
        )

    group_compare_jobs: list[tuple[dict[str, Any], int, str, str, Any]] = []
    compare_coroutines = []
    for group in groups_payload:
        members = group_members[group["group_id"]]
        merged_text, merged_page_count, merged_pages = _build_merged_text(members)
        if merged_page_count <= 0:
            merged_page_count = len(merged_pages)
        merged_filename = (
            members[0].task.filename
            if len(members) == 1
            else f"{Path(members[0].task.filename).stem}_merged_{len(members)}"
        )
        group_compare_jobs.append((group, merged_page_count, merged_filename, merged_text, merged_pages))
        compare_coroutines.append(
            _run_limited(
                llm_semaphore,
                compare_rule_and_llm_fields_for_content(
                    filename=merged_filename,
                    page_count=merged_page_count,
                    full_text=merged_text,
                    result_json=merged_pages,
                    include_evidence=include_evidence,
                ),
            )
        )

    if compare_coroutines:
        compare_results = await asyncio.gather(*compare_coroutines, return_exceptions=True)
        for (group, merged_page_count, merged_filename, merged_text, merged_pages), comparison in zip(
            group_compare_jobs,
            compare_results,
        ):
            if isinstance(comparison, Exception):
                logger.warning(
                    "Falling back to rule-only extraction for group %s in batch %s because field extraction failed: %s",
                    group["group_id"],
                    batch_id,
                    comparison,
                )
                comparison = _build_rule_fallback_comparison(
                    filename=merged_filename,
                    page_count=merged_page_count,
                    full_text=merged_text,
                    result_json=merged_pages,
                )

            _merge_usage(raw_usage, comparison.get("raw_usage", {}))
            comparison_provider = comparison.get("provider")
            if comparison_provider not in {"", None}:
                provider = comparison_provider
            model = model or (comparison.get("model") or "")
            documents_payload.append(
                {
                    "group_id": group["group_id"],
                    "merged_page_count": merged_page_count,
                    "rule_fields": comparison["rule_fields"],
                    "llm_fields": comparison["llm_fields"],
                    "recommended_fields": comparison["recommended_fields"],
                    "conflicts": comparison["conflicts"],
                    "agreement": comparison["agreement"],
                }
            )

    result = {
        "batch_id": batch_id,
        "groups": groups_payload,
        "documents": documents_payload,
        "provider": provider,
        "model": model,
        "raw_usage": raw_usage,
        "summary": {
            "total_tasks": len(tasks),
            "done_tasks": done_tasks,
            "eligible_tasks": len(eligible_tasks),
            "skipped_tasks": skipped_tasks,
            "groups_count": len(groups_payload),
            "documents_count": len(documents_payload),
        },
    }
    return _finalize_boundary_payload(
        result,
        batch_id=batch_id,
        task_by_id={int(task.id): task for task in eligible_tasks},
        applied_similarity_threshold=applied_similarity_threshold,
        sequence_meta=boundary_result.sequence_meta,
    )


async def get_batch_merge_extract_result(
    db: AsyncSession,
    *,
    batch_id: str,
    include_evidence: bool = True,
    force_refresh: bool = False,
    similarity_threshold: int | None = None,
) -> dict[str, Any] | None:
    cache_key = _merge_cache_key_for_threshold(batch_id, similarity_threshold)
    if not force_refresh:
        cached = cache_get(cache_key)
        if isinstance(cached, dict):
            try:
                current_tasks = await _load_batch_tasks(db, batch_id)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Failed to validate batch merge cache for batch %s, fallback to cached payload.",
                    batch_id,
                    exc_info=True,
                )
                current_tasks = None
            if current_tasks is None:
                payload = deepcopy(cached)
                if not include_evidence:
                    _strip_evidence_in_result(payload)
                return payload
            if _is_merge_cache_stale(cached, current_tasks):
                logger.info("Discarding stale batch merge cache for batch %s.", batch_id)
                cache_delete(cache_key)
            else:
                payload = deepcopy(cached)
                if not include_evidence:
                    _strip_evidence_in_result(payload)
                return payload

    computed = await batch_merge_extract_fields(
        db,
        batch_id=batch_id,
        include_evidence=True,
        similarity_threshold=similarity_threshold,
    )
    if not computed:
        return None

    computed["generated_at"] = datetime.now(timezone.utc).isoformat()
    cache_set(cache_key, computed, MERGE_CACHE_TTL)
    payload = deepcopy(computed)
    if not include_evidence:
        _strip_evidence_in_result(payload)
    return payload


async def get_batch_boundary_analysis_result(
    db: AsyncSession,
    *,
    batch_id: str,
    force_refresh: bool = False,
    similarity_threshold: int | None = None,
) -> dict[str, Any] | None:
    tasks = await _load_batch_tasks(db, batch_id)
    eligible_tasks = [task for task in tasks if _task_is_boundary_analysis_eligible(task)]
    eligible_task_ids = {int(task.id) for task in eligible_tasks}
    applied_similarity_threshold = _normalize_similarity_threshold(similarity_threshold)
    uses_custom_threshold = _uses_custom_similarity_threshold(similarity_threshold)
    try:
        boundary_truth = await get_batch_boundary_truth(db, batch_id=batch_id)
    except Exception:  # noqa: BLE001
        logger.warning("Failed to load boundary truth for batch %s.", batch_id, exc_info=True)
        boundary_truth = {"tasks": []}
    truth_task_to_doc_key = {
        int(item["task_id"]): _coerce_text(item.get("doc_key"))
        for item in boundary_truth.get("tasks", [])
        if _coerce_text(item.get("doc_key"))
    }

    if not force_refresh and not uses_custom_threshold:
        persisted = await load_boundary_analysis(db, batch_id=batch_id)
        persisted_task_ids = {int(task_id) for task_id in (persisted or {}).get("task_to_group", {}).keys()}
        if persisted and persisted_task_ids == eligible_task_ids and not truth_task_to_doc_key:
            return _finalize_boundary_payload(
                persisted,
                batch_id=batch_id,
                task_by_id={int(task.id): task for task in eligible_tasks},
                applied_similarity_threshold=applied_similarity_threshold,
                sequence_meta=dict(persisted.get("sequence_meta") or {}),
            )

    if not eligible_tasks:
        return None

    candidates = [_build_task_candidate(task) for task in eligible_tasks]
    feedback_priors = await load_boundary_feedback_priors(db)
    boundary_sequences = _build_boundary_sequences_payload(candidates)
    boundary_result = _build_boundary_hints(
        candidates,
        feedback_priors=feedback_priors,
        similarity_threshold=applied_similarity_threshold,
    )
    if not uses_custom_threshold:
        try:
            await save_boundary_analysis(
                db,
                batch_id=batch_id,
                sequences=boundary_sequences,
                boundary_result=boundary_result,
            )
        except Exception:  # noqa: BLE001
            logger.warning("Failed to persist boundary analysis for batch %s.", batch_id, exc_info=True)
    payload = _build_boundary_analysis_payload(
        batch_id=batch_id,
        boundary_sequences=boundary_sequences,
        boundary_result=boundary_result,
    )
    if truth_task_to_doc_key:
        groups_payload, task_to_group = _build_boundary_groups_from_truth(
            boundary_sequences=boundary_sequences,
            boundary_result=boundary_result,
            truth_task_to_doc_key=truth_task_to_doc_key,
        )
        payload["groups"] = groups_payload
        payload["task_to_group"] = task_to_group
        payload["summary"]["group_count"] = len(groups_payload)
        payload["truth_updated_at"] = boundary_truth.get("truth_updated_at")
    return _finalize_boundary_payload(
        payload,
        batch_id=batch_id,
        task_by_id={int(task.id): task for task in eligible_tasks},
        applied_similarity_threshold=applied_similarity_threshold,
        sequence_meta=boundary_result.sequence_meta,
    )
