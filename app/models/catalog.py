"""Curated vocabulary catalog ORM models.

These models back the *preloaded* exam-vocabulary dataset (TOEFL / IELTS / SAT /
GRE / academic). Unlike ``Vocabulary`` (which holds words an individual user
adds themselves), ``CatalogWord`` rows are shared/global content seeded in
advance — designed to scale to ~10,000 records imported from JSON or CSV.

``UserWordAnswer`` stores each user's own sentence and voice recording for a
catalog word, so progress is saved for later review.
"""

from datetime import datetime

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class CatalogWord(Base):
    """One curated vocabulary entry from the shared exam dataset."""

    __tablename__ = "catalog_words"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # --- Core content (matches the seed JSON schema) -----------------------
    word: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    turkish_translation: Mapped[str] = mapped_column(String, nullable=False)
    pronunciation: Mapped[str | None] = mapped_column(String, nullable=True)
    # Optional pre-recorded audio. When absent, the UI falls back to browser TTS.
    audio_url: Mapped[str | None] = mapped_column(String, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String, nullable=True)
    example_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    example_sentence_tr: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- Classification ----------------------------------------------------
    # level: "beginner" | "intermediate" | "advanced"
    level: Mapped[str] = mapped_column(String, default="intermediate", index=True)
    # exam_category: e.g. ["TOEFL", "IELTS", "SAT"]. Stored as JSON so it works
    # on SQLite today and JSON/JSONB on PostgreSQL later without code changes.
    exam_category: Mapped[list[str]] = mapped_column(JSON, default=list)
    # word_type: "noun" | "verb" | "adjective" | "adverb" | ...
    word_type: Mapped[str | None] = mapped_column(String, nullable=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    answers = relationship(
        "UserWordAnswer",
        back_populates="catalog_word",
        cascade="all, delete-orphan",
    )

    # Per-user learning progress for this word.
    progress_entries = relationship(
        "UserWordProgress",
        back_populates="catalog_word",
        cascade="all, delete-orphan",
    )


class UserWordAnswer(Base):
    """A user's saved sentence + recording for a single catalog word."""

    __tablename__ = "user_word_answers"
    # One answer per (user, word); saving again updates the existing row.
    __table_args__ = (
        UniqueConstraint("user_id", "catalog_word_id", name="uq_user_catalog_word"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    catalog_word_id: Mapped[int] = mapped_column(
        ForeignKey("catalog_words.id", ondelete="CASCADE"), index=True, nullable=False
    )

    user_sentence: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Path/URL to the user's uploaded voice recording (served from /static).
    recording_url: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    catalog_word = relationship("CatalogWord", back_populates="answers")
