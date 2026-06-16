"""Public pricing page and premium upgrade flow."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.routers import templates
from app.services import subscription_service
from app.services.auth_service import get_current_user_optional

router = APIRouter(tags=["subscription"])


@router.get("/pricing", response_class=HTMLResponse)
def pricing_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Public pricing — no login required."""
    premium = subscription_service.user_has_premium_access(user) if user else False
    return templates.TemplateResponse(
        request,
        "pricing.html",
        {
            "user": user,
            "premium": premium,
            "plan_label": (
                subscription_service.get_user_plan_label(user) if user else None
            ),
        },
    )


@router.get("/upgrade", response_class=HTMLResponse)
def upgrade_page(
    request: Request,
    db: Session = Depends(get_db),
    user: User | None = Depends(get_current_user_optional),
):
    """Shown when a Free user tries to access a Premium feature."""
    if user and subscription_service.user_has_premium_access(user):
        return RedirectResponse(url="/dashboard", status_code=303)
    return templates.TemplateResponse(
        request,
        "upgrade.html",
        {"user": user},
    )
