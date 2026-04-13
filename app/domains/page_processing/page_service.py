"""
Page Processing Domain — 页面处理领域服务。

负责：
- 图像预处理
- OCR 调用
- 版面分析
- pHash / 页面相似度
- 候选字段提取（标题/日期/文号候选）
- 首页得分和重复页得分计算

这是计算面最基础的一层，为分件提供原始感知数据。
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 候选字段提取（从 OCR 文本中识别标题/日期/文号候选）
# ---------------------------------------------------------------------------

_DATE_PATTERNS = [
    re.compile(r"\d{4}[年\-/]\d{1,2}[月\-/]\d{1,2}日?"),
    re.compile(r"\d{4}年\d{1,2}月"),
]

_DOC_NO_PATTERNS = [
    re.compile(r"[\u4e00-\u9fa5]{2,6}[〔\[【（(]\d{4}[〕\]】）)]\d+号"),
    re.compile(r"[A-Za-z]{1,6}[〔\[【（(]?\d{4}[〕\]】）)]?\d+号?"),
]


def extract_candidates_from_text(ocr_text: str) -> dict[str, list[str]]:
    """从 OCR 文本中提取日期、文号候选。"""
    if not ocr_text:
        return {"dates": [], "doc_nos": [], "title_lines": []}

    lines = [l.strip() for l in ocr_text.splitlines() if l.strip()]

    dates = []
    for pat in _DATE_PATTERNS:
        dates.extend(pat.findall(ocr_text))

    doc_nos = []
    for pat in _DOC_NO_PATTERNS:
        doc_nos.extend(pat.findall(ocr_text))

    # 前 5 行中长度在 10-60 字符的行作为标题候选
    title_lines = [l for l in lines[:5] if 10 <= len(l) <= 60]

    return {
        "dates": list(dict.fromkeys(dates)),
        "doc_nos": list(dict.fromkeys(doc_nos)),
        "title_lines": title_lines[:3],
    }


def compute_phash_hex(image_bytes: bytes) -> str | None:
    """计算图像的感知哈希（pHash）。需要 imagehash + Pillow。"""
    try:
        import io
        import imagehash
        from PIL import Image
        img = Image.open(io.BytesIO(image_bytes)).convert("L")
        return str(imagehash.phash(img))
    except Exception:
        logger.debug("pHash computation failed, falling back to sha256 prefix")
        return None


def compute_sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def score_first_page(ocr_text: str, candidates: dict[str, list[str]]) -> float:
    """
    简单启发式：估算此页是否为新件首页。
    返回 0.0–1.0 得分，越高越可能是首页。
    """
    score = 0.0
    if not ocr_text:
        return score

    lines = [l.strip() for l in ocr_text.splitlines() if l.strip()]
    if not lines:
        return score

    # 有文号则强烈暗示首页
    if candidates.get("doc_nos"):
        score += 0.45

    # 有日期
    if candidates.get("dates"):
        score += 0.20

    # 有标题候选（较短的行居中或出现在开头）
    if candidates.get("title_lines"):
        score += 0.20

    # 首行文字较短（通常单独成行的标题）
    first_line = lines[0] if lines else ""
    if 4 <= len(first_line) <= 30:
        score += 0.15

    return min(score, 1.0)


def score_duplicate_page(phash_a: str | None, phash_b: str | None) -> float:
    """
    通过 pHash 汉明距离估算两页相似度。
    返回 0.0–1.0，越高越相似（越可能是重复页）。
    """
    if not phash_a or not phash_b:
        return 0.0
    try:
        import imagehash
        h1 = imagehash.hex_to_hash(phash_a)
        h2 = imagehash.hex_to_hash(phash_b)
        distance = h1 - h2
        # pHash 64 位，距离 0 = 完全相同，距离 > 15 认为不相似
        return max(0.0, 1.0 - distance / 16.0)
    except Exception:
        return 0.0


# ---------------------------------------------------------------------------
# Page schema 构建
# ---------------------------------------------------------------------------

def build_page_schema(
    *,
    page_id: str,
    batch_id: str,
    page_index: int,
    image_uri: str,
    ocr_text: str,
    ocr_blocks: dict[str, Any] | None,
    layout_type: str | None,
    phash: str | None,
    first_page_score: float,
    duplicate_score: float,
    candidates: dict[str, list[str]],
) -> dict[str, Any]:
    """构建标准化的 page schema，作为下游分件和排序的输入。"""
    return {
        "page_id": page_id,
        "batch_id": batch_id,
        "page_index": page_index,
        "image_uri": image_uri,
        "ocr_text": ocr_text,
        "ocr_blocks": ocr_blocks or {},
        "layout_type": layout_type or "unknown",
        "phash": phash,
        "first_page_score": first_page_score,
        "duplicate_score": duplicate_score,
        "candidates": candidates,
    }


async def compute_phash_from_uri(image_uri: str) -> str | None:
    """
    从 MinIO image_uri 拉取图像并计算 pHash（降级模式）。

    优先从 MinIO 拉取；若 URI 为本地路径则直接读取。
    需要 imagehash + Pillow 已安装。
    """
    import asyncio

    image_bytes: bytes | None = None

    if image_uri.startswith("s3://") or "/" in image_uri:
        # 尝试通过内部 storage service 拉取（非阻塞）
        try:
            from app.infrastructure.storage import fetch_object_bytes
            image_bytes = await asyncio.to_thread(fetch_object_bytes, image_uri)
        except Exception:
            logger.debug("fetch_object_bytes failed for uri=%s", image_uri)

    if image_bytes is None:
        # 回退：本地路径
        import pathlib
        p = pathlib.Path(image_uri)
        if p.exists():
            image_bytes = p.read_bytes()

    if not image_bytes:
        return None

    return await asyncio.to_thread(compute_phash_hex, image_bytes)
