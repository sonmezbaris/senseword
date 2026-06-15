"""Review routes: spaced-repetition session."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers import templates
from app.services import review_service, vocabulary_service
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/review", tags=["review"])


@router.get("", response_class=HTMLResponse)
def review_session(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Show the next word that is due for review (one at a time)."""
    word = review_service.get_next_due_word(db, user.id)
    due_count = len(review_service.get_due_words(db, user.id))
    return templates.TemplateResponse(
        request,
        "review.html",
        {"user": user, "word": word, "due_count": due_count},
    )


@router.post("/{word_id}")
def submit_review(
    word_id: int,
    result: str = Form(...),  # easy | medium | hard
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    word = vocabulary_service.get_word(db, user.id, word_id)
    if word:
        review_service.record_review(db, word, result)
    # Loop back to the review page, which serves the next due word.
    return RedirectResponse(url="/review", status_code=303)
