"""Exam routes — multiple-choice cloze (fill-in-the-blank) practice tests.

Public (no login required): pick an exam format (IELTS / TOEFL / YDS / e-YDS)
and solve a freshly generated cloze test. Answers are checked instantly in the
browser (green tick), and the user can leave the exam at any time.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers import templates
from app.services import exam_service
from app.services.auth_service import get_current_user_optional

router = APIRouter(prefix="/exam", tags=["exam"])


@router.get("", response_class=HTMLResponse)
def exam_home(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Exam picker: choose which exam format to practice."""
    return templates.TemplateResponse(
        request,
        "exam_home.html",
        {"user": user, "exams": exam_service.list_exam_types()},
    )


@router.get("/{slug}", response_class=HTMLResponse)
def exam_take(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Generate and render an interactive cloze exam for the given format."""
    try:
        exam_type = exam_service.resolve_exam_type(slug)
    except ValueError:
        raise HTTPException(status_code=404, detail="Bilinmeyen sınav türü")

    exam = exam_service.generate(exam_type, db)
    # Flatten questions so the template can number them across passages.
    questions = [q for section in exam["sections"] for q in section["questions"]]
    return templates.TemplateResponse(
        request,
        "exam.html",
        {
            "user": user,
            "exam": exam,
            "questions": questions,
        },
    )
