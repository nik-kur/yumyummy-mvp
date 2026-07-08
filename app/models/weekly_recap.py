from sqlalchemy import Column, Integer, Date, Text, DateTime, ForeignKey, UniqueConstraint, func

from app.db.base import Base


class WeeklyRecap(Base):
    """Cache for a user's "Week in Recap" (Задача 6).

    One row per (user, ISO Monday week-start). We recompute the numeric stats
    live on every read (cheap DB aggregate), but persist the LLM-generated
    summary here so opening / re-sending a recap never pays for the model call
    twice. ``stats_json`` is a snapshot taken when the summary was generated —
    kept for the record / future server-side push, not read on the hot path.

    Additive (25(0) clients never touch this table).
    """

    __tablename__ = "weekly_recaps"
    __table_args__ = (
        UniqueConstraint("user_id", "week_start", name="uq_weekly_recap_user_week"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    week_start = Column(Date, nullable=False, index=True)  # Monday of the week
    stats_json = Column(Text, nullable=True)
    llm_summary = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
