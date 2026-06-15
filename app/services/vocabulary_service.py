"""Vocabulary service: CRUD operations scoped to a single user."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.vocabulary import Vocabulary
from app.schemas.vocabulary import VocabularyCreate, VocabularyUpdate


def list_words(db: Session, user_id: int) -> list[Vocabulary]:
    return (
        db.query(Vocabulary)
        .filter(Vocabulary.user_id == user_id)
        .order_by(Vocabulary.created_at.desc())
        .all()
    )


def get_word(db: Session, user_id: int, word_id: int) -> Vocabulary | None:
    return (
        db.query(Vocabulary)
        .filter(Vocabulary.id == word_id, Vocabulary.user_id == user_id)
        .first()
    )


def create_word(db: Session, user_id: int, payload: VocabularyCreate) -> Vocabulary:
    word = Vocabulary(user_id=user_id, **payload.model_dump())
    db.add(word)
    db.commit()
    db.refresh(word)
    return word


def update_word(
    db: Session, word: Vocabulary, payload: VocabularyUpdate
) -> Vocabulary:
    # Only overwrite fields that were actually provided.
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(word, field, value)
    db.commit()
    db.refresh(word)
    return word


def save_user_sentence(db: Session, word: Vocabulary, sentence: str) -> Vocabulary:
    """Store the learner's own sentence and mark the word as 'learning'."""
    word.user_sentence = sentence
    if word.status == "new":
        word.status = "learning"
    db.commit()
    db.refresh(word)
    return word


def delete_word(db: Session, word: Vocabulary) -> None:
    db.delete(word)
    db.commit()


def recent_words(db: Session, user_id: int, limit: int = 5) -> list[Vocabulary]:
    return (
        db.query(Vocabulary)
        .filter(Vocabulary.user_id == user_id)
        .order_by(Vocabulary.created_at.desc())
        .limit(limit)
        .all()
    )
