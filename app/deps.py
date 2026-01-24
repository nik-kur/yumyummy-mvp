from collections.abc import Generator

from fastapi import Header, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def verify_internal_token(x_internal_token: str = Header(..., alias="X-Internal-Token")) -> str:
    """
    Dependency to verify X-Internal-Token header for internal API endpoints.
    Raises 401 if token is missing or invalid.
    """
    if not settings.internal_api_token:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal API token not configured"
        )
    
    if x_internal_token != settings.internal_api_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Internal-Token"
        )
    
    return x_internal_token
