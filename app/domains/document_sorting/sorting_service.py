"""
Document Sorting Domain — 件级排序领域服务。

核心能力：
- 基于形成时间、文号、附件关系对件进行业务排序
- 计算每件的排序键
- 处理附件跟随主件逻辑
- 支持 Final 阶段正式排序和编号

遵循 Develop.md 阶段 5 和阶段 9。
"""

from __future__ import annotations

import logging
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


_DATE_PARSE_FMTS = [
    "%Y年%m月%d日",
    "%Y年%m月",
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%Y%m%d",
]


def _parse_date(date_str: str | None) -> datetime | None:
    """尝试解析日期字符串，返回 datetime 或 None。"""
    if not date_str:
        return None
    date_str = date_str.strip()
    for fmt in _DATE_PARSE_FMTS:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    # 尝试提取 yyyymmdd
    m = re.search(r"(\d{4})[年\-/](\d{1,2})[月\-/](\d{1,2})", date_str)
    if m:
        try:
            return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    return None


def _extract_doc_no_serial(doc_no: str | None) -> int:
    """从文号中提取流水号用于二级排序。"""
    if not doc_no:
        return 9999
    m = re.search(r"(\d+)号?$", doc_no)
    return int(m.group(1)) if m else 9999


def compute_sort_key(doc_schema: dict[str, Any]) -> tuple:
    """
    计算件的排序键（多级排序）：
    1. 形成时间（升序）
    2. 文号流水号（升序）
    3. 件在卷中的原始位置（升序）
    """
    metadata = doc_schema.get("metadata_json") or doc_schema.get("metadata") or {}
    candidates = doc_schema.get("candidates") or {}

    # 日期：优先用已提取的 metadata.date，其次用候选日期
    date_str = metadata.get("date") or (
        candidates.get("dates", [None])[0] if candidates.get("dates") else None
    )
    parsed_date = _parse_date(date_str)
    date_key = parsed_date.isoformat() if parsed_date else "9999-12-31"

    # 文号
    doc_no = metadata.get("doc_no") or (
        candidates.get("doc_nos", [None])[0] if candidates.get("doc_nos") else None
    )
    serial_key = _extract_doc_no_serial(doc_no)

    # 原始位置（start_page）作为兜底排序
    start_page = doc_schema.get("start_page", 9999)

    return (date_key, serial_key, start_page)


def sort_docs(docs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    对件列表按排序键排序，返回带 sort_index 的新列表。
    附件紧跟主件（doc_kind=attachment 跟在关联主件之后）。
    """
    # 先分离主件和附件
    main_docs = [d for d in docs if d.get("doc_kind", "main") != "attachment"]
    attachment_docs = [d for d in docs if d.get("doc_kind", "main") == "attachment"]

    # 主件按排序键排序
    main_docs.sort(key=compute_sort_key)

    # 附件插入到关联主件之后
    result: list[dict[str, Any]] = []
    for main_doc in main_docs:
        result.append(main_doc)
        doc_id = main_doc.get("tmp_doc_id") or main_doc.get("doc_id")
        related_attachments = [
            a for a in attachment_docs if a.get("parent_doc_id") == doc_id
        ]
        # 附件如果有多个，按原始位置排序
        related_attachments.sort(key=lambda a: a.get("start_page", 9999))
        result.extend(related_attachments)

    # 没有关联主件的附件追加到末尾
    orphan_attachments = [
        a for a in attachment_docs
        if not any(
            a.get("parent_doc_id") == (m.get("tmp_doc_id") or m.get("doc_id"))
            for m in main_docs
        )
    ]
    result.extend(orphan_attachments)

    # 写入 sort_index
    for i, doc in enumerate(result):
        doc["sort_index"] = i

    return result


def assign_archive_numbers(
    sorted_docs: list[dict[str, Any]],
    *,
    batch_id: str,
    prefix: str = "",
    start_serial: int = 1,
    policy_rules: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Final 阶段：为已排序的件分配正式档案编号。

    Opt 1：编号格式从 policy_rules.numbering_rules 中读取，支持字段：
      fonds_no      — 全宗号（如 "001"）
      catalog_no    — 目录号（如 "2024"）
      volume_no     — 案卷号（如 "0001"）
      serial_format — 件号格式字符串，默认 "{serial:04d}"
    最终格式：{fonds_no}-{catalog_no}-{volume_no}-{serial_format}
    若无 numbering_rules，回退到 {prefix}{batch_id}-{serial:04d}。
    """
    numbering: dict[str, Any] = (policy_rules or {}).get("numbering_rules", {})
    fonds_no = numbering.get("fonds_no", "")
    catalog_no = numbering.get("catalog_no", "")
    volume_no = numbering.get("volume_no", "")
    serial_fmt: str = numbering.get("serial_format", "{serial:04d}")

    for i, doc in enumerate(sorted_docs):
        serial = start_serial + i
        try:
            serial_str = serial_fmt.format(serial=serial)
        except (KeyError, ValueError):
            serial_str = f"{serial:04d}"

        if fonds_no or catalog_no or volume_no:
            parts = [p for p in (fonds_no, catalog_no, volume_no, serial_str) if p]
            doc["archive_no"] = "-".join(parts)
        else:
            doc["archive_no"] = f"{prefix}{batch_id}-{serial_str}"
    return sorted_docs
