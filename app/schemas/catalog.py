"""Pydantic schemas for the curated vocabulary catalog and user answers."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CatalogWordBase(BaseModel):
    """Shape of a single catalog entry — mirrors the seed JSON exactly."""

    word: str
    turkish_translation: str
    pronunciation: str | None = None
    audio_url: str | None = None
    image_url: str | None = None
    example_sentence: str | None = None
    example_sentence_tr: str | None = None
    level: str = "intermediate"  # beginner | intermediate | advanced
    exam_category: list[str] = Field(default_factory=list)
    word_type: str | None = None  # noun | verb | adjective | adverb | ...


class CatalogWordCreate(CatalogWordBase):
    """Payload used when importing/seeding words."""


class CatalogWordRead(CatalogWordBase):
    id: int

    model_config = ConfigDict(from_attributes=True)


class UserAnswerCreate(BaseModel):
    """Payload for saving a learner's sentence for a catalog word."""

    catalog_word_id: int
    user_sentence: str | None = None


class UserAnswerRead(BaseModel):
    id: int
    catalog_word_id: int
    user_sentence: str | None = None
    recording_url: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
