"""
Account/identity resolution helpers shared by the auth endpoints.

Key ideas:
  * An :class:`Account` is the owner of everything a person sees.
  * A :class:`User` row is the per-account diary/profile container that all
    existing bot code operates on.
  * ``find_or_create_account_for_identity`` is the single entry point used by
    every provider sign-in (Apple/Google/email): it returns the existing
    account for a known identity, or provisions a fresh account + identity +
    empty ``users`` container for a new one.
"""

from __future__ import annotations

from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.account import Account, Identity
from app.models.user import User


def get_identity(db: Session, provider: str, provider_id: str) -> Optional[Identity]:
    return (
        db.query(Identity)
        .filter(Identity.provider == provider, Identity.provider_id == str(provider_id))
        .first()
    )


def account_member_users(db: Session, account_id: int) -> List[User]:
    return (
        db.query(User)
        .filter(User.account_id == account_id)
        .order_by(User.id.asc())
        .all()
    )


def get_primary_user(db: Session, account: Account) -> User:
    """Return the account's diary container, creating one if missing.

    The primary user is the lowest-id member (the Telegram user for
    bot-origin accounts, the app-created user otherwise). A defensive
    create covers accounts that somehow have no member yet.
    """
    members = account_member_users(db, account.id)
    if members:
        return members[0]
    user = User(account_id=account.id)
    db.add(user)
    db.flush()
    return user


def find_or_create_account_for_identity(
    db: Session,
    *,
    provider: str,
    provider_id: str,
    email: Optional[str] = None,
) -> Tuple[Account, bool]:
    """Resolve (or provision) the account behind a provider identity.

    Returns ``(account, created)`` where ``created`` is True if a brand-new
    account was provisioned.
    """
    identity = get_identity(db, provider, provider_id)
    if identity is not None:
        account = db.query(Account).filter(Account.id == identity.account_id).first()
        if account is not None:
            if email and not account.primary_email:
                account.primary_email = email.strip().lower()
                db.commit()
            return account, False

    # New identity -> new account + empty diary container.
    account = Account(primary_email=email.strip().lower() if email else None)
    db.add(account)
    db.flush()

    db.add(
        Identity(
            account_id=account.id,
            provider=provider,
            provider_id=str(provider_id),
            email=email.strip().lower() if email else None,
        )
    )
    db.add(User(account_id=account.id))  # telegram_id stays NULL for app users
    db.commit()
    db.refresh(account)
    return account, True


def ensure_account_for_telegram_user(db: Session, user: User) -> Account:
    """Guarantee an existing Telegram user has an account + telegram identity.

    Used when the bot issues a link code for a user created before the
    accounts backfill (or any edge where account_id is unexpectedly NULL).
    """
    if user.account_id:
        account = db.query(Account).filter(Account.id == user.account_id).first()
        if account is not None:
            return account

    account = Account()
    db.add(account)
    db.flush()
    user.account_id = account.id
    if user.telegram_id and get_identity(db, "telegram", user.telegram_id) is None:
        db.add(
            Identity(
                account_id=account.id,
                provider="telegram",
                provider_id=str(user.telegram_id),
            )
        )
    db.commit()
    db.refresh(account)
    return account
