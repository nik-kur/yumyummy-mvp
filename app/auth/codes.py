"""
One-time code generation / verification for passwordless flows.

Codes are stored only as SHA-256 hashes. Email login uses a 6-digit numeric
code; Telegram linking uses an 8-char uppercase code that's easy to read out
of the bot and type into the app.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.auth_code import AuthOneTimeCode

_LINK_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # no ambiguous chars (0/O, 1/I)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def hash_code(code: str) -> str:
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def generate_numeric_code(length: int = 6) -> str:
    return "".join(secrets.choice("0123456789") for _ in range(length))


def generate_link_code(length: int = 8) -> str:
    return "".join(secrets.choice(_LINK_ALPHABET) for _ in range(length))


# --- email login ----------------------------------------------------------

def create_email_login_code(db: Session, email: str) -> Tuple[str, AuthOneTimeCode]:
    email = email.strip().lower()
    code = generate_numeric_code(6)
    row = AuthOneTimeCode(
        purpose="email_login",
        code_hash=hash_code(code),
        subject=email,
        expires_at=_now() + timedelta(minutes=settings.auth_email_code_ttl_minutes),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return code, row


def verify_email_login_code(db: Session, email: str, code: str) -> bool:
    """Validate + consume an email login code. Returns True on success."""
    email = email.strip().lower()
    row = (
        db.query(AuthOneTimeCode)
        .filter(
            AuthOneTimeCode.purpose == "email_login",
            AuthOneTimeCode.subject == email,
            AuthOneTimeCode.code_hash == hash_code(code),
            AuthOneTimeCode.consumed_at.is_(None),
        )
        .order_by(AuthOneTimeCode.id.desc())
        .first()
    )
    if row is None:
        return False
    if _as_utc(row.expires_at) < _now():
        return False
    row.consumed_at = _now()
    db.commit()
    return True


# --- telegram linking ------------------------------------------------------

def create_telegram_link_code(
    db: Session, *, account_id: int, telegram_id: Optional[str]
) -> Tuple[str, AuthOneTimeCode]:
    code = generate_link_code(8)
    row = AuthOneTimeCode(
        purpose="telegram_link",
        code_hash=hash_code(code),
        subject=str(telegram_id) if telegram_id is not None else None,
        account_id=account_id,
        expires_at=_now() + timedelta(minutes=settings.auth_link_code_ttl_minutes),
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return code, row


def consume_telegram_link_code(db: Session, code: str) -> Optional[AuthOneTimeCode]:
    """Validate + consume a telegram-link code. Returns the row (with the
    issuing ``account_id``) on success, else ``None``."""
    row = (
        db.query(AuthOneTimeCode)
        .filter(
            AuthOneTimeCode.purpose == "telegram_link",
            AuthOneTimeCode.code_hash == hash_code(code),
            AuthOneTimeCode.consumed_at.is_(None),
        )
        .order_by(AuthOneTimeCode.id.desc())
        .first()
    )
    if row is None:
        return None
    if _as_utc(row.expires_at) < _now():
        return None
    row.consumed_at = _now()
    db.commit()
    return row
