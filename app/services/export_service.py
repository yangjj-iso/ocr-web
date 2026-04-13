"""
Export Service — 可检索 PDF 与目录产物服务。

Develop.md §11 / §12 / §16（目录与 PDF 导出、artifact 登记）。
"""

from __future__ import annotations

import asyncio
import io
import logging
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import uuid4

logger = logging.getLogger(__name__)


def _pdf_storage_uri(tenant_id: str, batch_id: str, export_type: Literal["draft", "final"], version: int) -> str:
    return f"tenant/{tenant_id}/batch/{batch_id}/{export_type}/searchable_v{version}.pdf"


def _catalog_storage_uri(tenant_id: str, batch_id: str, export_type: Literal["draft", "final"], version: int) -> str:
    return f"tenant/{tenant_id}/batch/{batch_id}/{export_type}/catalog_v{version}.json"


def _build_searchable_pdf_bytes_sync(page_entries: list[dict[str, Any]]) -> bytes:
    """同步生成双层 PDF：底图 + 不可见 OCR 文本层。"""
    try:
        import fitz  # type: ignore[import]
    except ImportError:
        logger.error("PyMuPDF (fitz) not installed. Run: pip install pymupdf")
        raise

    doc = fitz.open()
    for entry in page_entries:
        img_bytes: bytes = entry.get("image_bytes") or b""
        ocr_blocks: dict[str, Any] = entry.get("ocr_blocks") or {}

        if not img_bytes:
            doc.new_page()
            continue

        img_stream = io.BytesIO(img_bytes)
        try:
            from PIL import Image  # type: ignore[import]

            pil_img = Image.open(img_stream)
            img_w, img_h = pil_img.size
        except Exception:
            img_w, img_h = 595, 842

        page = doc.new_page(width=img_w, height=img_h)
        page.insert_image(fitz.Rect(0, 0, img_w, img_h), stream=img_bytes)

        blocks = ocr_blocks.get("blocks", []) if isinstance(ocr_blocks, dict) else []
        for block in blocks:
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    text: str = (span.get("text") or "").strip()
                    bbox = span.get("bbox")
                    if not text or not bbox or len(bbox) < 4:
                        continue
                    rect = fitz.Rect(bbox[0], bbox[1], bbox[2], bbox[3])
                    font_size = max(4.0, rect.height * 0.75)
                    try:
                        page.insert_text(
                            rect.tl,
                            text,
                            fontsize=font_size,
                            render_mode=3,
                            overlay=False,
                        )
                    except Exception:
                        continue

    buf = io.BytesIO()
    doc.save(buf, garbage=4, deflate=True)
    doc.close()
    return buf.getvalue()


async def _fetch_image_bytes(image_uri: str) -> bytes | None:
    if not image_uri:
        return None
    try:
        from app.infrastructure.storage import fetch_object_bytes

        return await asyncio.to_thread(fetch_object_bytes, image_uri)
    except Exception:
        pass

    import pathlib

    p = pathlib.Path(image_uri)
    if p.exists():
        return p.read_bytes()
    return None


async def _upload_bytes(storage_uri: str, data: bytes) -> None:
    try:
        from app.infrastructure.storage import put_object_bytes

        await asyncio.to_thread(put_object_bytes, storage_uri, data)
    except Exception:
        logger.warning("Object storage write failed for %s, saving locally as fallback", storage_uri)
        import pathlib

        local_path = pathlib.Path("uploads") / storage_uri.replace("/", "_")
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(data)


async def _register_artifact(
    *,
    batch_id: str,
    artifact_type: str,
    storage_uri: str,
    run_id: str,
    version: int,
    doc_id: str | None = None,
) -> None:
    try:
        from app.db.database import async_session as AsyncSessionLocal
        from app.db.models import ArtifactFile

        artifact_id = f"art_{uuid4().hex[:12]}"
        async with AsyncSessionLocal() as db:
            artifact = ArtifactFile(
                artifact_id=artifact_id,
                batch_id=batch_id,
                doc_id=doc_id,
                artifact_type=artifact_type,
                artifact_version=version,
                storage_uri=storage_uri,
                created_by_run_id=run_id,
                upload_status="uploaded",
            )
            db.add(artifact)
            await db.commit()
    except Exception:
        logger.exception(
            "Failed to register artifact: batch_id=%s type=%s uri=%s",
            batch_id,
            artifact_type,
            storage_uri,
        )


async def export_searchable_pdf(
    *,
    batch_id: str,
    tenant_id: str,
    pages: list[dict[str, Any]] | None = None,
    doc_ids: list[str] | None = None,
    version: int = 1,
    run_id: str | None = None,
    export_type: Literal["draft", "final"] = "final",
) -> str:
    """
    生成 searchable PDF 并登记 artifact。

    export_type:
    - draft -> tenant/{tenant}/batch/{batch}/draft/searchable_v{version}.pdf
    - final -> tenant/{tenant}/batch/{batch}/final/searchable_v{version}.pdf
    """
    del doc_ids  # 预留参数，兼容既有调用

    storage_uri = _pdf_storage_uri(tenant_id, batch_id, export_type, version)
    artifact_run_id = run_id or f"export_{uuid4().hex[:8]}"

    page_entries: list[dict[str, Any]] = []
    if pages:
        fetch_tasks = [_fetch_image_bytes(p.get("image_uri", "")) for p in pages]
        image_bytes_list = await asyncio.gather(*fetch_tasks, return_exceptions=True)
        for p, img in zip(pages, image_bytes_list):
            page_entries.append(
                {
                    "image_bytes": img if isinstance(img, bytes) else b"",
                    "ocr_blocks": p.get("ocr_blocks") or {},
                }
            )

    if page_entries:
        try:
            pdf_bytes = await asyncio.to_thread(_build_searchable_pdf_bytes_sync, page_entries)
            await _upload_bytes(storage_uri, pdf_bytes)
            logger.info(
                "export_searchable_pdf: batch_id=%s type=%s pages=%d size=%d uri=%s",
                batch_id,
                export_type,
                len(page_entries),
                len(pdf_bytes),
                storage_uri,
            )
        except Exception:
            logger.exception("PDF generation failed for batch_id=%s type=%s", batch_id, export_type)
    else:
        logger.warning(
            "export_searchable_pdf: no pages provided for batch_id=%s type=%s",
            batch_id,
            export_type,
        )

    await _register_artifact(
        batch_id=batch_id,
        artifact_type="draft_pdf" if export_type == "draft" else "final_pdf",
        storage_uri=storage_uri,
        run_id=artifact_run_id,
        version=version,
    )

    return storage_uri


async def export_draft_catalog_json(
    *,
    batch_id: str,
    tenant_id: str,
    catalog_data: dict,
    version: int = 1,
    run_id: str | None = None,
) -> str:
    storage_uri = _catalog_storage_uri(tenant_id, batch_id, "draft", version)
    artifact_run_id = run_id or f"export_{uuid4().hex[:8]}"

    try:
        import json as _json

        catalog_bytes = _json.dumps(catalog_data, ensure_ascii=False, indent=2).encode("utf-8")
        await _upload_bytes(storage_uri, catalog_bytes)
    except Exception:
        logger.exception("Failed to upload draft catalog JSON: batch_id=%s uri=%s", batch_id, storage_uri)

    await _register_artifact(
        batch_id=batch_id,
        artifact_type="draft_catalog",
        storage_uri=storage_uri,
        run_id=artifact_run_id,
        version=version,
    )
    return storage_uri


async def export_final_catalog_json(
    *,
    batch_id: str,
    tenant_id: str,
    entries: list[dict],
    version: int = 1,
    run_id: str | None = None,
) -> str:
    storage_uri = _catalog_storage_uri(tenant_id, batch_id, "final", version)
    artifact_run_id = run_id or f"export_{uuid4().hex[:8]}"

    payload = {
        "batch_id": batch_id,
        "tenant_id": tenant_id,
        "version": "final",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "doc_count": len(entries),
        "entries": entries,
    }

    try:
        import json as _json

        catalog_bytes = _json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
        await _upload_bytes(storage_uri, catalog_bytes)
    except Exception:
        logger.exception("Failed to upload final catalog JSON: batch_id=%s uri=%s", batch_id, storage_uri)

    await _register_artifact(
        batch_id=batch_id,
        artifact_type="final_catalog",
        storage_uri=storage_uri,
        run_id=artifact_run_id,
        version=version,
    )
    return storage_uri
