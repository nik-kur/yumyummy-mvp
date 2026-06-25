"""
Verify third-party identity tokens (Sign in with Apple, Google Sign-In).

The mobile app performs the native sign-in and hands us the resulting
identity token (Apple) / ID token (Google). Both are JWTs signed by the
provider; we verify them against the provider's published JWKS, check the
audience/issuer, and extract the stable subject id + email.

We deliberately fetch JWKS lazily and cache via PyJWT's ``PyJWKClient`` so
importing this module has no network side effects (and tests can monkeypatch
the two public ``verify_*`` functions).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import jwt
from jwt import PyJWKClient

from app.core.config import settings

APPLE_ISSUER = "https://appleid.apple.com"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"

GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"


class ProviderAuthError(Exception):
    """Raised when a provider identity token is invalid or misconfigured."""


@dataclass(frozen=True)
class ProviderIdentity:
    provider: str
    provider_id: str           # the token's stable `sub`
    email: Optional[str] = None


# Cached JWKS clients (created on first use).
_apple_jwk_client: Optional[PyJWKClient] = None
_google_jwk_client: Optional[PyJWKClient] = None


def _apple_client() -> PyJWKClient:
    global _apple_jwk_client
    if _apple_jwk_client is None:
        _apple_jwk_client = PyJWKClient(APPLE_JWKS_URL)
    return _apple_jwk_client


def _google_client() -> PyJWKClient:
    global _google_jwk_client
    if _google_jwk_client is None:
        _google_jwk_client = PyJWKClient(GOOGLE_JWKS_URL)
    return _google_jwk_client


def verify_apple_identity_token(identity_token: str) -> ProviderIdentity:
    """Verify an Apple identity token and return the resolved identity."""
    audiences = settings.apple_client_id_set
    if not audiences:
        raise ProviderAuthError("Apple sign-in is not configured (APPLE_CLIENT_ID)")
    try:
        signing_key = _apple_client().get_signing_key_from_jwt(identity_token)
        claims = jwt.decode(
            identity_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=list(audiences),
            issuer=APPLE_ISSUER,
        )
    except jwt.PyJWTError as exc:
        raise ProviderAuthError(f"invalid Apple token: {exc}") from exc

    sub = claims.get("sub")
    if not sub:
        raise ProviderAuthError("Apple token missing 'sub'")
    return ProviderIdentity(provider="apple", provider_id=str(sub), email=claims.get("email"))


def verify_google_id_token(id_token: str) -> ProviderIdentity:
    """Verify a Google ID token and return the resolved identity."""
    audiences = settings.google_client_id_set
    if not audiences:
        raise ProviderAuthError("Google sign-in is not configured (GOOGLE_CLIENT_ID)")
    try:
        signing_key = _google_client().get_signing_key_from_jwt(id_token)
        claims = jwt.decode(
            id_token,
            signing_key.key,
            algorithms=["RS256"],
            audience=list(audiences),
        )
    except jwt.PyJWTError as exc:
        raise ProviderAuthError(f"invalid Google token: {exc}") from exc

    if claims.get("iss") not in GOOGLE_ISSUERS:
        raise ProviderAuthError("Google token has unexpected issuer")
    sub = claims.get("sub")
    if not sub:
        raise ProviderAuthError("Google token missing 'sub'")
    return ProviderIdentity(provider="google", provider_id=str(sub), email=claims.get("email"))
