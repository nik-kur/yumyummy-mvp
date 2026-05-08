"""
Telegram deep-link acquisition tracking.

Every time a user opens t.me/<bot>?start=<source> we log a row here so we
can attribute traffic sources, measure conversion / retention per
campaign, and analyse multi-touch journeys (a single Telegram user can
click multiple deep links over their lifetime).

First-touch attribution is also stored on `users.acquisition_source` so
the most common "where did this user come from?" question is a single
column read on the user row.
"""

from sqlalchemy import Column, DateTime, Integer, String, func

from app.db.base import Base


class AcquisitionEvent(Base):
    __tablename__ = "acquisition_events"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, index=True, nullable=False)
    source = Column(String, index=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
