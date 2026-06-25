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
