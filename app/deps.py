from collections.abc import Generator
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_account(
    authorization: Optional[str] = Header(None, alias="Authorization"),
    db: Session = Depends(get_db),
):
    """Resolve the signed-in mobile account from a ``Bearer <jwt>`` header.

    Raises 401 if the header is missing/malformed or the token is invalid,
    404 if the token is valid but the account no longer exists.
    """
    # Imported lazily to avoid a hard dependency on PyJWT at import time for
    # parts of the app (e.g. the bot) that never touch app auth.
    from app.core.jwt_auth import account_id_from_token, TokenError
    from app.models.account import Account

    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        account_id = account_id_from_token(token)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {exc}",
            headers={"WWW-Authenticate": "Bearer"},
        )

    account = db.query(Account).filter(Account.id == account_id).first()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return account


def verify_internal_token(x_internal_token: str = Header(..., alias="X-Internal-Token")) -> str:
    """
    Dependency to verify X-Internal-Token header for internal API endpoints
    called by the Telegram bot (/billing/*, /agent/run, /ai/agent, etc.).
    Raises 401 if the token is missing or invalid.
    """
    expected = settings.internal_api_token_backend
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal API token not configured"
        )

    if x_internal_token != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Internal-Token"
        )

    return x_internal_token
