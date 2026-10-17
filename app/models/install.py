"""
App installs, for preview mode (V3 screen 21).

Someone who closes the paywall offer without buying can look around the real
app on an *anonymous* account and log one meal with AI for free. The free log
belongs to the install, not the account: ``install_id`` is a random id the app
keeps in the iOS Keychain, which survives deleting and reinstalling the app,
so a reinstall does not hand out another free log.

``account_id`` points at the anonymous account while preview lasts; when the
person signs in (after buying) that account is merged into the real one and
deleted, and the row is kept — with ``free_log_used_at`` — so the install
stays spent. Real accounts never depend on this table.
"""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func

from app.db.base import Base


class Install(Base):
    __tablename__ = "installs"

    id = Column(Integer, primary_key=True, index=True)
    install_id = Column(String(128), nullable=False, unique=True, index=True)
    account_id = Column(
        Integer,
        ForeignKey("accounts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_seen_at = Column(DateTime(timezone=True), server_default=func.now())
    free_log_used_at = Column(DateTime(timezone=True), nullable=True)
    # AI calls this install made in preview (meal logs that came back as
    # something else, voice transcriptions): capped, so preview cannot be
    # farmed for free AI.
    ai_calls = Column(Integer, nullable=False, server_default="0", default=0)
    # Client IP at registration, for the per-IP caps against reinstall farming.
    ip = Column(String(64), nullable=True, index=True)
