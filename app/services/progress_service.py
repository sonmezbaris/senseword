"""User word progress service.

Read/write helpers for ``UserWordProgress``. The algorithm is deliberately
simple for the MVP:

  * Each exposure (seeing/completing a word) increments ``times_seen``.
  * A correct answer raises ``memory_strength`` (and ``times_correct``).
  * A wrong answer lowers it (and ``times_wrong``).
  * ``status`` and ``next_review_at`` are derived from ``memory_strength`` so
    weak words come back sooner.

All of this can be swapped for SM-2 / AI scheduling later without changing the
routers, since they only call these functions.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.models.word_progress import (
    STATUS_LEARNING,
    STATUS_MASTERED,
    STATUS_NEW,
    STATUS_REVIEWING,
    UserWordProgress,
)

# How much a single answer moves the 0–100 memory strength.
CORRECT_STEP = 20
WRONG_STEP = 15

# Weak = a word the user has seen but doesn't know well yet.
WEAK_THRESHOLD = 50

# Weak Words page criteria (broader than the dashboard counter):
# low strength, repeatedly missed, or still in the "learning" stage.
WEAK_PAGE_STRENGTH = 40
WEAK_WRONG_THRESHOLD = 3

# --- Status thresholds (memory strength) -----------------------------------
#   strength < 30        -> learning
#   30 <= strength <= 80 -> reviewing
#   strength > 80        -> mastered
STATUS_LEARNING_MAX = 30
STATUS_MASTERED_MIN = 80

# --- Spaced-repetition intervals (days) by memory strength -----------------
# Edit this single table to retune the schedule. Each entry is
# (inclusive_max_strength, interval_in_days).
REVIEW_INTERVALS = [
    (20, 0),    # 0–20: review today
    (40, 1),    # 21–40: tomorrow
    (60, 3),    # 41–60: in 3 days
    (80, 7),    # 61–80: in 7 days
    (100, 14),  # 81–100: in 14 days
]


def _clamp(value: int, low: int = 0, high: int = 100) -> int:
    return max(low, min(high, value))


def _interval_days(strength: int) -> int:
    """Days until the next review for a given memory strength (see table)."""
    strength = _clamp(strength)
    for max_strength, days in REVIEW_INTERVALS:
        if strength <= max_strength:
            return days
    return REVIEW_INTERVALS[-1][1]


def calculate_next_review_at(
    memory_strength: int, *, from_time: datetime | None = None
) -> datetime:
    """Return when a word should next be reviewed, based on memory strength.

    Transparent MVP schedule (see ``REVIEW_INTERVALS``):
        0–20 today · 21–40 tomorrow · 41–60 +3d · 61–80 +7d · 81–100 +14d
    """
    now = from_time or datetime.utcnow()
    return now + timedelta(days=_interval_days(memory_strength))


def status_for_strength(strength: int) -> str:
    """Coarse learning status derived from memory strength (requirement 5)."""
    if strength > STATUS_MASTERED_MIN:
        return STATUS_MASTERED
    if strength >= STATUS_LEARNING_MAX:
        return STATUS_REVIEWING
    return STATUS_LEARNING


# ---------------------------------------------------------------------------
# Core operations
# ---------------------------------------------------------------------------
def get_or_create_progress(
    db: Session, user_id: int, word_id: int
) -> UserWordProgress:
    """Return the progress row for a (user, word), creating it if missing."""
    progress = (
        db.query(UserWordProgress)
        .filter(
            UserWordProgress.user_id == user_id,
            UserWordProgress.word_id == word_id,
        )
        .first()
    )
    if progress is None:
        progress = UserWordProgress(
            user_id=user_id,
            word_id=word_id,
            status=STATUS_NEW,
            memory_strength=0,
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)
    return progress


def mark_word_seen(db: Session, user_id: int, word_id: int) -> UserWordProgress:
    """Record an exposure: bump ``times_seen`` and ``last_seen_at``."""
    progress = get_or_create_progress(db, user_id, word_id)
    progress.times_seen += 1
    progress.last_seen_at = datetime.utcnow()
    if progress.status == STATUS_NEW:
        progress.status = STATUS_LEARNING
    db.commit()
    db.refresh(progress)
    return progress


def update_memory_strength(
    db: Session, user_id: int, word_id: int, result: str
) -> UserWordProgress:
    """Apply an answer result and recompute strength, status, and schedule.

    ``result`` is "correct" or "wrong". Anything other than "correct" is
    treated as wrong, so callers can stay simple.
    """
    progress = get_or_create_progress(db, user_id, word_id)

    if result == "correct":
        progress.memory_strength = _clamp(progress.memory_strength + CORRECT_STEP)
        progress.times_correct += 1
    else:
        progress.memory_strength = _clamp(progress.memory_strength - WRONG_STEP)
        progress.times_wrong += 1

    progress.last_seen_at = datetime.utcnow()
    progress.status = status_for_strength(progress.memory_strength)
    progress.next_review_at = calculate_next_review_at(progress.memory_strength)

    db.commit()
    db.refresh(progress)
    return progress


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------
def get_due_reviews(db: Session, user_id: int) -> list[UserWordProgress]:
    """Progress rows whose ``next_review_at`` has passed (soonest first)."""
    now = datetime.utcnow()
    return (
        db.query(UserWordProgress)
        .filter(
            UserWordProgress.user_id == user_id,
            UserWordProgress.next_review_at.isnot(None),
            UserWordProgress.next_review_at <= now,
        )
        .order_by(UserWordProgress.next_review_at.asc())
        .all()
    )


def get_weak_words(
    db: Session, user_id: int, *, threshold: int = WEAK_THRESHOLD
) -> list[UserWordProgress]:
    """Seen words the user struggles with (low strength), weakest first."""
    return (
        db.query(UserWordProgress)
        .filter(
            UserWordProgress.user_id == user_id,
            UserWordProgress.times_seen > 0,
            UserWordProgress.memory_strength < threshold,
        )
        .order_by(
            UserWordProgress.memory_strength.asc(),
            UserWordProgress.last_seen_at.asc(),
        )
        .all()
    )


def _weak_page_filter(user_id: int):
    """Shared predicate for the Weak Words page (see ``WEAK_*`` constants).

    A word qualifies if the user has seen it AND any of:
      * memory strength below ``WEAK_PAGE_STRENGTH``
      * wrong at least ``WEAK_WRONG_THRESHOLD`` times
      * still in the "learning" status
    """
    return (
        UserWordProgress.user_id == user_id,
        UserWordProgress.times_seen > 0,
        or_(
            UserWordProgress.memory_strength < WEAK_PAGE_STRENGTH,
            UserWordProgress.times_wrong >= WEAK_WRONG_THRESHOLD,
            UserWordProgress.status == STATUS_LEARNING,
        ),
    )


def list_weak_words(db: Session, user_id: int) -> list[UserWordProgress]:
    """Weak-word progress rows with their catalog word eagerly loaded.

    Used by the Weak Words page so the template can show the English word,
    Turkish meaning, and stats without extra queries.
    """
    return (
        db.query(UserWordProgress)
        .options(joinedload(UserWordProgress.catalog_word))
        .filter(*_weak_page_filter(user_id))
        .order_by(
            UserWordProgress.memory_strength.asc(),
            UserWordProgress.times_wrong.desc(),
        )
        .all()
    )


def get_next_weak_word(db: Session, user_id: int) -> UserWordProgress | None:
    """Weakest word to study next (for the "Review all weak words" flow)."""
    return (
        db.query(UserWordProgress)
        .filter(*_weak_page_filter(user_id))
        .order_by(
            UserWordProgress.memory_strength.asc(),
            UserWordProgress.times_wrong.desc(),
        )
        .first()
    )


def get_next_due_word(db: Session, user_id: int) -> UserWordProgress | None:
    """The single most-overdue word progress row, or None if nothing is due."""
    now = datetime.utcnow()
    return (
        db.query(UserWordProgress)
        .filter(
            UserWordProgress.user_id == user_id,
            UserWordProgress.next_review_at.isnot(None),
            UserWordProgress.next_review_at <= now,
        )
        .order_by(UserWordProgress.next_review_at.asc())
        .first()
    )


# ---------------------------------------------------------------------------
# Dashboard counts
# ---------------------------------------------------------------------------
def count_due_reviews(db: Session, user_id: int) -> int:
    """How many words are due for review now (review-today included)."""
    now = datetime.utcnow()
    return (
        db.query(func.count(UserWordProgress.id))
        .filter(
            UserWordProgress.user_id == user_id,
            UserWordProgress.next_review_at.isnot(None),
            UserWordProgress.next_review_at <= now,
        )
        .scalar()
        or 0
    )


def count_weak_words(
    db: Session, user_id: int, *, threshold: int = WEAK_THRESHOLD
) -> int:
    return (
        db.query(func.count(UserWordProgress.id))
        .filter(
            UserWordProgress.user_id == user_id,
            UserWordProgress.times_seen > 0,
            UserWordProgress.memory_strength < threshold,
        )
        .scalar()
        or 0
    )


def count_mastered_words(db: Session, user_id: int) -> int:
    return (
        db.query(func.count(UserWordProgress.id))
        .filter(
            UserWordProgress.user_id == user_id,
            UserWordProgress.status == STATUS_MASTERED,
        )
        .scalar()
        or 0
    )


def progress_summary(db: Session, user_id: int) -> dict:
    """Bundle the dashboard counts in one call."""
    return {
        "due_reviews": count_due_reviews(db, user_id),
        "weak_words": count_weak_words(db, user_id),
        "mastered_words": count_mastered_words(db, user_id),
    }
