"""
Direct-to-storage upload support for meal photos.

The app asks for a short-lived presigned PUT URL, uploads the image straight
to R2/S3, then passes the returned ``public_url`` to ``/app/agent/run`` as the
``image_url``. Keeps large binaries off our API and off Render's ephemeral
disk.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.deps import get_current_account
from app.models.account import Account
from app.services import storage
from app.schemas.app_api import PresignRequest, PresignResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/app/uploads", tags=["uploads"])


@router.post("/meal-photo/presign", response_model=PresignResponse)
def presign_meal_photo(
    payload: PresignRequest,
    account: Account = Depends(get_current_account),
):
    if not storage.is_enabled():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Photo storage is not configured",
        )
    try:
        key, upload_url, public_url, ttl = storage.generate_presigned_put(
            account.id, content_type=payload.content_type, ext=payload.ext
        )
    except storage.StorageNotConfiguredError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    except Exception as exc:  # boto/network failure
        logger.error("[UPLOADS] presign failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Could not create upload URL")

    return PresignResponse(
        key=key, upload_url=upload_url, public_url=public_url, expires_in_seconds=ttl
    )
