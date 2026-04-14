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

import asyncio
import hashlib
import logging
import pathlib
import re
import tempfile
from typing import Any

from sqlalchemy import select

from app.db.database import async_session
from app.db.models import PageRecord

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


async def _load_batch_pages(batch_id: str) -> list[PageRecord]:
    async with async_session() as session:
        result = await session.execute(
            select(PageRecord)
            .where(PageRecord.batch_id == batch_id)
            .order_by(PageRecord.page_index.asc())
        )
        return list(result.scalars().all())


async def _materialize_storage_uri(storage_uri: str | None) -> tuple[str | None, str | None]:
    raw = str(storage_uri or "").strip()
    if not raw:
        return None, None

    candidate = pathlib.Path(raw)
    if candidate.exists():
        return str(candidate), None

    try:
        from app.infrastructure.storage import fetch_object_bytes

        data = await asyncio.to_thread(fetch_object_bytes, raw)
    except Exception:
        logger.debug("Unable to materialize storage uri: %s", raw)
        return None, None

    suffix = candidate.suffix or ".png"
    handle = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        handle.write(data)
        handle.flush()
    finally:
        handle.close()
    return handle.name, handle.name


def _cleanup_temp_path(path: str | None) -> None:
    if not path:
        return
    try:
        pathlib.Path(path).unlink(missing_ok=True)
    except Exception:
        logger.debug("Failed to cleanup temp path: %s", path)


def _normalize_page_ids(page_ids: list[str] | None) -> set[str]:
    return {str(page_id).strip() for page_id in (page_ids or []) if str(page_id).strip()}


async def preprocess_pages(*, batch_id: str, page_ids: list[str]) -> None:
    """Apply lightweight preprocessing and persist preview URIs for selected pages."""
    from app.infrastructure.storage import put_object_bytes
    from app.utils.image_preprocess import cleanup_preprocessed_image, preprocess_image

    selected_ids = _normalize_page_ids(page_ids)

    async with async_session() as session:
        result = await session.execute(
            select(PageRecord)
            .where(PageRecord.batch_id == batch_id)
            .order_by(PageRecord.page_index.asc())
        )
        pages = list(result.scalars().all())

        updated = 0
        for page in pages:
            if selected_ids and page.page_id not in selected_ids:
                continue
            if not page.image_uri:
                continue

            source_path, cleanup_source = await _materialize_storage_uri(page.image_uri)
            if not source_path:
                continue

            processed_path: str | None = None
            try:
                processed_path = await asyncio.to_thread(preprocess_image, source_path, "opencv_document")
                payload = await asyncio.to_thread(pathlib.Path(processed_path).read_bytes)
                preview_uri = f"archive/preprocessed/{batch_id}/{page.page_id}.png"
                page.preview_uri = await asyncio.to_thread(put_object_bytes, preview_uri, payload)
                updated += 1
            except Exception:
                logger.exception("preprocess_pages failed for batch=%s page_id=%s", batch_id, page.page_id)
            finally:
                if processed_path:
                    await asyncio.to_thread(cleanup_preprocessed_image, source_path, processed_path)
                _cleanup_temp_path(cleanup_source)

        if updated:
            await session.commit()


async def run_ocr_pages(*, batch_id: str, page_ids: list[str]) -> None:
    """Run OCR for selected pages and persist text/block results into PageRecord."""
    from app.core.ocr_engine import ocr_image_basic

    selected_ids = _normalize_page_ids(page_ids)

    async with async_session() as session:
        result = await session.execute(
            select(PageRecord)
            .where(PageRecord.batch_id == batch_id)
            .order_by(PageRecord.page_index.asc())
        )
        pages = list(result.scalars().all())

        updated = 0
        for page in pages:
            if selected_ids and page.page_id not in selected_ids:
                continue

            source_uri = page.preview_uri or page.image_uri
            source_path, cleanup_source = await _materialize_storage_uri(source_uri)
            if not source_path:
                continue

            try:
                ocr_result = await asyncio.to_thread(ocr_image_basic, source_path)
                lines = [line for line in (ocr_result.get("lines") or []) if str(line.get("text") or "").strip()]
                page.ocr_text = "\n".join(str(line.get("text") or "").strip() for line in lines)
                page.ocr_blocks_json = ocr_result
                if not page.layout_type:
                    page.layout_type = "mixed" if ocr_result.get("regions") else ("text" if lines else "unknown")
                updated += 1
            except Exception:
                logger.exception("run_ocr_pages failed for batch=%s page_id=%s", batch_id, page.page_id)
            finally:
                _cleanup_temp_path(cleanup_source)

        if updated:
            await session.commit()


async def extract_page_features(*, batch_id: str, page_ids: list[str]) -> None:
    """Compute page-level candidates, first-page score, pHash, and duplicate score."""
    selected_ids = _normalize_page_ids(page_ids)

    async with async_session() as session:
        result = await session.execute(
            select(PageRecord)
            .where(PageRecord.batch_id == batch_id)
            .order_by(PageRecord.page_index.asc())
        )
        pages = list(result.scalars().all())

        phash_cache: dict[str, str | None] = {}

        async def ensure_phash(page: PageRecord) -> str | None:
            if page.page_id in phash_cache:
                return phash_cache[page.page_id]
            phash_value = page.phash
            if not phash_value:
                phash_value = await compute_phash_from_uri(page.preview_uri or page.image_uri or "")
            phash_cache[page.page_id] = phash_value
            return phash_value

        updated = 0
        for index, page in enumerate(pages):
            if selected_ids and page.page_id not in selected_ids:
                continue

            ocr_text = page.ocr_text or ""
            candidates = extract_candidates_from_text(ocr_text)
            first_page_score = score_first_page(ocr_text, candidates)
            phash_value = await ensure_phash(page)

            duplicate_score = 0.0
            if index > 0:
                prev_phash = await ensure_phash(pages[index - 1])
                duplicate_score = score_duplicate_page(prev_phash, phash_value)

            page.candidates_json = candidates
            page.first_page_score = first_page_score
            page.phash = phash_value
            page.duplicate_score = duplicate_score
            if not page.layout_type and ocr_text.strip():
                page.layout_type = "text"
            updated += 1

        if updated:
            await session.commit()
