"""
Cross-platform identity model.

The ``users`` table predates the mobile app and is keyed on ``telegram_id``.
To support a single profile that is shared across the Telegram bot, the iOS
app and (later) Android, we introduce two new tables:

* ``accounts``   — one row per *human*. Owns the profile, diary and
  entitlement. Everything a person sees on any device hangs off their account.
* ``identities`` — the ways a person can sign in (telegram / apple / google /
  email). Many identities point at one account, which is how "log in with
  Apple on the phone" and "the Telegram bot" resolve to the same diary.

A ``users`` row remains the per-account *container* for the diary (meals,
days, saved meals) and the billing columns, so all existing bot code keeps
working unchanged. Each account has one or more ``users`` rows linked via
``users.account_id`` (normally exactly one; more than one can exist briefly
after a Telegram<->app link, until :func:`app.auth.merge.merge_users`
consolidates them).
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import relationship

from app.db.base import Base


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Convenience metadata (not authoritative — identities are the source of
    # truth for how a person signs in).
    display_name = Column(String, nullable=True)
    primary_email = Column(String, nullable=True, index=True)

    identities = relationship(
        "Identity",
        back_populates="account",
        cascade="all, delete-orphan",
    )
    users = relationship("User", back_populates="account")


class Identity(Base):
    __tablename__ = "identities"

    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(
        Integer,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # 'telegram' | 'apple' | 'google' | 'email'
    provider = Column(String, nullable=False)
    # Stable, provider-specific subject id: telegram_id, Apple `sub`,
    # Google `sub`, or the lowercased email address for the 'email' provider.
    provider_id = Column(String, nullable=False)
    # Best-effort email captured from the provider (display only).
    email = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    account = relationship("Account", back_populates="identities")

    __table_args__ = (
        UniqueConstraint("provider", "provider_id", name="uq_identity_provider"),
    )
