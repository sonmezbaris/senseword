"""Review service: simple spaced-repetition scheduling and statistics.

The scheduling here is intentionally simple for the MVP. Each difficulty
rating maps to a fixed interval that grows with the number of successful
reviews. This can later be swapped for SM-2 / Anki-style or AI-driven
scheduling without touching the routers.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.review import ReviewLog
from app.models.vocabulary import Vocabulary
from app.schemas.review import DashboardStats

# Base interval (in days) per difficulty rating. Harder words come back sooner.
BASE_INTERVALS = {
    "hard": 1,
    "medium": 3,
    "easy": 7,
}

# Once a word reaches this many reviews we consider it "learned".
LEARNED_THRESHOLD = 4


def _next_interval_days(result: str, review_count: int) -> int:
    """Grow the interval with each review so easy words space out over time."""
    base = BASE_INTERVALS.get(result, 3)
    # Multiplier increases as the learner gets the word right more often.
    return base * max(1, review_count)


def get_due_words(db: Session, user_id: int) -> list[Vocabulary]:
    """Words whose next_review_date has passed (or is now)."""
    now = datetime.utcnow()
    return (
        db.query(Vocabulary)
        .filter(
            Vocabulary.user_id == user_id,
            Vocabulary.next_review_date <= now,
        )
        .order_by(Vocabulary.next_review_date.asc())
        .all()
    )


def get_next_due_word(db: Session, user_id: int) -> Vocabulary | None:
    due = get_due_words(db, user_id)
    return due[0] if due else None


def record_review(db: Session, word: Vocabulary, result: str) -> Vocabulary:
    """Apply a review result: update difficulty, schedule, status, and log it."""
    word.difficulty = result
    word.review_count += 1

    interval = _next_interval_days(result, word.review_count)
    word.next_review_date = datetime.utcnow() + timedelta(days=interval)

    if word.review_count >= LEARNED_THRESHOLD and result != "hard":
        word.status = "learned"
    elif word.status == "new":
        word.status = "learning"

    db.add(ReviewLog(vocabulary_id=word.id, result=result))
    db.commit()
    db.refresh(word)
    return word


def get_dashboard_stats(db: Session, user_id: int) -> DashboardStats:
    total = (
        db.query(func.count(Vocabulary.id))
        .filter(Vocabulary.user_id == user_id)
        .scalar()
    )
    learned = (
        db.query(func.count(Vocabulary.id))
        .filter(Vocabulary.user_id == user_id, Vocabulary.status == "learned")
        .scalar()
    )
    due = len(get_due_words(db, user_id))

    start_of_day = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    reviews_today = (
        db.query(func.count(ReviewLog.id))
        .join(Vocabulary, ReviewLog.vocabulary_id == Vocabulary.id)
        .filter(
            Vocabulary.user_id == user_id,
            ReviewLog.reviewed_at >= start_of_day,
        )
        .scalar()
    )

    return DashboardStats(
        total_words=total or 0,
        learned_words=learned or 0,
        due_for_review=due,
        reviews_today=reviews_today or 0,
    )
