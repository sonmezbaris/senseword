"""Daily mission progress ORM model.

A lightweight daily-goal tracker to boost retention: each user gets one row per
calendar day counting new words studied, review words completed, and voice
practices recorded. Goals themselves live in ``mission_service`` (not stored
per row) so they can be tuned without a migration.
"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class DailyMissionProgress(Base):
    """One row per (user, day) tracking progress toward the daily mission."""

    __tablename__ = "daily_mission_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_user_mission_date"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # The calendar day this progress is for (UTC).
    date: Mapped[date] = mapped_column(Date, index=True, nullable=False)

    new_words_completed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    review_words_completed: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    voice_practices_completed: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )
    # Flips true once all three goals are met for the day.
    mission_completed: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="daily_missions")
