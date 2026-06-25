"""
Short-lived one-time codes used by passwordless auth flows.

Two purposes today:

* ``email_login``   — a 6-digit code emailed to the user; redeemed to mint a
  JWT for the matching email identity.
* ``telegram_link`` — a code issued *inside the Telegram bot* (tied to that
  user's account). The signed-in app user types it to merge their Telegram
  history into the account they are using on the phone.

Codes are stored hashed (SHA-256), never in plaintext, and expire quickly.
"""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    func,
)

from app.db.base import Base


class AuthOneTimeCode(Base):
    __tablename__ = "auth_one_time_codes"

    id = Column(Integer, primary_key=True, index=True)

    purpose = Column(String, nullable=False, index=True)  # 'email_login' | 'telegram_link'
    code_hash = Column(String, nullable=False, index=True)

    # For 'email_login' this is the lowercased email. For 'telegram_link' this
    # is the issuing telegram_id (informational; account_id is authoritative).
    subject = Column(String, nullable=True, index=True)

    # Set for 'telegram_link': the account that owns the code (the Telegram
    # account to be merged into whoever redeems the code).
    account_id = Column(
        Integer,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=True,
    )

    expires_at = Column(DateTime(timezone=True), nullable=False)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
