"""
Minting and verifying the JWT access tokens used by the mobile app.

These are *our own* tokens (HS256, signed with ``settings.jwt_secret``),
issued after a provider sign-in succeeds. They are distinct from the
provider identity tokens (Apple/Google) which we only verify once at login.

Functions accept an explicit ``secret`` so they are trivially unit-testable
without global configuration.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import jwt  # PyJWT

from app.core.config import settings


class TokenError(Exception):
    """Raised when a token is missing/expired/invalid or no secret is configured."""


def _resolve_secret(secret: Optional[str]) -> str:
    resolved = secret or settings.jwt_secret
    if not resolved:
        raise TokenError("JWT secret is not configured (set JWT_SECRET)")
    return resolved


def create_access_token(
    account_id: int,
    *,
    secret: Optional[str] = None,
    ttl_days: Optional[int] = None,
    now: Optional[datetime] = None,
) -> str:
    """Mint a signed access token for ``account_id``."""
    key = _resolve_secret(secret)
    issued = now or datetime.now(timezone.utc)
    ttl = ttl_days if ttl_days is not None else settings.jwt_access_ttl_days
    payload = {
        "sub": str(account_id),
        "typ": "access",
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(days=ttl)).timestamp()),
    }
    return jwt.encode(payload, key, algorithm="HS256")


def decode_access_token(token: str, *, secret: Optional[str] = None) -> dict:
    """Verify and decode a token. Raises :class:`TokenError` on any problem."""
    key = _resolve_secret(secret)
    try:
        return jwt.decode(token, key, algorithms=["HS256"])
    except jwt.PyJWTError as exc:  # expired, bad signature, malformed, ...
        raise TokenError(str(exc)) from exc


def account_id_from_token(token: str, *, secret: Optional[str] = None) -> int:
    payload = decode_access_token(token, secret=secret)
    sub = payload.get("sub")
    if sub is None:
        raise TokenError("token missing 'sub'")
    try:
        return int(sub)
    except (TypeError, ValueError) as exc:
        raise TokenError("token 'sub' is not an account id") from exc
