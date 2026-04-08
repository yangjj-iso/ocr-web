"""Managed upload file storage helpers."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

from app.core.path_security import is_managed_upload_path
from config import ALLOWED_EXTENSIONS, UPLOAD_DIR

logger = logging.getLogger(__name__)


async def save_upload_file(filename: str, file_content: bytes, relative_path: str = "") -> tuple[str, str]:
    base_name = Path(filename).name
    ext = Path(base_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise ValueError(f"Unsupported file type: {ext}. Allowed: {allowed}")

    rel_parts: list[str] = []
    for part in Path((relative_path or "").replace("\\", "/")).parts:
        if part in {"", ".", ".."}:
            continue
        if len(part) == 2 and part[1] == ":":
            continue
        rel_parts.append(part)

    save_dir = UPLOAD_DIR.joinpath(*rel_parts[:-1]) if rel_parts else UPLOAD_DIR
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"{uuid.uuid4().hex}_{base_name}"
    save_path.write_bytes(file_content)
    return str(save_path), ext


def remove_managed_upload_file(file_path: str) -> None:
    if not is_managed_upload_path(file_path):
        return
    try:
        Path(file_path).unlink(missing_ok=True)
    except Exception:  # noqa: BLE001
        logger.warning("Failed to remove managed upload file: %s", file_path, exc_info=True)

