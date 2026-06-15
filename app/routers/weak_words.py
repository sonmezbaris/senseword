"""Weak Words page: words the user is struggling with.

Selection logic lives in ``progress_service`` (low strength / many wrong /
still learning); this router only fetches and renders.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers import templates
from app.services import progress_service
from app.services.auth_service import get_current_user

router = APIRouter(tags=["weak-words"])


@router.get("/weak-words", response_class=HTMLResponse)
def weak_words_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """List the user's weak words with stats and study actions."""
    rows = progress_service.list_weak_words(db, user.id)
    return templates.TemplateResponse(
        request,
        "weak_words.html",
        {"user": user, "rows": rows},
    )
