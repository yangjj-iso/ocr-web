"""
Draft Pipeline Domain — 草稿轨处理服务。

Develop.md §6（双轨分流 - Draft 轨）和 §10（自动著录与标签）。

负责：
1. 草稿字段提取（rules-first 策略）
2. 四类标签生成（文种/主题/状态/风险）
3. 草稿卷内目录生成（件级目录）
4. 质量评分计算并写入 DocVersion
5. 持久化 DocUnit + DocVersion 到 PostgreSQL
6. 将产物路径记录到 ArtifactFile
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 字段提取（混合策略：规则优先 + 候选填充）Develop.md §10
# ---------------------------------------------------------------------------

_PRESERVATION_KEYWORDS = {
    "永久": "permanent",
    "长期": "long_term",
    "30年": "30y",
    "10年": "10y",
    "短期": "short_term",
    "临时": "temp",
}


def extract_draft_metadata(
    doc: dict[str, Any],
    pages: list[dict[str, Any]],
    policy_rules: dict[str, Any],
) -> dict[str, Any]:
    """
    提取草稿件著录字段（Develop.md §10 混合策略）。

    规则优先字段：date / doc_no / page_count / 固定格式字段
    候选优先字段：title / responsible_party
    人工兜底：多候选冲突标记 needs_review=True
    """
    page_ids = doc.get("page_ids") or []
    doc_pages = [p for p in pages if p.get("page_id") in set(page_ids)]
    first_page = doc_pages[0] if doc_pages else {}

    candidates = first_page.get("candidates") or {}
    dates: list[str] = candidates.get("dates", [])
    doc_nos: list[str] = candidates.get("doc_nos", [])
    title_lines: list[str] = candidates.get("title_lines", [])

    # 日期：规则优先取第一个，多候选标记需审核
    date_val = dates[0] if dates else ""
    date_needs_review = len(dates) > 1

    # 文号：规则优先取第一个
    doc_no_val = doc_nos[0] if doc_nos else ""

    # 题名：候选优先取最长行（更完整）
    title_val = max(title_lines, key=len) if title_lines else ""
    title_needs_review = not title_val

    # 页数：从分件结果推算
    page_count = len(page_ids)

    # 保存期限：走规则自动判定 (Develop.md §12 业务共识)
    preservation_period = _infer_preservation_period(
        doc.get("doc_type_guess", ""), title_val, policy_rules, doc_no=doc_no_val
    )

    return {
        "title": title_val,
        "date": date_val,
        "doc_no": doc_no_val,
        "page_count": page_count,
        "preservation_period": preservation_period,
        "responsible_party": "",  # 人工兜底
        "_needs_review": date_needs_review or title_needs_review,
        "_candidates_raw": candidates,
    }


# Opt 3：doc_no 前缀 → 保存期限的默认映射（业务约定）
_DOC_NO_PREFIX_PERIOD: dict[str, str] = {
    "国办发": "permanent",
    "国发": "permanent",
    "国函": "long_term",
    "厅字": "long_term",
    "委发": "long_term",
    "通知": "10y",
    "备案": "10y",
}


def _infer_preservation_period(
    doc_type: str,
    title: str,
    policy_rules: dict[str, Any],
    doc_no: str = "",
) -> str:
    """
    基于规则快照自动判定保存期限（Develop.md §12 业务共识）。

    Opt 3：优先匹配 policy_rules.doc_no_period_rules（文号前缀 → 期限），
    其次走关键字匹配，最后回退 pending_review。
    """
    rules = (policy_rules or {}).get("preservation_rules", {})
    combined = f"{doc_type} {title}".lower()

    # Opt 3a：policy_rules 中配置的文号前缀规则优先
    doc_no_rules: dict[str, str] = (policy_rules or {}).get(
        "doc_no_period_rules", {}
    )
    merged_prefix_rules = {**_DOC_NO_PREFIX_PERIOD, **doc_no_rules}  # policy 覆盖默认
    for prefix, period in merged_prefix_rules.items():
        if doc_no.startswith(prefix):
            return period

    # Opt 3b：通用关键字匹配（题名 / 文种）
    for keyword, period in _PRESERVATION_KEYWORDS.items():
        if keyword in combined:
            return period

    # Opt 3c：policy_rules.preservation_rules 兜底
    for doc_type_key, period in rules.items():
        if doc_type_key.lower() in combined:
            return period

    return "pending_review"


# ---------------------------------------------------------------------------
# 标签生成（Develop.md §10 四类标签）
# ---------------------------------------------------------------------------

_DOC_KIND_KEYWORDS: dict[str, list[str]] = {
    "通知": ["通知", "公告"],
    "请示": ["请示", "请求"],
    "报告": ["报告", "汇报"],
    "批复": ["批复", "批准", "同意"],
    "决定": ["决定", "决议"],
    "函": ["函", "复函"],
}

_RISK_KEYWORDS = ["紧急", "保密", "秘密", "机密", "绝密", "退回", "撤销"]


def generate_draft_tags(
    doc: dict[str, Any],
    pages: list[dict[str, Any]],
) -> list[str]:
    """
    生成四类标签（Develop.md §10，§12）：
      文种标签 / 主题标签 / 状态标签 / 风险标签
    """
    page_ids = doc.get("page_ids") or []
    combined_text = ""
    for p in pages:
        if p.get("page_id") in set(page_ids):
            combined_text += (p.get("ocr_text") or "") + " "

    tags: list[str] = []

    # 1. 文种标签
    for doc_kind, keywords in _DOC_KIND_KEYWORDS.items():
        if any(kw in combined_text for kw in keywords):
            tags.append(f"文种:{doc_kind}")
            break

    # 2. 主题标签（Opt 2：优先按 policy_rules.subject_categories 关键词匹配）
    meta = doc.get("metadata_json") or {}
    title = meta.get("title") or ""
    subject_categories: list[str] = (doc.get("_policy_rules") or {}).get(
        "subject_categories", []
    )
    matched_subject: str = ""
    for category in subject_categories:
        if category in combined_text or (title and category in title):
            matched_subject = category
            break
    if not matched_subject and title:
        matched_subject = title[:8]  # 回退：取题名前 8 字作为主题
    if matched_subject:
        tags.append(f"主题:{matched_subject}")

    # 3. 状态标签
    doc_status = doc.get("status") or "draft"
    tags.append(f"状态:{doc_status}")

    # 4. 风险标签
    for kw in _RISK_KEYWORDS:
        if kw in combined_text:
            tags.append(f"风险:{kw}")

    return tags


# ---------------------------------------------------------------------------
# 草稿目录生成（Develop.md §11）
# ---------------------------------------------------------------------------

def build_draft_catalog(
    draft_docs: list[dict[str, Any]],
    batch_id: str,
    tenant_id: str,
) -> dict[str, Any]:
    """
    生成草稿卷内目录结构。

    返回 catalog dict（后续序列化为 JSON 存 MinIO）。
    """
    entries = []
    for i, doc in enumerate(draft_docs):
        meta = doc.get("metadata_json") or {}
        entries.append(
            {
                "order": i + 1,
                "tmp_doc_id": doc.get("tmp_doc_id", ""),
                "title": meta.get("title", ""),
                "date": meta.get("date", ""),
                "doc_no": meta.get("doc_no", ""),
                "page_count": meta.get("page_count", 0),
                "start_page": doc.get("start_page", 0),
                "end_page": doc.get("end_page", 0),
                "confidence": doc.get("confidence", 0.0),
                "status": doc.get("status", "draft"),
                "preservation_period": meta.get("preservation_period", ""),
                "tags": doc.get("tags", []),
            }
        )

    return {
        "batch_id": batch_id,
        "tenant_id": tenant_id,
        "version": "draft",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "doc_count": len(entries),
        "entries": entries,
    }


async def upload_draft_catalog(
    catalog: dict[str, Any],
    batch_id: str,
    tenant_id: str,
) -> str:
    """
    Opt 6：将草稿目录序列化后上传到 MinIO，返回 storage_uri。

    路径规则：tenant/{tenant_id}/batch/{batch_id}/draft_catalog.json
    """
    import asyncio
    import io

    storage_uri = f"tenant/{tenant_id}/batch/{batch_id}/draft_catalog.json"
    catalog_bytes = json.dumps(catalog, ensure_ascii=False, indent=2).encode("utf-8")

    try:
        from app.infrastructure.storage.storage_service import get_storage_client

        client = get_storage_client()
        await asyncio.to_thread(
            client.put_object,
            object_name=storage_uri,
            data=io.BytesIO(catalog_bytes),
            length=len(catalog_bytes),
            content_type="application/json",
        )
        logger.info("draft_catalog uploaded: %s (%d bytes)", storage_uri, len(catalog_bytes))
    except Exception:
        # 回退：写本地临时文件
        import tempfile, os
        tmp = tempfile.NamedTemporaryFile(
            delete=False, suffix="_draft_catalog.json", mode="wb"
        )
        tmp.write(catalog_bytes)
        tmp.close()
        storage_uri = tmp.name
        logger.warning("MinIO upload failed; draft_catalog saved locally: %s", storage_uri)

    return storage_uri


# ---------------------------------------------------------------------------
# 持久化 DocUnit + DocVersion（Develop.md §16.2）
# ---------------------------------------------------------------------------

async def persist_draft_docs(
    db: AsyncSession,
    draft_docs: list[dict[str, Any]],
    batch_id: str,
    tenant_id: str,
    run_id: str,
    quality_scores: dict[str, float],
) -> list[str]:
    """
    将草稿件集合写入 DocUnit + DocVersion 表。

    返回创建的 doc_id 列表。
    """
    from app.db.models import DocUnit, DocVersion

    doc_ids: list[str] = []
    for doc in draft_docs:
        doc_id = doc.get("tmp_doc_id") or f"doc_{uuid4().hex[:12]}"
        doc.setdefault("tmp_doc_id", doc_id)

        # DocUnit：稳定身份（每件只创建一次）
        unit = DocUnit(
            doc_id=doc_id,
            batch_id=batch_id,
            tenant_id=tenant_id,
            doc_kind=doc.get("doc_kind", "main"),
            current_version=1,
            status="draft",
        )
        db.add(unit)

        # DocVersion：本次草稿版本快照
        version = DocVersion(
            doc_version_id=f"dv_{doc_id}_v1",
            doc_id=doc_id,
            batch_id=batch_id,
            version_no=1,
            version_type="draft",
            start_page=doc.get("start_page", 0),
            end_page=doc.get("end_page", 0),
            page_ids_json=doc.get("page_ids", []),
            sort_index=doc.get("sort_index", 0),
            metadata_json=doc.get("metadata_json", {}),
            tags_json=doc.get("tags", []),
            confidence_json=doc.get("confidence_json", {}),
            quality_scores_json=quality_scores,
            is_current=True,
        )
        db.add(version)
        doc_ids.append(doc_id)

    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to persist draft docs for batch_id=%s", batch_id)
        raise

    return doc_ids


# ---------------------------------------------------------------------------
# 产物 MinIO 路径（Develop.md §16.4）
# ---------------------------------------------------------------------------

def draft_catalog_storage_uri(tenant_id: str, batch_id: str) -> str:
    return f"tenant/{tenant_id}/batch/{batch_id}/draft/catalog_v1.json"


def draft_pdf_storage_uri(tenant_id: str, batch_id: str) -> str:
    return f"tenant/{tenant_id}/batch/{batch_id}/draft/searchable_v1.pdf"


# ---------------------------------------------------------------------------
# ArtifactFile 登记
# ---------------------------------------------------------------------------

async def register_artifact(
    db: AsyncSession,
    *,
    batch_id: str,
    artifact_type: str,
    storage_uri: str,
    run_id: str,
    doc_id: str | None = None,
) -> str:
    """登记产物到 artifact_files 表（Develop.md §16.2）。"""
    from app.db.models import ArtifactFile

    artifact_id = f"art_{uuid4().hex[:12]}"
    artifact = ArtifactFile(
        artifact_id=artifact_id,
        batch_id=batch_id,
        doc_id=doc_id,
        artifact_type=artifact_type,
        artifact_version=1,
        storage_uri=storage_uri,
        created_by_run_id=run_id,
        upload_status="uploaded",
    )
    db.add(artifact)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        logger.exception("Failed to register artifact: type=%s batch=%s", artifact_type, batch_id)
        raise
    return artifact_id
