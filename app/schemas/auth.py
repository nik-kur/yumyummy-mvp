"""Pydantic schemas for the mobile auth endpoints."""

from typing import Optional

from pydantic import BaseModel, Field


class AppleSignInRequest(BaseModel):
    identity_token: str = Field(..., min_length=1)


class GoogleSignInRequest(BaseModel):
    id_token: str = Field(..., min_length=1)


class EmailCodeRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)


class EmailCodeRequestResponse(BaseModel):
    sent: bool = True
    # Populated only when AUTH_EMAIL_DEBUG_RETURN_CODE is enabled (dev only).
    debug_code: Optional[str] = None


class EmailVerifyRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=320)
    code: str = Field(..., min_length=4, max_length=12)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    account_id: int
    created: bool = False


class TelegramLinkIssueRequest(BaseModel):
    telegram_id: str = Field(..., min_length=1)


class TelegramLinkIssueResponse(BaseModel):
    code: str
    expires_in_seconds: int


class TelegramLinkRedeemRequest(BaseModel):
    code: str = Field(..., min_length=4, max_length=16)


class TelegramLinkRedeemResponse(BaseModel):
    status: str  # 'linked' | 'already_linked'
    account_id: int


# --- reverse linking: app -> telegram --------------------------------------

class AppLinkIssueResponse(BaseModel):
    """Returned to the signed-in app. The app opens ``deep_link`` (which sends
    the user into the bot with ``/start link_<code>``) and shows ``code`` as a
    manual fallback."""
    code: str
    expires_in_seconds: int
    bot_username: str
    deep_link: str


class AppLinkRedeemRequest(BaseModel):
    """Sent by the bot when a user opens a ``/start link_<code>`` deep link."""
    code: str = Field(..., min_length=4, max_length=16)
    telegram_id: str = Field(..., min_length=1)


class AppLinkRedeemResponse(BaseModel):
    status: str  # 'linked' | 'already_linked'
    account_id: int
