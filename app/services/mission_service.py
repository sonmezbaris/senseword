"""Daily mission service.

Tracks each user's progress toward a simple daily goal to encourage them to
come back. The goals live here (not in the DB) so they're easy to tweak:

    10 new words · 20 review words · 3 voice practices

All writes are idempotent per day via a single (user, date) row. Routers call
the ``record_*`` helpers when the matching activity happens during study.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy.orm import Session

from app.models.mission import DailyMissionProgress

# Default daily mission goals. Tune freely; no migration needed.
DEFAULT_MISSION = {
    "new_words": 10,
    "review_words": 20,
    "voice_practices": 3,
}


def _today() -> date:
    """The current day in UTC (matches the rest of the app's timestamps)."""
    return datetime.utcnow().date()


def get_or_create_today(db: Session, user_id: int) -> DailyMissionProgress:
    """Return today's mission row for a user, creating it if missing."""
    today = _today()
    row = (
        db.query(DailyMissionProgress)
        .filter(
            DailyMissionProgress.user_id == user_id,
            DailyMissionProgress.date == today,
        )
        .first()
    )
    if row is None:
        row = DailyMissionProgress(user_id=user_id, date=today)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _refresh_completion(row: DailyMissionProgress) -> None:
    """Recompute ``mission_completed`` from the three counters vs the goals."""
    row.mission_completed = (
        row.new_words_completed >= DEFAULT_MISSION["new_words"]
        and row.review_words_completed >= DEFAULT_MISSION["review_words"]
        and row.voice_practices_completed >= DEFAULT_MISSION["voice_practices"]
    )


def record_new_word(db: Session, user_id: int) -> DailyMissionProgress:
    """Count one new word studied toward today's mission."""
    row = get_or_create_today(db, user_id)
    row.new_words_completed += 1
    _refresh_completion(row)
    db.commit()
    db.refresh(row)
    return row


def record_review_word(db: Session, user_id: int) -> DailyMissionProgress:
    """Count one review word completed toward today's mission."""
    row = get_or_create_today(db, user_id)
    row.review_words_completed += 1
    _refresh_completion(row)
    db.commit()
    db.refresh(row)
    return row


def record_voice_practice(db: Session, user_id: int) -> DailyMissionProgress:
    """Count one voice practice (recording) toward today's mission."""
    row = get_or_create_today(db, user_id)
    row.voice_practices_completed += 1
    _refresh_completion(row)
    db.commit()
    db.refresh(row)
    return row


def _bar(done: int, goal: int) -> dict:
    """A single mission line: done/goal capped at the goal, with a percentage."""
    capped = min(done, goal)
    percent = round(capped / goal * 100) if goal else 100
    return {"done": done, "goal": goal, "percent": percent, "met": done >= goal}


def get_today_summary(db: Session, user_id: int) -> dict:
    """Dashboard-ready view of today's mission progress."""
    row = get_or_create_today(db, user_id)
    return {
        "completed": row.mission_completed,
        "new_words": _bar(row.new_words_completed, DEFAULT_MISSION["new_words"]),
        "review_words": _bar(
            row.review_words_completed, DEFAULT_MISSION["review_words"]
        ),
        "voice_practices": _bar(
            row.voice_practices_completed, DEFAULT_MISSION["voice_practices"]
        ),
    }
