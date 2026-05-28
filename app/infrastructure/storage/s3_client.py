"""MinIO / S3 object storage client for the compute worker.

Provides lightweight wrappers around the ``minio`` library for downloading
input files and uploading result artifacts.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from minio import Minio

from config import (
    MINIO_ACCESS_KEY,
    MINIO_BUCKET,
    MINIO_ENDPOINT,
    MINIO_SECRET_KEY,
    MINIO_SECURE,
)

logger = logging.getLogger(__name__)

_client: "Minio | None" = None


def get_minio_client() -> "Minio":
    """Return a lazily-initialized MinIO client singleton."""
    global _client
    if _client is None:
        from minio import Minio

        _client = Minio(
            MINIO_ENDPOINT,
            access_key=MINIO_ACCESS_KEY,
            secret_key=MINIO_SECRET_KEY,
            secure=MINIO_SECURE,
        )
        logger.info(
            "MinIO client initialized: endpoint=%s, secure=%s",
            MINIO_ENDPOINT,
            MINIO_SECURE,
        )
    return _client


def download_object(bucket: str, object_key: str, target_path: str) -> None:
    """Download an object from MinIO/S3 to a local file path."""
    client = get_minio_client()
    client.fget_object(bucket, object_key, target_path)
    logger.debug("Downloaded s3://%s/%s → %s", bucket, object_key, target_path)


def upload_object(
    bucket: str,
    object_key: str,
    file_path: str,
    content_type: str = "application/octet-stream",
) -> None:
    """Upload a local file to MinIO/S3."""
    client = get_minio_client()
    # Ensure bucket exists
    if not client.bucket_exists(bucket):
        client.make_bucket(bucket)
        logger.info("Created MinIO bucket: %s", bucket)
    client.fput_object(bucket, object_key, file_path, content_type=content_type)
    logger.debug("Uploaded %s → s3://%s/%s", file_path, bucket, object_key)


def object_exists(bucket: str, object_key: str) -> bool:
    """Check whether an object exists in the bucket."""
    client = get_minio_client()
    try:
        client.stat_object(bucket, object_key)
        return True
    except Exception:
        return False


def get_default_bucket() -> str:
    """Return the configured default bucket name."""
    return MINIO_BUCKET
