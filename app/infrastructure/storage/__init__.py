"""Storage/path adapters."""

from app.core.path_security import ensure_allowed_path, is_managed_upload_path
from app.core.preview import build_pdf_page_preview, build_thumbnail
from app.infrastructure.storage.storage_service import (
    fetch_object_bytes,
    get_storage_client,
    put_object_bytes,
)
from app.infrastructure.storage.uploads import remove_managed_upload_file, save_upload_file

__all__ = [
    "build_pdf_page_preview",
    "build_thumbnail",
    "ensure_allowed_path",
    "fetch_object_bytes",
    "get_storage_client",
    "is_managed_upload_path",
    "put_object_bytes",
    "remove_managed_upload_file",
    "save_upload_file",
]
