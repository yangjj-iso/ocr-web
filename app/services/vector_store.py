"""Archive-record retrieval adapter used by the hierarchical agent workflow.

This is a lightweight compatibility layer that exposes a ``similarity_search``
API even when a dedicated vector database is not yet wired in. The current
implementation falls back to lexical scoring over ``archive_records`` so the
workflow can already consume historical few-shot examples.
"""

from __future__ import annotations

from difflib import SequenceMatcher
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session
from app.db.models import ArchiveRecord

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9\u4e00-\u9fff]+")


def _tokenize(text: str) -> list[str]:
    return [token.lower() for token in _TOKEN_PATTERN.findall(str(text or "")) if token.strip()]


def _record_text(record: ArchiveRecord) -> str:
    return " ".join(
        [
            str(record.archive_no or ""),
            str(record.doc_no or ""),
            str(record.responsible or ""),
            str(record.title or ""),
            str(record.date or ""),
            str(record.pages or ""),
            str(record.classification or ""),
            str(record.remarks or ""),
        ]
    ).strip()


def _score_record(query: str, record_text: str) -> float:
    query_tokens = set(_tokenize(query))
    if not query_tokens:
        return 0.0
    record_tokens = set(_tokenize(record_text))
    overlap = len(query_tokens & record_tokens) / max(len(query_tokens), 1)
    fuzzy = SequenceMatcher(None, query.lower(), record_text.lower()).ratio()
    return round((overlap * 0.7) + (fuzzy * 0.3), 6)


def _record_payload(record: ArchiveRecord, score: float) -> dict[str, Any]:
    return {
        "id": int(record.id),
        "task_id": int(record.task_id) if record.task_id is not None else None,
        "batch_id": str(record.batch_id or ""),
        "archive_no": str(record.archive_no or ""),
        "doc_no": str(record.doc_no or ""),
        "responsible": str(record.responsible or ""),
        "title": str(record.title or ""),
        "date": str(record.date or ""),
        "pages": str(record.pages or ""),
        "classification": str(record.classification or ""),
        "remarks": str(record.remarks or ""),
        "score": float(score),
    }


async def similarity_search(
    query: str,
    *,
    k: int = 4,
    db: AsyncSession | None = None,
    exclude_batch_id: str = "",
) -> list[dict[str, Any]]:
    query = str(query or "").strip()
    if not query:
        return []

    own_session = db is None
    session_cm = async_session() if own_session else None
    session = await session_cm.__aenter__() if session_cm is not None else db
    assert session is not None

    try:
        stmt = select(ArchiveRecord).order_by(ArchiveRecord.created_at.desc()).limit(max(k * 25, 100))
        if exclude_batch_id:
            stmt = stmt.where((ArchiveRecord.batch_id.is_(None)) | (ArchiveRecord.batch_id != exclude_batch_id))

        records = (await session.execute(stmt)).scalars().all()
        scored = []
        for record in records:
            text = _record_text(record)
            if not text:
                continue
            score = _score_record(query, text)
            if score <= 0:
                continue
            scored.append(_record_payload(record, score))

        scored.sort(key=lambda item: (-float(item["score"]), -int(item["id"])))
        return scored[:k]
    finally:
        if session_cm is not None:
            await session_cm.__aexit__(None, None, None)
