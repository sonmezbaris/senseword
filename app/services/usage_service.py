"""Daily usage limits for Free-plan users."""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.usage import UserDailyUsage
from app.models.user import User
from app.services import subscription_service

FREE_NEW_WORDS_DAILY = 10
FREE_REVIEWS_DAILY = 20


def _today() -> date:
    return datetime.utcnow().date()


def get_or_create_today_usage(db: Session, user_id: int) -> UserDailyUsage:
    today = _today()
    row = (
        db.query(UserDailyUsage)
        .filter(
            UserDailyUsage.user_id == user_id,
            UserDailyUsage.date == today,
        )
        .first()
    )
    if row is None:
        row = UserDailyUsage(user_id=user_id, date=today)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def get_today_usage_summary(db: Session, user: User) -> dict:
    """Dashboard-friendly usage counters."""
    usage = get_or_create_today_usage(db, user.id)
    unlimited = subscription_service.user_has_premium_access(user)
    return {
        "unlimited": unlimited,
        "new_words": usage.new_words_count,
        "new_words_limit": FREE_NEW_WORDS_DAILY,
        "reviews": usage.review_count,
        "reviews_limit": FREE_REVIEWS_DAILY,
        "new_words_remaining": max(0, FREE_NEW_WORDS_DAILY - usage.new_words_count),
        "reviews_remaining": max(0, FREE_REVIEWS_DAILY - usage.review_count),
    }


def can_study_new_word(db: Session, user: User) -> bool:
    if subscription_service.user_has_premium_access(user):
        return True
    usage = get_or_create_today_usage(db, user.id)
    return usage.new_words_count < FREE_NEW_WORDS_DAILY


def can_review_word(db: Session, user: User) -> bool:
    if subscription_service.user_has_premium_access(user):
        return True
    usage = get_or_create_today_usage(db, user.id)
    return usage.review_count < FREE_REVIEWS_DAILY


def increment_new_word_usage(db: Session, user_id: int) -> UserDailyUsage:
    usage = get_or_create_today_usage(db, user_id)
    usage.new_words_count += 1
    db.commit()
    db.refresh(usage)
    return usage


def increment_review_usage(db: Session, user_id: int) -> UserDailyUsage:
    usage = get_or_create_today_usage(db, user_id)
    usage.review_count += 1
    db.commit()
    db.refresh(usage)
    return usage
