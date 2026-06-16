"""User ORM model."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Subscription plan identifiers (stored in ``plan`` column).
PLAN_FREE = "free"
PLAN_PREMIUM = "premium"
PLAN_FOUNDING = "founding"

# Subscription lifecycle states (stored in ``subscription_status``).
SUB_INACTIVE = "inactive"
SUB_ACTIVE = "active"
SUB_TRIALING = "trialing"
SUB_CANCELED = "canceled"
SUB_EXPIRED = "expired"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    learning_goal: Mapped[str | None] = mapped_column(String, nullable=True)

    # --- Subscription (payment provider wired later) -------------------------
    plan: Mapped[str] = mapped_column(String, default=PLAN_FREE, nullable=False)
    subscription_status: Mapped[str] = mapped_column(
        String, default=SUB_INACTIVE, nullable=False
    )
    subscription_provider: Mapped[str] = mapped_column(
        String, default="manual", nullable=False
    )
    subscription_customer_id: Mapped[str | None] = mapped_column(String, nullable=True)
    subscription_id: Mapped[str | None] = mapped_column(String, nullable=True)
    subscription_current_period_end: Mapped[datetime | None] = mapped_column(
        DateTime, nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow
    )

    vocabulary = relationship(
        "Vocabulary",
        back_populates="owner",
        cascade="all, delete-orphan",
    )
    word_progress = relationship(
        "UserWordProgress",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    daily_missions = relationship(
        "DailyMissionProgress",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    daily_usage = relationship(
        "UserDailyUsage",
        back_populates="user",
        cascade="all, delete-orphan",
    )
