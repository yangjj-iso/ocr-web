import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis_cache import cache_get, cache_set
from app.db.models import ArchiveRecord, BatchQAFeedback, BatchQARecord, OCRTask
from app.services.excel_export import extract_fields
from app.services.llm_field_extraction_service import (
    call_minimax_batch_qa_answer,
    call_minimax_batch_qa_support_check,
)


BATCH_QA_CACHE_PREFIX = "batch_qa:"
BATCH_QA_CACHE_TTL = 900
DEFAULT_CHUNK_SIZE = 600
DEFAULT_CHUNK_OVERLAP = 120
SNIPPET_MAX_CHARS = 240
DEFAULT_TOP_K = 8
LOW_EVIDENCE_REJECT_THRESHOLD = 0.12
QA_RATINGS = {"helpful", "not_helpful"}

_ASCII_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")
_CJK_SEQUENCE_PATTERN = re.compile(r"[\u4e00-\u9fff]+")
# Keep Chinese and alphanumeric characters; strip separators/punctuation.
# This avoids wiping CJK queries during normalization.
_NORMALIZE_PATTERN = re.compile(r"[^\w\u4e00-\u9fff]+", re.UNICODE)
_QUERY_FILLER_TERMS = (
    "这一批",
    "这批",
    "本批",
    "材料",
    "文件",
    "文档",
    "内容",
    "里面",
    "其中",
    "主要",
    "涉及",
    "请问",
    "一下",
    "是否",
    "有无",
    "有没有",
    "哪些",
    "哪个",
    "什么",
    "怎么",
    "如何",
    "时候",
    "情况",
    "信息",
    "告诉我",
    "帮我",
)
_QUERY_JOINER_TERMS = ("以及", "或者", "并且", "和", "与", "及", "或")
MAX_EVIDENCE_PER_TASK = 2


@dataclass(slots=True)
class QATaskCandidate:
    task_id: int
    filename: str
    full_text: str
    metadata_text: str
    updated_at: datetime | None


@dataclass(slots=True)
class EvidenceChunk:
    task_id: int
    filename: str
    chunk_index: int
    text: str
    score: float
    keyword_hits: int
    phrase_hit: int
    metadata_hits: int


def _coerce_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _normalize_text(text: str) -> str:
    return _NORMALIZE_PATTERN.sub("", _coerce_text(text)).lower()


def _dedupe_preserve_order(tokens: list[str]) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for token in tokens:
        if not token or token in seen:
            continue
        seen.add(token)
        deduped.append(token)
    return deduped


def _expand_cjk_query_terms(sequence: str) -> list[str]:
    cleaned = _normalize_text(sequence)
    if not cleaned:
        return []

    for filler in _QUERY_FILLER_TERMS:
        cleaned = cleaned.replace(filler, " ")
    for joiner in _QUERY_JOINER_TERMS:
        cleaned = cleaned.replace(joiner, " ")

    parts = [part.strip() for part in cleaned.split() if len(part.strip()) >= 2]
    if not parts and len(cleaned) >= 2:
        parts = [cleaned]

    terms: list[str] = []
    for part in parts:
        terms.append(part)
        if len(part) >= 4:
            for size in range(min(4, len(part) - 1), 1, -1):
                terms.append(part[:size])
                terms.append(part[-size:])
    return _dedupe_preserve_order(terms)


def _tokenize_query(question: str) -> list[str]:
    body = _coerce_text(question)
    if not body:
        return []

    tokens: list[str] = []
    for token in _ASCII_TOKEN_PATTERN.findall(body):
        normalized = token.lower()
        if len(normalized) >= 2 or normalized.isdigit():
            tokens.append(normalized)

    for sequence in _CJK_SEQUENCE_PATTERN.findall(body):
        tokens.extend(_expand_cjk_query_terms(sequence))

    return _dedupe_preserve_order(tokens)


def split_text_chunks(
    text: str,
    *,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> list[str]:
    body = _coerce_text(text)
    if not body:
        return []

    paragraph_candidates = [part.strip() for part in re.split(r"\n\s*\n+", body) if part.strip()]
    if not paragraph_candidates:
        paragraph_candidates = [line.strip() for line in body.splitlines() if line.strip()]
    if not paragraph_candidates:
        paragraph_candidates = [body]

    step = max(1, chunk_size - min(overlap, chunk_size - 1))
    chunks: list[str] = []

    for paragraph in paragraph_candidates:
        if len(paragraph) <= chunk_size:
            chunks.append(paragraph)
            continue
        for start in range(0, len(paragraph), step):
            piece = paragraph[start : start + chunk_size].strip()
            if piece:
                chunks.append(piece)
            if start + chunk_size >= len(paragraph):
                break

    return chunks


def _build_evidence_snippet(text: str, query_terms: list[str], *, max_chars: int = SNIPPET_MAX_CHARS) -> str:
    clean = re.sub(r"\s+", " ", _coerce_text(text)).strip()
    if len(clean) <= max_chars:
        return clean

    lowered = clean.lower()
    pivot = -1
    for term in sorted(query_terms, key=len, reverse=True):
        hit = lowered.find(term.lower())
        if hit != -1:
            pivot = hit
            break

    if pivot == -1:
        return f"{clean[:max_chars]}..."

    start = max(0, pivot - max_chars // 2)
    end = min(len(clean), start + max_chars)
    if end - start < max_chars:
        start = max(0, end - max_chars)
    snippet = clean[start:end]
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(clean) else ""
    return f"{prefix}{snippet}{suffix}"


def _term_weight(term: str) -> float:
    if not term:
        return 0.0
    if _ASCII_TOKEN_PATTERN.fullmatch(term):
        if term.isdigit():
            return 1.0 if len(term) >= 4 else 0.6
        return min(2.0, 0.6 + (len(term) * 0.18))
    return min(2.6, 0.45 + (len(term) * 0.35))


def _score_chunk(chunk_text: str, metadata_text: str, query_terms: list[str], normalized_question: str) -> tuple[float, int, int, int]:
    normalized_chunk = _normalize_text(chunk_text)
    normalized_meta = _normalize_text(metadata_text)
    if not normalized_chunk:
        return 0.0, 0, 0, 0
    if not query_terms:
        return 0.0, 0, 0, 0

    matched_terms = [term for term in query_terms if term and term in normalized_chunk]
    matched_meta_terms = [term for term in query_terms if term and term in normalized_meta]
    keyword_hits = len(matched_terms)
    metadata_hits = len(matched_meta_terms)

    long_phrase_terms = [term for term in query_terms if len(term) >= 4]
    phrase_hit = int(
        bool(
            (normalized_question and len(normalized_question) <= 32 and normalized_question in normalized_chunk)
            or any(term in normalized_chunk for term in long_phrase_terms)
        )
    )

    total_weight = max(sum(_term_weight(term) for term in query_terms), 1.0)
    keyword_score = sum(_term_weight(term) for term in matched_terms) / total_weight
    metadata_score = sum(_term_weight(term) for term in matched_meta_terms) / total_weight
    score = min(1.0, (keyword_score * 0.55) + (phrase_hit * 0.25) + (metadata_score * 0.2))
    return round(score, 6), keyword_hits, phrase_hit, metadata_hits


def build_ranked_evidence(candidates: list[QATaskCandidate], question: str, *, top_k: int) -> list[dict[str, Any]]:
    query_terms = _tokenize_query(question)
    normalized_question = _normalize_text(question)
    chunks: list[EvidenceChunk] = []

    for candidate in candidates:
        for chunk_index, chunk_text in enumerate(split_text_chunks(candidate.full_text)):
            score, keyword_hits, phrase_hit, metadata_hits = _score_chunk(
                chunk_text,
                candidate.metadata_text,
                query_terms,
                normalized_question,
            )
            chunks.append(
                EvidenceChunk(
                    task_id=candidate.task_id,
                    filename=candidate.filename,
                    chunk_index=chunk_index,
                    text=chunk_text,
                    score=score,
                    keyword_hits=keyword_hits,
                    phrase_hit=phrase_hit,
                    metadata_hits=metadata_hits,
                )
            )

    if not chunks:
        return []

    ranked = sorted(
        chunks,
        key=lambda item: (
            -item.score,
            -item.phrase_hit,
            -item.keyword_hits,
            -item.metadata_hits,
            item.task_id,
            item.chunk_index,
        ),
    )

    positive = [item for item in ranked if item.score > 0]
    pool = positive if positive else ranked

    selected: list[EvidenceChunk] = []
    per_task_count: dict[int, int] = defaultdict(int)
    for item in pool:
        if per_task_count[item.task_id] >= MAX_EVIDENCE_PER_TASK:
            continue
        selected.append(item)
        per_task_count[item.task_id] += 1
        if len(selected) >= top_k:
            break

    if len(selected) < min(top_k, len(pool)):
        selected_ids = {(item.task_id, item.chunk_index) for item in selected}
        for item in pool:
            key = (item.task_id, item.chunk_index)
            if key in selected_ids:
                continue
            selected.append(item)
            if len(selected) >= top_k:
                break

    return [
        {
            "task_id": item.task_id,
            "filename": item.filename,
            "snippet": _build_evidence_snippet(item.text, query_terms),
            "score": item.score,
        }
        for item in selected
    ]


async def _load_batch_candidates(db: AsyncSession, batch_id: str) -> list[QATaskCandidate]:
    stmt = (
        select(OCRTask)
        .join(ArchiveRecord, ArchiveRecord.task_id == OCRTask.id)
        .where(
            ArchiveRecord.batch_id == batch_id,
            OCRTask.status == "done",
            OCRTask.full_text.is_not(None),
        )
        .order_by(OCRTask.created_at.asc(), OCRTask.id.asc())
    )
    rows = (await db.execute(stmt)).scalars().all()

    candidates: list[QATaskCandidate] = []
    seen: set[int] = set()
    for task in rows:
        if task.id in seen:
            continue
        seen.add(task.id)

        full_text = _coerce_text(task.full_text)
        if not full_text:
            continue

        fields = extract_fields(task.filename, full_text, task.result_json, task.page_count)
        metadata_text = " ".join(
            [
                _coerce_text(task.filename),
                _coerce_text(fields.get("题名")),
                _coerce_text(fields.get("文号")),
            ]
        ).strip()
        candidates.append(
            QATaskCandidate(
                task_id=task.id,
                filename=task.filename,
                full_text=full_text,
                metadata_text=metadata_text,
                updated_at=task.updated_at,
            )
        )

    return candidates


def _build_merge_version(candidates: list[QATaskCandidate]) -> str:
    if not candidates:
        return "none"
    digest_payload = [
        {
            "task_id": candidate.task_id,
            "updated_at": candidate.updated_at.isoformat() if candidate.updated_at else "",
            "text_len": len(candidate.full_text),
        }
        for candidate in candidates
    ]
    raw = json.dumps(digest_payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def _build_cache_key(batch_id: str, question: str, top_k: int, merge_version: str) -> str:
    question_hash = hashlib.sha1(question.encode("utf-8")).hexdigest()[:16]
    return f"{BATCH_QA_CACHE_PREFIX}{batch_id}:{merge_version}:{question_hash}:{top_k}"


def _merge_usage(total: dict[str, Any], *usages: dict[str, Any]) -> None:
    for usage in usages:
        for key, value in (usage or {}).items():
            if isinstance(value, (int, float)):
                total[key] = total.get(key, 0) + value
            elif key not in total:
                total[key] = value


def _build_citations(citation_indexes: list[int], evidence_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    for evidence_index in citation_indexes:
        index = int(evidence_index) - 1
        if index < 0 or index >= len(evidence_items):
            continue
        evidence = evidence_items[index]
        citations.append(
            {
                "evidence_index": evidence_index,
                "task_id": int(evidence.get("task_id", 0) or 0),
                "filename": _coerce_text(evidence.get("filename")),
            }
        )
    return citations


def _insufficient_answer(prefix: str = "无法确认") -> str:
    return f"{prefix}：当前批次证据不足以支撑可靠结论。"


def _serialize_feedback(feedback: BatchQAFeedback | None) -> dict[str, Any] | None:
    if not feedback:
        return None
    return {
        "rating": feedback.rating,
        "reason": feedback.reason,
        "comment": feedback.comment,
        "corrected_answer": feedback.corrected_answer,
        "corrected_evidence": feedback.corrected_evidence_json or [],
        "created_at": feedback.created_at.isoformat() if feedback.created_at else None,
        "updated_at": feedback.updated_at.isoformat() if feedback.updated_at else None,
    }


def _serialize_qa_record(row: BatchQARecord, feedback: BatchQAFeedback | None = None) -> dict[str, Any]:
    return {
        "qa_id": row.id,
        "batch_id": row.batch_id,
        "question": row.question,
        "answer": row.answer,
        "evidence": row.evidence_json or [],
        "support_level": row.support_level or "insufficient",
        "confidence": float(row.confidence or 0),
        "citations": row.citations_json or [],
        "provider": row.provider,
        "model": row.model,
        "raw_usage": row.raw_usage or {},
        "generated_at": row.generated_at.isoformat() if row.generated_at else None,
        "feedback": _serialize_feedback(feedback),
    }


async def _persist_qa_record(db: AsyncSession, payload: dict[str, Any]) -> int:
    row = BatchQARecord(
        batch_id=payload["batch_id"],
        question=payload["question"],
        answer=payload["answer"],
        evidence_json=payload.get("evidence") or [],
        provider=payload.get("provider") or "minimax",
        model=payload.get("model") or "",
        raw_usage=payload.get("raw_usage") or {},
        support_level=payload.get("support_level") or "insufficient",
        confidence=float(payload.get("confidence") or 0),
        citations_json=payload.get("citations") or [],
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return int(row.id)


def _build_insufficient_payload(batch_id: str, question: str, evidence: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "batch_id": batch_id,
        "question": question,
        "answer": _insufficient_answer(),
        "evidence": evidence,
        "qa_id": None,
        "support_level": "insufficient",
        "confidence": 0.0,
        "citations": [],
        "provider": "retrieval",
        "model": "hybrid-retrieval-v1",
        "raw_usage": {},
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def answer_batch_question(
    db: AsyncSession,
    *,
    batch_id: str,
    question: str,
    top_k: int = DEFAULT_TOP_K,
    persist: bool = True,
) -> dict[str, Any] | None:
    clean_question = _coerce_text(question)
    if not clean_question:
        raise ValueError("question must not be empty.")

    candidates = await _load_batch_candidates(db, batch_id)
    if not candidates:
        return None

    merge_version = _build_merge_version(candidates)
    cache_key = _build_cache_key(batch_id, clean_question, top_k, merge_version)
    cached = cache_get(cache_key)
    if isinstance(cached, dict):
        payload = dict(cached)
        if persist and not payload.get("qa_id"):
            qa_id = await _persist_qa_record(db, payload)
            payload["qa_id"] = qa_id
            cache_set(cache_key, payload, BATCH_QA_CACHE_TTL)
        return payload

    evidence = build_ranked_evidence(candidates, clean_question, top_k=top_k)
    if not evidence:
        return None

    if float(evidence[0].get("score") or 0) < LOW_EVIDENCE_REJECT_THRESHOLD:
        payload = _build_insufficient_payload(batch_id, clean_question, evidence)
        if persist:
            payload["qa_id"] = await _persist_qa_record(db, payload)
        cache_set(cache_key, payload, BATCH_QA_CACHE_TTL)
        return payload

    llm_response = await call_minimax_batch_qa_answer(
        batch_id=batch_id,
        question=clean_question,
        evidence_items=evidence,
    )
    support_check = await call_minimax_batch_qa_support_check(
        question=clean_question,
        answer=llm_response["answer"],
        evidence_items=evidence,
    )

    support_level = _coerce_text(support_check.get("support_level")).lower() or "insufficient"
    confidence = float(support_check.get("confidence") or 0)
    citations = _build_citations(llm_response.get("citations") or [], evidence)
    answer = _coerce_text(llm_response.get("answer"))

    if support_level == "insufficient":
        answer = _insufficient_answer()
        citations = []

    raw_usage: dict[str, Any] = {}
    _merge_usage(raw_usage, llm_response.get("raw_usage") or {}, support_check.get("raw_usage") or {})

    payload = {
        "batch_id": batch_id,
        "question": clean_question,
        "answer": answer or _insufficient_answer(),
        "evidence": evidence,
        "qa_id": None,
        "support_level": support_level if support_level in {"supported", "partial", "insufficient"} else "insufficient",
        "confidence": min(1.0, max(0.0, confidence)),
        "citations": citations,
        "provider": llm_response.get("provider") or "minimax",
        "model": llm_response.get("model") or "",
        "raw_usage": raw_usage,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    if persist:
        payload["qa_id"] = await _persist_qa_record(db, payload)

    cache_set(cache_key, payload, BATCH_QA_CACHE_TTL)
    return payload


async def get_batch_qa_history(
    db: AsyncSession,
    *,
    batch_id: str,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    page = max(page, 1)
    page_size = max(1, min(page_size, 100))
    offset = (page - 1) * page_size

    total = int(
        (
            await db.execute(
                select(func.count(BatchQARecord.id)).where(BatchQARecord.batch_id == batch_id)
            )
        ).scalar()
        or 0
    )
    if total == 0:
        return {
            "batch_id": batch_id,
            "total": 0,
            "page": page,
            "page_size": page_size,
            "items": [],
        }

    rows = (
        await db.execute(
            select(BatchQARecord)
            .where(BatchQARecord.batch_id == batch_id)
            .order_by(BatchQARecord.generated_at.desc(), BatchQARecord.id.desc())
            .offset(offset)
            .limit(page_size)
        )
    ).scalars().all()
    qa_ids = [row.id for row in rows]

    feedback_map: dict[int, BatchQAFeedback] = {}
    if qa_ids:
        feedback_rows = (
            await db.execute(
                select(BatchQAFeedback).where(
                    BatchQAFeedback.batch_id == batch_id,
                    BatchQAFeedback.qa_record_id.in_(qa_ids),
                )
            )
        ).scalars().all()
        feedback_map = {int(row.qa_record_id): row for row in feedback_rows}

    return {
        "batch_id": batch_id,
        "total": total,
        "page": page,
        "page_size": page_size,
        "items": [_serialize_qa_record(row, feedback_map.get(int(row.id))) for row in rows],
    }


async def submit_batch_qa_feedback(
    db: AsyncSession,
    *,
    batch_id: str,
    qa_id: int,
    rating: str,
    reason: str | None = None,
    comment: str | None = None,
    corrected_answer: str | None = None,
    corrected_evidence: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    normalized_rating = _coerce_text(rating).lower()
    if normalized_rating not in QA_RATINGS:
        raise ValueError("rating must be either helpful or not_helpful.")

    clean_reason = _coerce_text(reason)
    if normalized_rating == "not_helpful" and not clean_reason:
        raise ValueError("reason is required when rating is not_helpful.")

    qa_row = (
        await db.execute(
            select(BatchQARecord).where(
                BatchQARecord.id == qa_id,
                BatchQARecord.batch_id == batch_id,
            )
        )
    ).scalar_one_or_none()
    if not qa_row:
        return None

    corrected = corrected_evidence if isinstance(corrected_evidence, list) else []
    existing = (
        await db.execute(
            select(BatchQAFeedback).where(
                BatchQAFeedback.batch_id == batch_id,
                BatchQAFeedback.qa_record_id == qa_id,
            )
        )
    ).scalar_one_or_none()

    if existing:
        existing.rating = normalized_rating
        existing.reason = clean_reason or None
        existing.comment = _coerce_text(comment) or None
        existing.corrected_answer = _coerce_text(corrected_answer) or None
        existing.corrected_evidence_json = corrected
        row = existing
    else:
        row = BatchQAFeedback(
            batch_id=batch_id,
            qa_record_id=qa_id,
            rating=normalized_rating,
            reason=clean_reason or None,
            comment=_coerce_text(comment) or None,
            corrected_answer=_coerce_text(corrected_answer) or None,
            corrected_evidence_json=corrected,
        )
        db.add(row)

    await db.commit()
    await db.refresh(row)
    return {
        "batch_id": batch_id,
        "qa_id": qa_id,
        "feedback": _serialize_feedback(row),
    }


async def get_batch_qa_metrics(db: AsyncSession, *, batch_id: str) -> dict[str, Any]:
    total_answers = int(
        (
            await db.execute(
                select(func.count(BatchQARecord.id)).where(BatchQARecord.batch_id == batch_id)
            )
        ).scalar()
        or 0
    )
    insufficient_count = int(
        (
            await db.execute(
                select(func.count(BatchQARecord.id)).where(
                    BatchQARecord.batch_id == batch_id,
                    BatchQARecord.support_level == "insufficient",
                )
            )
        ).scalar()
        or 0
    )

    feedback_rows = (
        await db.execute(
            select(BatchQAFeedback).where(BatchQAFeedback.batch_id == batch_id)
        )
    ).scalars().all()
    feedback_count = len(feedback_rows)
    helpful_count = sum(1 for row in feedback_rows if row.rating == "helpful")
    helpful_rate = round(helpful_count / feedback_count, 6) if feedback_count else 0.0
    insufficient_rate = round(insufficient_count / total_answers, 6) if total_answers else 0.0

    today = datetime.now(timezone.utc).date()
    start_day = today - timedelta(days=6)
    trend_map: dict[str, dict[str, int]] = {
        (start_day + timedelta(days=offset)).isoformat(): {"feedback_count": 0, "helpful_count": 0}
        for offset in range(7)
    }
    for row in feedback_rows:
        if not row.updated_at:
            continue
        day_key = row.updated_at.date().isoformat()
        bucket = trend_map.get(day_key)
        if not bucket:
            continue
        bucket["feedback_count"] += 1
        if row.rating == "helpful":
            bucket["helpful_count"] += 1

    recent_trend = []
    for day in sorted(trend_map.keys()):
        bucket = trend_map[day]
        feedback_total = bucket["feedback_count"]
        day_helpful_rate = round(bucket["helpful_count"] / feedback_total, 6) if feedback_total else 0.0
        recent_trend.append(
            {
                "date": day,
                "feedback_count": feedback_total,
                "helpful_count": bucket["helpful_count"],
                "helpful_rate": day_helpful_rate,
            }
        )

    return {
        "batch_id": batch_id,
        "helpful_rate": helpful_rate,
        "insufficient_rate": insufficient_rate,
        "feedback_count": feedback_count,
        "recent_trend": recent_trend,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
