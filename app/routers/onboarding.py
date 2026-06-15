"""Onboarding routes: let a new user pick their learning goal once.

Shown right after registration, or on the next login for any existing user who
hasn't chosen a goal yet. Once a goal is saved the user goes to the dashboard.
"""

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers import templates
from app.services import auth_service
from app.services.auth_service import get_current_user

router = APIRouter(tags=["onboarding"])


@router.get("/onboarding", response_class=HTMLResponse)
def onboarding_page(
    request: Request,
    user: User = Depends(get_current_user),
):
    # Renders for both first-time users and those changing their goal later
    # (the current goal, if any, is pre-selected in the template).
    return templates.TemplateResponse(
        request,
        "onboarding.html",
        {"user": user, "goals": auth_service.LEARNING_GOALS, "error": None},
    )


@router.post("/onboarding")
def save_onboarding(
    request: Request,
    learning_goal: str = Form(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not auth_service.is_valid_goal(learning_goal):
        return templates.TemplateResponse(
            request,
            "onboarding.html",
            {
                "user": user,
                "goals": auth_service.LEARNING_GOALS,
                "error": "Please choose a valid learning goal.",
            },
            status_code=400,
        )

    auth_service.set_learning_goal(db, user, learning_goal)
    return RedirectResponse(url="/dashboard", status_code=303)
