"""
Object storage for meal photos (Cloudflare R2 or AWS S3, S3-compatible API).

The mobile client uploads photos directly to storage using a short-lived
presigned PUT URL, then references the resulting public URL when calling
``/app/agent/run``. Render's filesystem is ephemeral, so photos must live in
object storage, never on disk.

boto3 is imported lazily so environments that don't enable storage don't pay
the import cost and the rest of the app keeps working if boto3 is absent.
"""

from __future__ import annotations

import uuid
from typing import Optional, Tuple

from app.core.config import settings

# Map a handful of common content types to file extensions.
_EXT_BY_CONTENT_TYPE = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
    "image/heic": "heic",
}


class StorageNotConfiguredError(Exception):
    pass


def is_enabled() -> bool:
    return bool(
        settings.storage_enabled
        and settings.storage_bucket
        and settings.storage_access_key_id
        and settings.storage_secret_access_key
    )


def _client():
    if not is_enabled():
        raise StorageNotConfiguredError("Object storage is not configured")
    try:
        import boto3  # lazy
        from botocore.client import Config
    except ImportError as exc:  # pragma: no cover - depends on env
        raise StorageNotConfiguredError(f"boto3 not installed: {exc}") from exc

    return boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint_url or None,
        region_name=settings.storage_region or "auto",
        aws_access_key_id=settings.storage_access_key_id,
        aws_secret_access_key=settings.storage_secret_access_key,
        config=Config(signature_version="s3v4"),
    )


def build_key(account_id: int, *, content_type: str = "image/jpeg", ext: Optional[str] = None) -> str:
    if not ext:
        ext = _EXT_BY_CONTENT_TYPE.get((content_type or "").lower(), "jpg")
    ext = ext.lstrip(".").lower()
    return f"meal-photos/{account_id}/{uuid.uuid4().hex}.{ext}"


def public_url(key: str) -> Optional[str]:
    base = settings.storage_public_base_url
    if not base:
        return None
    return f"{base.rstrip('/')}/{key}"


def generate_presigned_put(
    account_id: int, *, content_type: str = "image/jpeg", ext: Optional[str] = None
) -> Tuple[str, str, Optional[str], int]:
    """Return ``(key, upload_url, public_url, expires_in_seconds)``."""
    key = build_key(account_id, content_type=content_type, ext=ext)
    ttl = int(settings.storage_presign_ttl_seconds)
    client = _client()
    upload_url = client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": settings.storage_bucket,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=ttl,
    )
    return key, upload_url, public_url(key), ttl
