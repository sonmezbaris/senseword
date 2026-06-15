"""Catalog service: read the curated word dataset and save user answers.

This is the data-access layer for the preloaded learning flow. The routers and
templates never touch the ORM directly — they go through these functions, so
the storage can scale (10k+ rows) or change without UI changes.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.catalog import CatalogWord, UserWordAnswer

# Levels in learning order. "all" is a virtual level meaning "no filter".
LEVELS = ("beginner", "intermediate", "advanced")


def _base_query(db: Session, level: str | None):
    """Catalog query ordered by id, optionally filtered to one level."""
    q = db.query(CatalogWord).order_by(CatalogWord.id.asc())
    if level and level in LEVELS:
        q = q.filter(CatalogWord.level == level)
    return q


# ---------------------------------------------------------------------------
# Catalog reads
# ---------------------------------------------------------------------------
def count_words(db: Session, level: str | None = None) -> int:
    """Number of catalog words, optionally within a single level."""
    q = db.query(func.count(CatalogWord.id))
    if level and level in LEVELS:
        q = q.filter(CatalogWord.level == level)
    return q.scalar() or 0


def level_counts(db: Session) -> dict[str, int]:
    """Word count per level (plus ``all``) for the browse tabs."""
    rows = (
        db.query(CatalogWord.level, func.count(CatalogWord.id))
        .group_by(CatalogWord.level)
        .all()
    )
    counts = {lvl: 0 for lvl in LEVELS}
    for lvl, n in rows:
        counts[lvl] = n
    counts["all"] = sum(counts.values())
    return counts


def get_word_by_id(db: Session, word_id: int) -> CatalogWord | None:
    return db.get(CatalogWord, word_id)


def get_word_at_position(
    db: Session, position: int, level: str | None = None
) -> CatalogWord | None:
    """Return the word at a 0-based position within the (optionally filtered)
    catalog. OFFSET/LIMIT means this works the same for 20 or 10,000 rows.
    """
    if position < 0:
        return None
    return _base_query(db, level).offset(position).limit(1).first()


def list_words(
    db: Session,
    *,
    limit: int = 100,
    offset: int = 0,
    level: str | None = None,
) -> list[CatalogWord]:
    """A page of words, optionally filtered to a single level."""
    return _base_query(db, level).offset(offset).limit(limit).all()


# ---------------------------------------------------------------------------
# User answers (sentence + recording)
# ---------------------------------------------------------------------------
def get_answer(
    db: Session, user_id: int, catalog_word_id: int
) -> UserWordAnswer | None:
    return (
        db.query(UserWordAnswer)
        .filter(
            UserWordAnswer.user_id == user_id,
            UserWordAnswer.catalog_word_id == catalog_word_id,
        )
        .first()
    )


def save_answer(
    db: Session,
    user_id: int,
    catalog_word_id: int,
    *,
    user_sentence: str | None = None,
    recording_url: str | None = None,
) -> UserWordAnswer:
    """Create or update the user's answer for a word (upsert by user+word).

    Only provided (non-None) fields are written, so saving a sentence does not
    wipe a previously stored recording and vice versa.
    """
    answer = get_answer(db, user_id, catalog_word_id)
    if answer is None:
        answer = UserWordAnswer(user_id=user_id, catalog_word_id=catalog_word_id)
        db.add(answer)

    if user_sentence is not None:
        answer.user_sentence = user_sentence
    if recording_url is not None:
        answer.recording_url = recording_url

    db.commit()
    db.refresh(answer)
    return answer


def count_answered(db: Session, user_id: int) -> int:
    """How many catalog words this user has saved an answer for."""
    return (
        db.query(func.count(UserWordAnswer.id))
        .filter(UserWordAnswer.user_id == user_id)
        .scalar()
        or 0
    )


def answered_word_ids(db: Session, user_id: int) -> set[int]:
    """Set of catalog word ids the user has already answered.

    Used by the browse list to mark completed words with a check.
    """
    rows = (
        db.query(UserWordAnswer.catalog_word_id)
        .filter(UserWordAnswer.user_id == user_id)
        .all()
    )
    return {r[0] for r in rows}
