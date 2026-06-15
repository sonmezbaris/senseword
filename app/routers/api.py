"""JSON API routes (versioned under /api/v1).

These endpoints return JSON rather than HTML so they can be consumed by the
frontend JavaScript today and by the future mobile app later.
"""

from fastapi import APIRouter, Query

from app.services import pronunciation_service

router = APIRouter(prefix="/api/v1", tags=["api"])


@router.get("/pronunciation")
def get_pronunciation(word: str = Query(..., description="English word to look up")):
    """Return the generated pronunciation for a single word.

    Example:
        GET /api/v1/pronunciation?word=apple
        -> {"word": "apple", "pronunciation": "/ˈæp.əl/"}
    """
    pronunciation = pronunciation_service.get_pronunciation(word)
    return {"word": word, "pronunciation": pronunciation}
