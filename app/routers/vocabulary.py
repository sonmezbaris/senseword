"""Vocabulary routes: list and add words."""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers import templates
from app.schemas.vocabulary import VocabularyCreate
from app.services import pronunciation_service, vocabulary_service
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])


@router.get("", response_class=HTMLResponse)
def vocabulary_list(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    words = vocabulary_service.list_words(db, user.id)
    return templates.TemplateResponse(
        request, "vocabulary_list.html", {"user": user, "words": words}
    )


@router.get("/add", response_class=HTMLResponse)
def add_word_page(
    request: Request,
    user: User = Depends(get_current_user),
):
    return templates.TemplateResponse(
        request, "vocabulary_add.html", {"user": user, "error": None}
    )


@router.post("/add")
def add_word(
    request: Request,
    word: str = Form(...),
    meaning: str = Form(...),
    pronunciation: str = Form(""),
    example_sentence: str = Form(""),
    image_url: str = Form(""),
    difficulty: str = Form("medium"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Fallback: if the user left pronunciation empty (e.g. JS disabled),
    # auto-generate it on the server so the field is never blank.
    pronunciation = pronunciation.strip()
    if not pronunciation:
        pronunciation = pronunciation_service.get_pronunciation(word)

    payload = VocabularyCreate(
        word=word.strip(),
        meaning=meaning.strip(),
        pronunciation=pronunciation or None,
        example_sentence=example_sentence.strip() or None,
        image_url=image_url.strip() or None,
        difficulty=difficulty,
    )
    vocabulary_service.create_word(db, user.id, payload)
    return RedirectResponse(url="/vocabulary", status_code=303)


@router.post("/{word_id}/delete")
def delete_word(
    word_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    word = vocabulary_service.get_word(db, user.id, word_id)
    if word:
        vocabulary_service.delete_word(db, word)
    return RedirectResponse(url="/vocabulary", status_code=303)
