"""Pydantic schemas for learning paths."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class LearningPathBase(BaseModel):
    name: str
    slug: str
    description: str | None = None
    level: str = "mixed"  # beginner | intermediate | advanced | mixed
    goal_type: str | None = None
    is_active: bool = True


class LearningPathCreate(LearningPathBase):
    """Payload used when seeding/creating a path."""


class LearningPathRead(LearningPathBase):
    id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LearningPathSummary(BaseModel):
    """A path plus its word count, for browse/detail listings."""

    path: LearningPathRead
    word_count: int
