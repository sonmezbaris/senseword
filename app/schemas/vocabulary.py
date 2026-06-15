"""Pydantic schemas for vocabulary words."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class VocabularyBase(BaseModel):
    word: str
    meaning: str  # Turkish meaning
    pronunciation: str | None = None
    example_sentence: str | None = None
    image_url: str | None = None
    difficulty: str = "medium"  # easy | medium | hard


class VocabularyCreate(VocabularyBase):
    """Payload for adding a new word."""


class VocabularyUpdate(BaseModel):
    """Partial update payload; all fields optional."""

    word: str | None = None
    meaning: str | None = None
    pronunciation: str | None = None
    example_sentence: str | None = None
    image_url: str | None = None
    user_sentence: str | None = None
    difficulty: str | None = None
    status: str | None = None


class VocabularyRead(VocabularyBase):
    id: int
    user_id: int
    user_sentence: str | None = None
    status: str
    review_count: int
    next_review_date: datetime
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
