"""
Mobile authentication endpoints.

  POST /auth/apple                 Sign in with Apple (verify identity token)
  POST /auth/google                Google Sign-In (verify ID token)
  POST /auth/email/request         Send a 6-digit email login code
  POST /auth/email/verify          Verify the code -> mint a JWT
  POST /auth/link/telegram/issue   (bot, internal token) issue a link code
  POST /auth/link/telegram/redeem  (app, JWT) redeem code -> merge accounts

Every successful sign-in returns one of our HS256 access tokens (see
``app.core.jwt_auth``) carrying the account id.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.deps import get_db, get_current_account, verify_internal_token
from app.core.config import settings
from app.core import jwt_auth
from app.auth import providers, codes
from app.auth.service import (
    find_or_create_account_for_identity,
    ensure_account_for_telegram_user,
)
from app.auth.merge import link_telegram_account
from app.models.account import Account
from app.models.user import User
from app.schemas.auth import (
    AppleSignInRequest,
    GoogleSignInRequest,
    EmailCodeRequest,
    EmailCodeRequestResponse,
    EmailVerifyRequest,
    AuthTokenResponse,
    TelegramLinkIssueRequest,
    TelegramLinkIssueResponse,
    TelegramLinkRedeemRequest,
    TelegramLinkRedeemResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _mint_token(account: Account, *, created: bool) -> AuthTokenResponse:
    try:
        token = jwt_auth.create_access_token(account.id)
    except jwt_auth.TokenError as exc:
        # No JWT secret configured — refuse rather than issue an insecure token.
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    return AuthTokenResponse(access_token=token, account_id=account.id, created=created)


@router.post("/apple", response_model=AuthTokenResponse)
def sign_in_with_apple(payload: AppleSignInRequest, db: Session = Depends(get_db)):
    try:
        identity = providers.verify_apple_identity_token(payload.identity_token)
    except providers.ProviderAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    account, created = find_or_create_account_for_identity(
        db, provider=identity.provider, provider_id=identity.provider_id, email=identity.email
    )
    logger.info("[AUTH] apple sign-in account_id=%s created=%s", account.id, created)
    return _mint_token(account, created=created)


@router.post("/google", response_model=AuthTokenResponse)
def sign_in_with_google(payload: GoogleSignInRequest, db: Session = Depends(get_db)):
    try:
        identity = providers.verify_google_id_token(payload.id_token)
    except providers.ProviderAuthError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc))

    account, created = find_or_create_account_for_identity(
        db, provider=identity.provider, provider_id=identity.provider_id, email=identity.email
    )
    logger.info("[AUTH] google sign-in account_id=%s created=%s", account.id, created)
    return _mint_token(account, created=created)


@router.post("/email/request", response_model=EmailCodeRequestResponse)
def request_email_code(payload: EmailCodeRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if "@" not in email:
        raise HTTPException(status_code=400, detail="Invalid email address")

    code, _row = codes.create_email_login_code(db, email)

    # TODO(email-provider): wire a real transactional email sender here
    # (e.g. Resend / Postmark / SES). Until then the code is logged and, in
    # dev only, optionally returned in the response for testing.
    logger.info("[AUTH] email login code issued for %s (expires in %sm)", email, settings.auth_email_code_ttl_minutes)

    debug_code = code if settings.auth_email_debug_return_code else None
    return EmailCodeRequestResponse(sent=True, debug_code=debug_code)


@router.post("/email/verify", response_model=AuthTokenResponse)
def verify_email_code(payload: EmailVerifyRequest, db: Session = Depends(get_db)):
    email = payload.email.strip().lower()
    if not codes.verify_email_login_code(db, email, payload.code):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired code")

    account, created = find_or_create_account_for_identity(
        db, provider="email", provider_id=email, email=email
    )
    logger.info("[AUTH] email sign-in account_id=%s created=%s", account.id, created)
    return _mint_token(account, created=created)


@router.post(
    "/link/telegram/issue",
    response_model=TelegramLinkIssueResponse,
    dependencies=[Depends(verify_internal_token)],
)
def issue_telegram_link_code(payload: TelegramLinkIssueRequest, db: Session = Depends(get_db)):
    """Called by the bot: mint a one-time code the user types into the app."""
    user = db.query(User).filter(User.telegram_id == payload.telegram_id).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    account = ensure_account_for_telegram_user(db, user)
    code, _row = codes.create_telegram_link_code(
        db, account_id=account.id, telegram_id=payload.telegram_id
    )
    return TelegramLinkIssueResponse(
        code=code, expires_in_seconds=settings.auth_link_code_ttl_minutes * 60
    )


@router.post("/link/telegram/redeem", response_model=TelegramLinkRedeemResponse)
def redeem_telegram_link_code(
    payload: TelegramLinkRedeemRequest,
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
):
    """Called by the signed-in app: merge the Telegram account into this one."""
    row = codes.consume_telegram_link_code(db, payload.code)
    if row is None or row.account_id is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")

    source_account = db.query(Account).filter(Account.id == row.account_id).first()
    if source_account is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Link source no longer exists")

    result = link_telegram_account(db, source_account=source_account, target_account=account)
    logger.info("[AUTH] telegram link result=%s account_id=%s", result, account.id)
    return TelegramLinkRedeemResponse(status=result, account_id=account.id)
