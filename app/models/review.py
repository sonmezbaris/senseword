"""Review log ORM model.

Stores the history of each review so we can show progress statistics and,
later, feed data into a smarter (possibly AI-driven) scheduling algorithm.
"""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class ReviewLog(Base):
    __tablename__ = "review_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    vocabulary_id: Mapped[int] = mapped_column(
        ForeignKey("vocabulary.id", ondelete="CASCADE"), index=True, nullable=False
    )

    # The difficulty rating the user gave during this review.
    result: Mapped[str] = mapped_column(String, nullable=False)  # easy | medium | hard
    reviewed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    vocabulary = relationship("Vocabulary", back_populates="reviews")
