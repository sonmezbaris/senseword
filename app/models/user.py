"""User ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    # Stores the bcrypt/pbkdf2 hash, never the plain password.
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    # Onboarding: the learner's chosen goal (e.g. "IELTS"). Null until selected,
    # which is how we know to show the onboarding flow.
    learning_goal: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # One user owns many vocabulary words.
    vocabulary = relationship(
        "Vocabulary",
        back_populates="owner",
        cascade="all, delete-orphan",
    )

    # Per-word learning progress across the curated catalog.
    word_progress = relationship(
        "UserWordProgress",
        back_populates="user",
        cascade="all, delete-orphan",
    )

    # Daily mission progress rows (one per day).
    daily_missions = relationship(
        "DailyMissionProgress",
        back_populates="user",
        cascade="all, delete-orphan",
    )
