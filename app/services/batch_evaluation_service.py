import hashlib
import itertools
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete as sa_delete
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_cache import cache_delete_pattern, cache_get, cache_set
from app.db.models import ArchiveRecord, BatchTruthDocumentField, BatchTruthTaskMap
from app.services.batch_merge_extraction_service import get_batch_merge_extract_result
from app.services.llm_field_extraction_service import ARCHIVE_FIELDS, call_minimax_batch_evaluation_report


COMPARE_TARGETS = ["rule", "llm", "recommended"]
METRICS_CACHE_PREFIX = "batch_eval_metrics:"
METRICS_CACHE_TTL = 1800
REPORT_CACHE_PREFIX = "batch_eval_ai_report:"
REPORT_CACHE_TTL = 1800
_NORMALIZE_PATTERN = re.compile(r"[\s,.;:!?\-_/\\，。；：！？（）()《》【】\[\]、]+")
_FIELD_COLUMN_MAP = {
    "档号": "archive_no",
    "文号": "doc_no",
    "责任者": "responsible",
    "题名": "title",
    "日期": "date",
    "页数": "pages",
    "密级": "classification",
    "备注": "remarks",
}


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_value(value: Any) -> str:
    return _NORMALIZE_PATTERN.sub("", _coerce_text(value)).lower()


def _is_filled(value: Any) -> bool:
    return bool(_normalize_value(value))


def _safe_ratio(numerator: float, denominator: float, *, empty_default: float = 0.0) -> float:
    if denominator <= 0:
        return empty_default
    return round(numerator / denominator, 6)


def _pair_set(group_map: dict[str, list[int]], allowed_tasks: set[int]) -> set[tuple[int, int]]:
    result: set[tuple[int, int]] = set()
    for task_ids in group_map.values():
        filtered = sorted(task_id for task_id in task_ids if task_id in allowed_tasks)
        for left, right in itertools.combinations(filtered, 2):
            result.add((left, right))
    return result


def _mean(values: list[float]) -> float:
    if not values:
        return 0.0
    return round(sum(values) / len(values), 6)


def _truth_version(truth_data: dict[str, Any]) -> str:
    tasks = sorted(
        (
            {"task_id": int(item["task_id"]), "doc_key": str(item["doc_key"])}
            for item in truth_data.get("tasks", [])
            if _coerce_text(item.get("doc_key"))
        ),
        key=lambda item: (item["task_id"], item["doc_key"]),
    )
    documents = sorted(
        (
            {"doc_key": str(item["doc_key"]), "fields": {field: _coerce_text(item.get("fields", {}).get(field)) for field in ARCHIVE_FIELDS}}
            for item in truth_data.get("documents", [])
            if _coerce_text(item.get("doc_key"))
        ),
        key=lambda item: item["doc_key"],
    )
    if not tasks and not documents:
        return "none"
    raw = json.dumps({"tasks": tasks, "documents": documents}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


async def _load_valid_batch_task_ids(db: AsyncSession, batch_id: str) -> set[int]:
    stmt = select(ArchiveRecord.task_id).where(ArchiveRecord.batch_id == batch_id, ArchiveRecord.task_id.is_not(None))
    rows = (await db.execute(stmt)).scalars().all()
    return {int(task_id) for task_id in rows if task_id is not None}


def _truth_row_to_fields(row: BatchTruthDocumentField) -> dict[str, str]:
    return {
        field: _coerce_text(getattr(row, column))
        for field, column in _FIELD_COLUMN_MAP.items()
    }


async def get_batch_evaluation_truth(db: AsyncSession, *, batch_id: str) -> dict[str, Any]:
    task_rows = (
        await db.execute(
            select(BatchTruthTaskMap)
            .where(BatchTruthTaskMap.batch_id == batch_id)
            .order_by(BatchTruthTaskMap.task_id.asc())
        )
    ).scalars().all()
    document_rows = (
        await db.execute(
            select(BatchTruthDocumentField)
            .where(BatchTruthDocumentField.batch_id == batch_id)
            .order_by(BatchTruthDocumentField.doc_key.asc())
        )
    ).scalars().all()

    updated_times: list[datetime] = []
    updated_times.extend([row.updated_at for row in task_rows if row.updated_at])
    updated_times.extend([row.updated_at for row in document_rows if row.updated_at])
    truth_updated_at = max(updated_times).isoformat() if updated_times else None

    return {
        "batch_id": batch_id,
        "tasks": [{"task_id": int(row.task_id), "doc_key": row.doc_key} for row in task_rows],
        "documents": [{"doc_key": row.doc_key, "fields": _truth_row_to_fields(row)} for row in document_rows],
        "truth_updated_at": truth_updated_at,
    }


async def save_batch_evaluation_truth(
    db: AsyncSession,
    *,
    batch_id: str,
    tasks: list[dict[str, Any]],
    documents: list[dict[str, Any]],
) -> dict[str, Any]:
    valid_task_ids = await _load_valid_batch_task_ids(db, batch_id)

    normalized_tasks: list[dict[str, Any]] = []
    seen_task_ids: set[int] = set()
    for item in tasks:
        try:
            task_id = int(item.get("task_id"))
        except (TypeError, ValueError) as error:
            raise ValueError("Task mapping requires a numeric task_id.") from error
        doc_key = _coerce_text(item.get("doc_key"))
        if task_id not in valid_task_ids:
            raise ValueError(f"Task #{task_id} does not belong to batch {batch_id}.")
        if not doc_key:
            raise ValueError(f"Task #{task_id} requires a non-empty doc_key.")
        if task_id in seen_task_ids:
            continue
        seen_task_ids.add(task_id)
        normalized_tasks.append({"task_id": task_id, "doc_key": doc_key})

    normalized_documents: list[dict[str, Any]] = []
    seen_doc_keys: set[str] = set()
    for item in documents:
        doc_key = _coerce_text(item.get("doc_key"))
        if not doc_key:
            raise ValueError("Document truth requires a non-empty doc_key.")
        if doc_key in seen_doc_keys:
            continue
        seen_doc_keys.add(doc_key)
        fields = item.get("fields") or {}
        normalized_documents.append(
            {
                "doc_key": doc_key,
                "fields": {field: _coerce_text(fields.get(field)) for field in ARCHIVE_FIELDS},
            }
        )

    await db.execute(sa_delete(BatchTruthTaskMap).where(BatchTruthTaskMap.batch_id == batch_id))
    await db.execute(sa_delete(BatchTruthDocumentField).where(BatchTruthDocumentField.batch_id == batch_id))

    for item in normalized_tasks:
        db.add(
            BatchTruthTaskMap(
                batch_id=batch_id,
                task_id=item["task_id"],
                doc_key=item["doc_key"],
            )
        )

    for item in normalized_documents:
        row_kwargs = {
            "batch_id": batch_id,
            "doc_key": item["doc_key"],
        }
        for field, column in _FIELD_COLUMN_MAP.items():
            row_kwargs[column] = item["fields"].get(field, "")
        db.add(BatchTruthDocumentField(**row_kwargs))

    await db.commit()
    cache_delete_pattern(f"{METRICS_CACHE_PREFIX}{batch_id}:*")
    cache_delete_pattern(f"{REPORT_CACHE_PREFIX}{batch_id}:*")
    return await get_batch_evaluation_truth(db, batch_id=batch_id)


def _extract_target_fields(document: dict[str, Any], target: str) -> dict[str, Any]:
    if target == "rule":
        source = document.get("rule_fields") or {}
    elif target == "llm":
        source = document.get("llm_fields") or {}
    else:
        source = document.get("recommended_fields") or {}
    return {field: source.get(field, "") for field in ARCHIVE_FIELDS}


def _build_operational_metrics(merge_result: dict[str, Any]) -> dict[str, Any]:
    groups = merge_result.get("groups") or []
    documents = merge_result.get("documents") or []
    fields_total = max(len(documents) * len(ARCHIVE_FIELDS), 1)

    fill_rate: dict[str, float] = {}
    for target in COMPARE_TARGETS:
        filled = 0
        for document in documents:
            fields = _extract_target_fields(document, target)
            for field in ARCHIVE_FIELDS:
                if _is_filled(fields.get(field)):
                    filled += 1
        fill_rate[target] = _safe_ratio(filled, len(documents) * len(ARCHIVE_FIELDS), empty_default=0.0)

    agreement_values = []
    conflict_fields = 0
    for document in documents:
        agreement_ratio = document.get("agreement", {}).get("ratio")
        if isinstance(agreement_ratio, (int, float)):
            agreement_values.append(float(agreement_ratio))
        conflict_fields += len(document.get("conflicts") or {})

    confidence_values = [
        float(group.get("same_document_confidence", 0))
        for group in groups
        if isinstance(group.get("same_document_confidence"), (int, float))
    ]

    return {
        "documents_count": len(documents),
        "groups_count": len(groups),
        "avg_same_document_confidence": _mean(confidence_values),
        "avg_rule_llm_agreement": _mean(agreement_values),
        "conflict_fields": conflict_fields,
        "conflict_rate": _safe_ratio(conflict_fields, fields_total, empty_default=0.0),
        "field_fill_rate": fill_rate,
    }


def _build_truth_metrics(merge_result: dict[str, Any], truth_data: dict[str, Any]) -> dict[str, Any] | None:
    truth_tasks = truth_data.get("tasks") or []
    truth_documents = truth_data.get("documents") or []
    if not truth_tasks and not truth_documents:
        return None

    predicted_group_to_tasks: dict[str, list[int]] = {}
    predicted_task_to_group: dict[int, str] = {}
    for group in merge_result.get("groups", []):
        group_id = str(group.get("group_id"))
        task_ids = [int(task_id) for task_id in group.get("task_ids", [])]
        predicted_group_to_tasks[group_id] = task_ids
        for task_id in task_ids:
            predicted_task_to_group[task_id] = group_id

    truth_task_to_doc_key: dict[int, str] = {}
    truth_doc_to_tasks: dict[str, list[int]] = defaultdict(list)
    for item in truth_tasks:
        doc_key = _coerce_text(item.get("doc_key"))
        if not doc_key:
            continue
        task_id = int(item.get("task_id"))
        truth_task_to_doc_key[task_id] = doc_key
        truth_doc_to_tasks[doc_key].append(task_id)

    mapped_tasks = set(predicted_task_to_group.keys()) & set(truth_task_to_doc_key.keys())
    predicted_pairs = _pair_set(predicted_group_to_tasks, mapped_tasks)
    truth_pairs = _pair_set(truth_doc_to_tasks, mapped_tasks)
    true_positive_pairs = predicted_pairs & truth_pairs

    pairwise_precision = _safe_ratio(
        len(true_positive_pairs),
        len(predicted_pairs),
        empty_default=1.0 if not truth_pairs else 0.0,
    )
    pairwise_recall = _safe_ratio(len(true_positive_pairs), len(truth_pairs), empty_default=1.0)
    pairwise_f1 = (
        round(2 * pairwise_precision * pairwise_recall / (pairwise_precision + pairwise_recall), 6)
        if pairwise_precision + pairwise_recall > 0
        else 0.0
    )

    predicted_group_dominant_doc: dict[str, str] = {}
    assignment_total = 0
    assignment_correct = 0
    for group_id, task_ids in predicted_group_to_tasks.items():
        doc_keys = [truth_task_to_doc_key[task_id] for task_id in task_ids if task_id in truth_task_to_doc_key]
        if not doc_keys:
            continue
        dominant_doc, _ = sorted(Counter(doc_keys).items(), key=lambda item: (-item[1], item[0]))[0]
        predicted_group_dominant_doc[group_id] = dominant_doc
        for task_id in task_ids:
            if task_id not in truth_task_to_doc_key:
                continue
            assignment_total += 1
            if truth_task_to_doc_key[task_id] == dominant_doc:
                assignment_correct += 1

    truth_doc_fields = {
        str(item["doc_key"]): {field: _coerce_text(item.get("fields", {}).get(field)) for field in ARCHIVE_FIELDS}
        for item in truth_documents
        if _coerce_text(item.get("doc_key"))
    }

    field_stats = {
        target: {
            "total": 0,
            "correct": 0,
            "per_field_total": {field: 0 for field in ARCHIVE_FIELDS},
            "per_field_correct": {field: 0 for field in ARCHIVE_FIELDS},
            "compared_documents": 0,
        }
        for target in COMPARE_TARGETS
    }

    for document in merge_result.get("documents", []):
        group_id = _coerce_text(document.get("group_id"))
        doc_key = predicted_group_dominant_doc.get(group_id)
        if not doc_key:
            continue
        truth_fields = truth_doc_fields.get(doc_key)
        if not truth_fields:
            continue
        for target in COMPARE_TARGETS:
            predicted_fields = _extract_target_fields(document, target)
            field_stats[target]["compared_documents"] += 1
            for field in ARCHIVE_FIELDS:
                field_stats[target]["total"] += 1
                field_stats[target]["per_field_total"][field] += 1
                if _normalize_value(predicted_fields.get(field)) == _normalize_value(truth_fields.get(field)):
                    field_stats[target]["correct"] += 1
                    field_stats[target]["per_field_correct"][field] += 1

    field_accuracy = {}
    for target in COMPARE_TARGETS:
        total = field_stats[target]["total"]
        correct = field_stats[target]["correct"]
        per_field = {
            field: _safe_ratio(
                field_stats[target]["per_field_correct"][field],
                field_stats[target]["per_field_total"][field],
                empty_default=0.0,
            )
            for field in ARCHIVE_FIELDS
        }
        field_accuracy[target] = {
            "overall_accuracy": _safe_ratio(correct, total, empty_default=0.0),
            "correct": correct,
            "total": total,
            "compared_documents": field_stats[target]["compared_documents"],
            "per_field_accuracy": per_field,
        }

    return {
        "coverage": {
            "truth_task_count": len(truth_task_to_doc_key),
            "predicted_task_count": len(predicted_task_to_group),
            "mapped_task_count": len(mapped_tasks),
            "truth_document_count": len(truth_doc_fields),
            "mapped_document_count": len(set(predicted_group_dominant_doc.values())),
        },
        "grouping": {
            "pairwise_precision": pairwise_precision,
            "pairwise_recall": pairwise_recall,
            "pairwise_f1": pairwise_f1,
            "task_assignment_accuracy": _safe_ratio(assignment_correct, assignment_total, empty_default=0.0),
            "tp_pairs": len(true_positive_pairs),
            "predicted_pairs": len(predicted_pairs),
            "truth_pairs": len(truth_pairs),
        },
        "field_accuracy": field_accuracy,
    }


async def get_batch_evaluation_metrics(
    db: AsyncSession,
    *,
    batch_id: str,
    force_refresh: bool = False,
) -> dict[str, Any] | None:
    merge_result = await get_batch_merge_extract_result(
        db,
        batch_id=batch_id,
        include_evidence=True,
        force_refresh=force_refresh,
    )
    if not merge_result:
        return None

    truth_data = await get_batch_evaluation_truth(db, batch_id=batch_id)
    merge_version = _coerce_text(merge_result.get("generated_at")) or "none"
    truth_version = _truth_version(truth_data)
    cache_key = f"{METRICS_CACHE_PREFIX}{batch_id}:{merge_version}:{truth_version}"

    if not force_refresh:
        cached = cache_get(cache_key)
        if isinstance(cached, dict):
            return cached

    payload = {
        "batch_id": batch_id,
        "operational_metrics": _build_operational_metrics(merge_result),
        "truth_metrics": _build_truth_metrics(merge_result, truth_data),
        "compare_targets": list(COMPARE_TARGETS),
        "generated_at": merge_result.get("generated_at"),
        "truth_updated_at": truth_data.get("truth_updated_at"),
    }
    cache_set(cache_key, payload, METRICS_CACHE_TTL)
    return payload


async def get_batch_evaluation_ai_report(
    db: AsyncSession,
    *,
    batch_id: str,
    force_refresh: bool = False,
) -> dict[str, Any] | None:
    merge_result = await get_batch_merge_extract_result(
        db,
        batch_id=batch_id,
        include_evidence=False,
        force_refresh=force_refresh,
    )
    if not merge_result:
        return None

    truth_data = await get_batch_evaluation_truth(db, batch_id=batch_id)
    merge_version = _coerce_text(merge_result.get("generated_at")) or "none"
    truth_version = _truth_version(truth_data)
    cache_key = f"{REPORT_CACHE_PREFIX}{batch_id}:{merge_version}:{truth_version}"

    if not force_refresh:
        cached = cache_get(cache_key)
        if isinstance(cached, dict):
            return cached

    metrics_payload = await get_batch_evaluation_metrics(
        db,
        batch_id=batch_id,
        force_refresh=force_refresh,
    )
    if not metrics_payload:
        return None

    report = await call_minimax_batch_evaluation_report(
        batch_id=batch_id,
        merge_result=merge_result,
        metrics=metrics_payload,
    )

    payload = {
        "batch_id": batch_id,
        "summary": report["summary"],
        "strengths": report["strengths"],
        "risks": report["risks"],
        "recommendations": report["recommendations"],
        "provider": report["provider"],
        "model": report["model"],
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "raw_usage": report["raw_usage"],
    }
    cache_set(cache_key, payload, REPORT_CACHE_TTL)
    return payload
