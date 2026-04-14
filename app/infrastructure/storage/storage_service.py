"""Minimal object storage service backed by the local uploads directory."""

from __future__ import annotations

import io
from pathlib import Path, PurePosixPath
from typing import BinaryIO

from config import UPLOAD_DIR


_OBJECT_STORE_ROOT = UPLOAD_DIR / "object_store"
_OBJECT_STORE_ROOT.mkdir(parents=True, exist_ok=True)


def _normalize_storage_uri(storage_uri: str) -> Path:
    raw = (storage_uri or "").strip()
    candidate = Path(raw)
    if raw and candidate.exists():
        return candidate

    pure_path = PurePosixPath(raw.replace("\\", "/"))
    safe_parts = [part for part in pure_path.parts if part not in {"", ".", "..", "/"}]
    if not safe_parts:
        raise ValueError("storage_uri must not be empty")
    return _OBJECT_STORE_ROOT.joinpath(*safe_parts)


def fetch_object_bytes(storage_uri: str) -> bytes:
    return _normalize_storage_uri(storage_uri).read_bytes()


def put_object_bytes(storage_uri: str, data: bytes) -> str:
    target = _normalize_storage_uri(storage_uri)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return str(target)


class LocalStorageClient:
    def put_object(
        self,
        *,
        object_name: str,
        data: BinaryIO | io.BytesIO,
        length: int | None = None,
        content_type: str | None = None,
    ) -> str:
        del length, content_type
        payload = data.read()
        if isinstance(payload, str):
            payload = payload.encode("utf-8")
        return put_object_bytes(object_name, payload)


def get_storage_client() -> LocalStorageClient:
    return LocalStorageClient()