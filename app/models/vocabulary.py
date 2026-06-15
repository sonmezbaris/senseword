"""Vocabulary word ORM model.

Each row is one word a user is learning, together with everything needed for
the multisensory learning flow (image, pronunciation, example sentence, the
user's own sentence) and the spaced-repetition bookkeeping fields.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Vocabulary(Base):
    __tablename__ = "vocabulary"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # --- Core word content -------------------------------------------------
    word: Mapped[str] = mapped_column(String, nullable=False, index=True)
    meaning: Mapped[str] = mapped_column(String, nullable=False)  # Turkish meaning
    pronunciation: Mapped[str | None] = mapped_column(String, nullable=True)
    example_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)

    # Sentence the learner writes themselves (active recall step).
    user_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Spaced repetition state ------------------------------------------
    # difficulty: "easy" | "medium" | "hard"
    difficulty: Mapped[str] = mapped_column(String, default="medium", nullable=False)
    # status: "new" | "learning" | "learned"
    status: Mapped[str] = mapped_column(String, default="new", nullable=False)
    review_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    next_review_date: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, index=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    owner = relationship("User", back_populates="vocabulary")
    reviews = relationship(
        "ReviewLog",
        back_populates="vocabulary",
        cascade="all, delete-orphan",
    )
