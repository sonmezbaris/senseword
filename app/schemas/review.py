"""Pydantic schemas for the review/spaced-repetition flow."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ReviewSubmit(BaseModel):
    """Payload sent when a user finishes reviewing a word.

    ``result`` is the self-rated difficulty which drives the next interval.
    """

    result: str  # easy | medium | hard


class ReviewLogRead(BaseModel):
    id: int
    vocabulary_id: int
    result: str
    reviewed_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DashboardStats(BaseModel):
    """Aggregated numbers shown on the dashboard."""

    total_words: int
    learned_words: int
    due_for_review: int
    reviews_today: int
