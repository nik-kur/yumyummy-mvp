"""
Preview mode (V3 screen 21): an anonymous account per app install.

* ``start_preview`` — find or create the install's anonymous account. An
  anonymous account is simply one with no sign-in identity at all; every real
  account has at least one (apple / google / email / telegram).
* ``free_log_available`` / ``mark_free_log_used`` — the install's single free
  AI meal log. Spent once per install, kept across reinstalls (the install id
  lives in the Keychain) and across the merge into a real account.
* ``merge_preview_into`` — on sign-in, move the anonymous account's diary and
  plan into the real account and delete it.

Per-IP caps limit how many installs and free logs one network can claim in a
day, so wiping the Keychain (a device reset) does not turn into a farm.
"""

from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.merge import merge_account_into
from app.core.config import settings
from app.deps import get_current_account, get_db
from app.models.account import Account, Identity
from app.models.install import Install
from app.models.user import User

logger = logging.getLogger(__name__)


def require_full_account(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
) -> None:
    """Route dependency: preview (anonymous) accounts may not use this."""
    if is_anonymous_account(db, account):
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="preview")


def require_free_log_left(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
) -> None:
    """Route dependency for a step of a log (photo upload): a preview
    account only while its free log is unused."""
    if is_anonymous_account(db, account) and not free_log_available(db, account):
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="preview")


def require_preview_ai_call(
    db: Session = Depends(get_db),
    account: Account = Depends(get_current_account),
) -> None:
    """Route dependency for an AI call before the log (voice transcription):
    a preview account spends one of its AI calls, leaving room for the log.
    Out of those calls with the free log still unused, typing is still free:
    429, not the paywall."""
    if not is_anonymous_account(db, account):
        return
    if not free_log_available(db, account):
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="preview")
    if not _spend_ai_call(db, account, keep_for_log=True):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Type your meal instead")


def client_ip(request: Request) -> Optional[str]:
    """The client IP for the preview caps. Cloudflare's header when present
    (Cloudflare overwrites whatever the client sent). Otherwise the rightmost
    X-Forwarded-For entry: the leftmost is whatever the client sent, the proxy
    appends the address it saw on the right."""
    cf = request.headers.get("cf-connecting-ip")
    xff = request.headers.get("x-forwarded-for")
    # Which source the caps run on (never the address itself): with more than
    # one proxy in front, the rightmost entry is a proxy and every install
    # would share one bucket.
    logger.info(
        "[PREVIEW] ip source=%s xff_entries=%s",
        "cf" if cf else "xff" if xff else "peer",
        len(xff.split(",")) if xff else 0,
    )
    if cf:
        return cf.strip()
    if xff:
        last = xff.split(",")[-1].strip()
        if last:
            return last
    return request.client.host if request.client else None


class PreviewUnavailable(Exception):
    """Preview cannot start for this request (disabled or over a cap)."""


def is_anonymous_account(db: Session, account: Account) -> bool:
    return db.query(Identity.id).filter(Identity.account_id == account.id).first() is None


def install_for_account(db: Session, account: Account) -> Optional[Install]:
    return db.query(Install).filter(Install.account_id == account.id).first()


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _day_ago() -> datetime:
    return _now() - timedelta(days=1)


def start_preview(db: Session, *, install_id: Optional[str], ip: Optional[str]) -> Tuple[Account, bool, str]:
    """Return ``(account, created, install_id)`` for this install's anonymous
    account. Install ids are issued here (``secrets``), never chosen by the
    client: an id the backend does not know gets a fresh one."""
    if not settings.preview_mode_enabled:
        raise PreviewUnavailable("preview mode is off")

    try:
        return _start_preview(db, install_id=install_id, ip=ip)
    except IntegrityError:
        db.rollback()
        return _start_preview(db, install_id=install_id, ip=ip)


def _start_preview(db: Session, *, install_id: Optional[str], ip: Optional[str]) -> Tuple[Account, bool, str]:
    install = (
        db.query(Install).filter(Install.install_id == install_id).first() if install_id else None
    )
    if install is not None and install.account_id is not None:
        account = db.query(Account).filter(Account.id == install.account_id).first()
        if account is not None and is_anonymous_account(db, account):
            install.last_seen_at = _now()
            db.commit()
            return account, False, install.install_id

    if install is None:
        today = db.query(Install).filter(Install.created_at >= _day_ago()).count()
        if today >= settings.preview_installs_per_day:
            logger.warning("[PREVIEW] global install cap hit (%s today)", today)
            raise PreviewUnavailable("preview is busy")
        if ip:
            recent = (
                db.query(Install)
                .filter(Install.ip == ip, Install.created_at >= _day_ago())
                .count()
            )
            if recent >= settings.preview_installs_per_ip_day:
                logger.warning("[PREVIEW] install cap hit ip=%s recent=%s", ip, recent)
                raise PreviewUnavailable("too many new installs from this network")
        install = Install(install_id=secrets.token_urlsafe(24), ip=ip)
        db.add(install)
        db.flush()

    # New install, or the old anonymous account was merged into a real one
    # (bought, signed in, later signed out): a fresh anonymous account. The
    # install keeps `free_log_used_at`, so no second free log.
    account = Account()
    db.add(account)
    db.flush()
    db.add(User(account_id=account.id))
    install.account_id = account.id
    install.last_seen_at = _now()
    db.commit()
    logger.info("[PREVIEW] anonymous account=%s install=%s", account.id, install.id)
    return account, True, install.install_id


def free_log_available(db: Session, account: Account) -> bool:
    """True while this anonymous account's install has not used its free log.
    Preview switched off ends it for sessions already started, too."""
    if not settings.preview_mode_enabled:
        return False
    install = install_for_account(db, account)
    if install is None or install.free_log_used_at is not None:
        return False
    if (install.ai_calls or 0) >= settings.preview_ai_calls_per_install:
        return False
    if install.ip:
        used_here = (
            db.query(Install)
            .filter(Install.ip == install.ip, Install.free_log_used_at >= _day_ago())
            .count()
        )
        if used_here >= settings.preview_free_logs_per_ip_day:
            return False
    return True


def claim_free_log(db: Session, account: Account) -> bool:
    """Atomically take the free log for one AI call. False if another request
    holds it, it is spent, the install is out of AI calls or preview is off."""
    if not settings.preview_mode_enabled:
        return False
    result = db.execute(
        update(Install)
        .where(
            Install.account_id == account.id,
            Install.free_log_used_at.is_(None),
            Install.ai_calls < settings.preview_ai_calls_per_install,
        )
        .values(free_log_used_at=_now(), ai_calls=Install.ai_calls + 1)
    )
    db.commit()
    return result.rowcount == 1


def release_free_log(db: Session, account: Account) -> None:
    """Give the free log back (the call was not a meal, or it failed)."""
    db.execute(
        update(Install).where(Install.account_id == account.id).values(free_log_used_at=None)
    )
    db.commit()


def _spend_ai_call(db: Session, account: Account, *, keep_for_log: bool) -> bool:
    limit = settings.preview_ai_calls_per_install - (1 if keep_for_log else 0)
    result = db.execute(
        update(Install)
        .where(Install.account_id == account.id, Install.ai_calls < limit)
        .values(ai_calls=Install.ai_calls + 1)
    )
    db.commit()
    return result.rowcount == 1


def merge_preview_into(db: Session, *, source_account: Account, target_account: Account) -> bool:
    """Fold an anonymous account into the account the person just signed into.

    Only ever touches an account with no identities, so a real account sent
    by mistake is never merged away. Returns whether a merge happened.
    """
    if source_account.id == target_account.id or not is_anonymous_account(db, source_account):
        return False
    # Keep the install row (free log spent), pointed at the real account.
    for install in db.query(Install).filter(Install.account_id == source_account.id).all():
        install.account_id = target_account.id
    db.flush()
    merge_account_into(db, source_account=source_account, target_account=target_account)
    db.commit()
    logger.info("[PREVIEW] merged anonymous account=%s into account=%s", source_account.id, target_account.id)
    return True
