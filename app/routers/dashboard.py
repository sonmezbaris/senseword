"""Dashboard route: progress overview for the logged-in user."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers import templates
from app.services import (
    mission_service,
    progress_service,
    review_service,
    subscription_service,
    usage_service,
    vocabulary_service,
)
from app.services.auth_service import get_current_user

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Make sure users complete onboarding before seeing the dashboard.
    if not user.learning_goal:
        return RedirectResponse(url="/onboarding", status_code=303)

    stats = review_service.get_dashboard_stats(db, user.id)
    recent = vocabulary_service.recent_words(db, user.id, limit=5)
    # Spaced-repetition progress across the curated catalog.
    progress = progress_service.progress_summary(db, user.id)
    # Today's daily mission progress.
    mission = mission_service.get_today_summary(db, user.id)
    premium = subscription_service.user_has_premium_access(user)
    plan_label = subscription_service.get_user_plan_label(user)
    usage = usage_service.get_today_usage_summary(db, user)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "user": user,
            "stats": stats,
            "recent": recent,
            "progress": progress,
            "mission": mission,
            "premium": premium,
            "plan_label": plan_label,
            "usage": usage,
        },
    )
