"""Learning path ORM models.

A *learning path* groups curated catalog words into an ordered, themed track
(e.g. "IELTS Core Vocabulary", "Business English Essentials"). Paths are built
on top of the existing ``CatalogWord`` data via a link table, so the word
catalog and personal-word features are untouched.
"""

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class LearningPath(Base):
    """A themed, ordered collection of catalog words."""

    __tablename__ = "learning_paths"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    # URL-friendly identifier, e.g. "ielts-core". Unique so it can be used in URLs.
    slug: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # level: "beginner" | "intermediate" | "advanced" | "mixed"
    level: Mapped[str] = mapped_column(String, default="mixed", index=True)
    # goal_type ties a path to an onboarding goal/use case, e.g. "IELTS",
    # "Business English", "Daily English".
    goal_type: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Ordered link rows to catalog words.
    path_words = relationship(
        "LearningPathWord",
        back_populates="learning_path",
        cascade="all, delete-orphan",
        order_by="LearningPathWord.order_index",
    )


class LearningPathWord(Base):
    """Link between a learning path and a catalog word, with an explicit order."""

    __tablename__ = "learning_path_words"
    # A word appears at most once per path.
    __table_args__ = (
        UniqueConstraint(
            "learning_path_id", "word_id", name="uq_path_word"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    learning_path_id: Mapped[int] = mapped_column(
        ForeignKey("learning_paths.id", ondelete="CASCADE"), index=True, nullable=False
    )
    word_id: Mapped[int] = mapped_column(
        ForeignKey("catalog_words.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # Position of the word within the path (0-based).
    order_index: Mapped[int] = mapped_column(Integer, default=0, index=True)

    learning_path = relationship("LearningPath", back_populates="path_words")
    catalog_word = relationship("CatalogWord")


class LearningPathProgress(Base):
    """Tracks how far a user has progressed through a learning path.

    One row per (user, path). ``current_index`` is the 0-based position of the
    word the user is currently on, so "Start study" can resume where they left
    off. ``completed`` flips once the user finishes the last word.
    """

    __tablename__ = "learning_path_progress"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "learning_path_id", name="uq_user_path_progress"
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    learning_path_id: Mapped[int] = mapped_column(
        ForeignKey("learning_paths.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # 0-based position of the word the user is currently studying.
    current_index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    learning_path = relationship("LearningPath")
