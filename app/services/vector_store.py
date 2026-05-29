"""Archive-record retrieval adapter used by the hierarchical agent workflow.

Supports two retrieval modes:
1. **Semantic search** (primary) \u2014 pgvector cosine similarity via embedding column
2. **Lexical search** (fallback) \u2014 token overlap + fuzzy matching

The system automatically degrades to lexical search when:
- Embedding service is unavailable
- pgvector extension is not installed
- Records lack embeddings
"""

from __future__ import annotations

from difflib import SequenceMatcher
import logging
import re
from typing import Any

from sqlalchemy import select, text as sql_text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import async_session
from app.db.models import ArchiveRecord

logger = logging.getLogger(__name__)

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
    """
    语义相似度检索 — 优先使用 pgvector，降级到词法匹配。

    Args:
        query: 检索查询文本
        k: 返回 top-k 结果
        db: 可选的数据库 session
        exclude_batch_id: 排除指定批次的记录

    Returns:
        按相似度降序排列的记录列表
    """
    query = str(query or "").strip()
    if not query:
        return []

    own_session = db is None
    session_cm = async_session() if own_session else None
    session = await session_cm.__aenter__() if session_cm is not None else db
    assert session is not None

    try:
        # 尝试语义检索
        result = await _semantic_search(query, k=k, db=session, exclude_batch_id=exclude_batch_id)
        if result is not None:
            return result

        # 降级到词法匹配
        logger.debug("Falling back to lexical search for query: %s", query[:50])
        return await _lexical_search(query, k=k, db=session, exclude_batch_id=exclude_batch_id)
    finally:
        if session_cm is not None:
            await session_cm.__aexit__(None, None, None)


async def _semantic_search(
    query: str,
    *,
    k: int,
    db: AsyncSession,
    exclude_batch_id: str,
) -> list[dict[str, Any]] | None:
    """pgvector 语义检索 — 返回 None 表示不可用，应降级"""
    from app.services.embedding_service import embed_single, is_embedding_available

    if not is_embedding_available():
        return None

    try:
        query_vec = await embed_single(query)
    except Exception as exc:
        logger.warning("Embedding failed, degrading to lexical: %s", exc)
        return None

    if query_vec is None:
        return None

    # 使用 pgvector cosine distance 运算符
    try:
        # 构建原始 SQL — pgvector 的 <=> 运算符
        vec_literal = "[" + ",".join(str(v) for v in query_vec) + "]"
        where_clause = ""
        if exclude_batch_id:
            where_clause = f"AND (batch_id IS NULL OR batch_id != :exclude_batch_id)"

        raw_sql = sql_text(f"""
            SELECT id, task_id, batch_id, archive_no, doc_no, responsible,
                   title, date, pages, classification, remarks,
                   1 - (embedding <=> :query_vec::vector) AS score
            FROM archive_records
            WHERE embedding IS NOT NULL {where_clause}
            ORDER BY embedding <=> :query_vec::vector
            LIMIT :k
        """)

        params: dict[str, Any] = {"query_vec": vec_literal, "k": k}
        if exclude_batch_id:
            params["exclude_batch_id"] = exclude_batch_id

        result = await db.execute(raw_sql, params)
        rows = result.fetchall()

        if not rows:
            # 没有带 embedding 的记录，降级
            return None

        return [
            {
                "id": row.id,
                "task_id": int(row.task_id) if row.task_id is not None else None,
                "batch_id": str(row.batch_id or ""),
                "archive_no": str(row.archive_no or ""),
                "doc_no": str(row.doc_no or ""),
                "responsible": str(row.responsible or ""),
                "title": str(row.title or ""),
                "date": str(row.date or ""),
                "pages": str(row.pages or ""),
                "classification": str(row.classification or ""),
                "remarks": str(row.remarks or ""),
                "score": float(row.score) if row.score is not None else 0.0,
            }
            for row in rows
        ]
    except Exception as exc:
        # pgvector 扩展未安装或其他 DB 错误 — 降级
        logger.debug("pgvector search failed, degrading to lexical: %s", exc)
        return None


async def _lexical_search(
    query: str,
    *,
    k: int,
    db: AsyncSession,
    exclude_batch_id: str,
) -> list[dict[str, Any]]:
    """词法匹配降级路径 — 与原始实现相同"""
    stmt = select(ArchiveRecord).order_by(ArchiveRecord.created_at.desc()).limit(max(k * 25, 100))
    if exclude_batch_id:
        stmt = stmt.where((ArchiveRecord.batch_id.is_(None)) | (ArchiveRecord.batch_id != exclude_batch_id))

    records = (await db.execute(stmt)).scalars().all()
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
