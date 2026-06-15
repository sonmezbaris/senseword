"""Learning routes: the multisensory study page for a single word."""

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers import templates
from app.services import speech_service, vocabulary_service
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/learn", tags=["learning"])


@router.get("/{word_id}", response_class=HTMLResponse)
def learn_word(
    word_id: int,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    word = vocabulary_service.get_word(db, user.id, word_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    guide = speech_service.get_pronunciation_guide(word.word, word.pronunciation)
    return templates.TemplateResponse(
        request,
        "learning_word.html",
        {"user": user, "word": word, "guide": guide},
    )


@router.post("/{word_id}/sentence")
def save_sentence(
    word_id: int,
    user_sentence: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Save the learner's own sentence (the active-recall step)."""
    word = vocabulary_service.get_word(db, user.id, word_id)
    if not word:
        raise HTTPException(status_code=404, detail="Word not found")

    vocabulary_service.save_user_sentence(db, word, user_sentence.strip())
    return RedirectResponse(url=f"/learn/{word_id}", status_code=303)
