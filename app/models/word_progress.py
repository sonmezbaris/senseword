"""Per-user, per-word learning progress.

Tracks how well a user knows each catalog word: a coarse ``status``, a
0–100 ``memory_strength``, exposure/answer counters, and a simple review
schedule. This sits alongside ``UserWordAnswer`` (which stores the user's
sentence + recording) and powers spaced-style review and "weak word" surfacing.

The MVP keeps the maths intentionally simple (see ``progress_service``); the
schema is rich enough to swap in a smarter algorithm later without migrations.
"""

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Valid status values, in rough learning order.
STATUS_NEW = "new"
STATUS_LEARNING = "learning"
STATUS_REVIEWING = "reviewing"
STATUS_MASTERED = "mastered"
STATUSES = (STATUS_NEW, STATUS_LEARNING, STATUS_REVIEWING, STATUS_MASTERED)


class UserWordProgress(Base):
    """One row per (user, catalog word) capturing the user's mastery."""

    __tablename__ = "user_word_progress"
    __table_args__ = (
        UniqueConstraint("user_id", "word_id", name="uq_user_word_progress"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # The studied word is a catalog word (the curated study dataset).
    word_id: Mapped[int] = mapped_column(
        ForeignKey("catalog_words.id", ondelete="CASCADE"), index=True, nullable=False
    )

    status: Mapped[str] = mapped_column(String, default=STATUS_NEW, nullable=False)
    # 0 = not known at all, 100 = fully mastered.
    memory_strength: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    times_seen: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    times_correct: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    times_wrong: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    next_review_at: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    user = relationship("User", back_populates="word_progress")
    catalog_word = relationship("CatalogWord", back_populates="progress_entries")
